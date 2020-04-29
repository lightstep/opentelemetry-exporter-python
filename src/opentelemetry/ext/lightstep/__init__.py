import math
import os
import typing

from google.protobuf.timestamp_pb2 import Timestamp
import requests

from opentelemetry import trace as trace_api
from opentelemetry.ext.lightstep import reporter
from opentelemetry.ext.lightstep.api_client import APIClient
from opentelemetry.sdk.trace import export as sdk

from opentelemetry.ext.lightstep import util
from opentelemetry.ext.lightstep.protobuf.collector_pb2 import (
    Auth,
    ReportRequest,
    Span,
    KeyValue,
    Reference,
    SpanContext,
)
from opentelemetry.ext.lightstep.version import __version__

TRACING_URL_ENV_VAR = "LS_TRACING_URL"
_DEFAULT_TRACING_URL = os.environ.get(
    TRACING_URL_ENV_VAR, "https://ingest.lightstep.com:443/api/v2/report"
)


_NANOS_IN_SECONDS = 1000000000
_NANOS_IN_MICROS = 1000


def _set_kv_value(kv, value):
    if isinstance(value, bool):
        kv.bool_value = value
    elif isinstance(value, int):
        kv.int_value = value
    elif isinstance(value, float):
        kv.double_value = value
    else:
        kv.string_value = value


def _nsec_to_sec(nsec=0):
    """Convert nanoseconds to seconds float."""
    nsec = nsec or 0
    return nsec / _NANOS_IN_SECONDS


def _time_to_seconds_nanos(nsec):
    """Convert time from nanos to a tuple containing
    seconds and nanoseconds.
    """
    nsec = nsec or 0
    seconds = int(_nsec_to_sec(nsec))
    nanos = int(nsec % _NANOS_IN_SECONDS)
    return (seconds, nanos)


def _span_duration(start, end):
    """Convert a time.time()-style timestamp to microseconds."""
    start = start or 0
    end = end or 0
    return math.floor(round((end - start) / 1000))


class LightstepSpanExporter(sdk.SpanExporter):
    """Lightstep span exporter for OpenTelemetry.
    """

    def __init__(
        self,
        name,
        token="",
        host="ingest.lightstep.com",
        port=443,
        encryption="tls",
        service_version=None,
    ):
        tags = {
            "lightstep.tracer_platform": "otel-ls-python",
            "lightstep.tracer_platform_version": __version__,
        }

        scheme = "https"
        if encryption != "tls":
            scheme = "http"

        url = "{}://{}:{}/api/v2/report".format(scheme, host, port)

        self._auth = self.create_auth(token)
        self._client = APIClient(token, url=url)
        self._guid = util._generate_guid()
        self._reporter = reporter.get_reporter(
            name, service_version, self._guid
        )

        if service_version is not None:
            tags["service.version"] = service_version

    def export(self, spans: typing.Sequence[sdk.Span]) -> "SpanExportResult":
        span_records = []
        for span in spans:
            span_record = self.create_span_record(span, self._guid)
            span_records.append(span_record)
            attrs = {}
            if span.resource is not None:
                attrs.update(span.resource.labels)
            if span.attributes is not None:
                attrs.update(span.attributes)
            for key, val in attrs.items():
                self.append_attribute(span_record, key, val)

            for event in span.events:
                event.attributes["message"] = event.name
                self.append_log(
                    span_record, event.attributes, event.timestamp,
                )

        if len(span_records) == 0:
            return sdk.SpanExportResult.SUCCESS

        report_request = ReportRequest(
            auth=self._auth, reporter=self._reporter, spans=span_records
        )
        # from google.protobuf.json_format import MessageToJson

        # print(MessageToJson(report_request))

        resp = self._client.send(report_request.SerializeToString())
        if resp.status_code == requests.codes["ok"]:
            return sdk.SpanExportResult.SUCCESS
        return sdk.SpanExportResult.FAILURE

    def shutdown(self) -> None:
        """Flush remaining spans"""
        # self.tracer.flush()

    def create_auth(self, access_token):
        auth = Auth()
        auth.access_token = access_token
        return auth

    def create_span_record(self, span: sdk.Span, guid: str):
        #     is_remote=span.context.is_remote,
        span_context = SpanContext(
            trace_id=0xFFFFFFFFFFFFFFFF & span.context.trace_id,
            span_id=0xFFFFFFFFFFFFFFFF & span.context.span_id,
        )
        parent_id = None
        if isinstance(span.parent, trace_api.SpanContext):
            parent_id = span.parent.span_id
        elif isinstance(span.parent, trace_api.Span):
            parent_id = span.parent.get_context().span_id
            #     start_time=_nsec_to_sec(span.start_time),
            #     tags=attrs,
            # )
        seconds, nanos = _time_to_seconds_nanos(span.start_time)
        span_record = Span(
            span_context=span_context,
            operation_name=span.name,
            start_timestamp=Timestamp(seconds=seconds, nanos=nanos),
            duration_micros=int(
                _span_duration(span.start_time, span.end_time)
            ),
        )
        if parent_id is not None:
            reference = span_record.references.add()
            reference.relationship = Reference.CHILD_OF
            reference.span_context.span_id = parent_id

        return span_record

    def append_attribute(self, span_record, key, value):
        kv = span_record.tags.add()
        kv.key = key
        _set_kv_value(kv, value)

    def append_join_id(self, span_record, key, value):
        self.append_attribute(span_record, key, value)

    def append_log(self, span_record, attrs, timestamp):
        if len(attrs) > 0:
            seconds, nanos = _time_to_seconds_nanos(timestamp)

            proto_log = span_record.logs.add()
            proto_log.timestamp.seconds = seconds
            proto_log.timestamp.nanos = nanos
            for k, v in attrs.items():
                field = proto_log.fields.add()
                field.key = k
                _set_kv_value(field, v)

    def create_report(self, runtime, span_records):
        return ReportRequest(reporter=runtime, spans=span_records)

    def combine_span_records(self, report_request, span_records):
        report_request.spans.extend(span_records)
        return report_request.spans

    def num_span_records(self, report_request):
        return len(report_request.spans)

    def get_span_records(self, report_request):
        return report_request.spans

    def get_span_name(self, span_record):
        return span_record.operation_name


class LightStepSpanExporter(LightstepSpanExporter):
    """Backwards compatibility wrapper class"""

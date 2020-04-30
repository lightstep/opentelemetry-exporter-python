import math
import os
import typing

import requests
from google.protobuf.timestamp_pb2 import Timestamp
from opentelemetry import trace as trace_api
from opentelemetry.ext.lightstep import reporter, util
from opentelemetry.ext.lightstep.api_client import APIClient
from opentelemetry.ext.lightstep.protobuf.collector_pb2 import (
    Auth,
    KeyValue,
    Reference,
    ReportRequest,
    Span,
    SpanContext,
)
from opentelemetry.ext.lightstep.version import __version__
from opentelemetry.sdk.trace import export as sdk

TRACING_URL_ENV_VAR = "LS_TRACING_URL"
_DEFAULT_TRACING_URL = os.environ.get(
    TRACING_URL_ENV_VAR, "https://ingest.lightstep.com:443/api/v2/report"
)


_NANOS_IN_SECONDS = 1000000000
_NANOS_IN_MICROS = 1000


def _set_kv_value(key_value, value):
    if isinstance(value, bool):
        key_value.bool_value = value
    elif isinstance(value, int):
        key_value.int_value = value
    elif isinstance(value, float):
        key_value.double_value = value
    else:
        key_value.string_value = value


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


def _create_span_record(span: sdk.Span):
    span_context = SpanContext(
        trace_id=0xFFFFFFFFFFFFFFFF & span.context.trace_id,
        span_id=0xFFFFFFFFFFFFFFFF & span.context.span_id,
    )

    parent_id = None
    if isinstance(span.parent, trace_api.SpanContext):
        parent_id = span.parent.span_id
    elif isinstance(span.parent, trace_api.Span):
        parent_id = span.parent.get_context().span_id

    seconds, nanos = _time_to_seconds_nanos(span.start_time)
    span_record = Span(
        span_context=span_context,
        operation_name=span.name,
        start_timestamp=Timestamp(seconds=seconds, nanos=nanos),
        duration_micros=int(_span_duration(span.start_time, span.end_time)),
    )
    if parent_id is not None:
        reference = span_record.references.add()
        reference.relationship = Reference.CHILD_OF
        reference.span_context.span_id = parent_id

    return span_record


def _append_log(span_record, attrs, timestamp):
    if len(attrs) > 0:
        seconds, nanos = _time_to_seconds_nanos(timestamp)

        proto_log = span_record.logs.add()
        proto_log.timestamp.seconds = seconds
        proto_log.timestamp.nanos = nanos
        for key, val in attrs.items():
            field = proto_log.fields.add()
            field.key = key
            _set_kv_value(field, val)


class LightstepSpanExporter(sdk.SpanExporter):
    """Lightstep span exporter for OpenTelemetry."""

    def __init__(
        self,
        name: str,
        token: str = "",
        host: str = "ingest.lightstep.com",
        port: int = 443,
        secure: bool = True,
        service_version: typing.Optional[str] = None,
    ):
        tags = {
            "lightstep.tracer_platform": "otel-ls-python",
            "lightstep.tracer_platform_version": __version__,
        }

        scheme = "https" if secure else "http"

        url = os.environ.get(
            TRACING_URL_ENV_VAR,
            "{}://{}:{}/api/v2/report".format(scheme, host, port)
        )

        self._auth = Auth()
        self._auth.access_token = token

        self._client = APIClient(token, url=url)
        self._guid = util._generate_guid()
        self._reporter = reporter.get_reporter(
            name, service_version, self._guid
        )

        if service_version is not None:
            tags["service.version"] = service_version

    def export(self, spans: typing.Sequence[sdk.Span]) -> sdk.SpanExportResult:
        """Exports a batch of telemetry data.

        Args:
            spans: The list of `opentelemetry.trace.Span` objects to be exported

        Returns:
            The result of the export
        """
        span_records = []
        for span in spans:
            span_record = _create_span_record(span)
            span_records.append(span_record)
            attrs = {}
            if span.resource is not None:
                attrs.update(span.resource.labels)
            if span.attributes is not None:
                attrs.update(span.attributes)
            for key, val in attrs.items():
                key_value = span_record.tags.add()
                key_value.key = key
                _set_kv_value(key_value, val)

            for event in span.events:
                event.attributes["message"] = event.name
                _append_log(
                    span_record, event.attributes, event.timestamp,
                )

        if len(span_records) == 0:
            return sdk.SpanExportResult.SUCCESS

        report_request = ReportRequest(
            auth=self._auth, reporter=self._reporter, spans=span_records
        )

        resp = self._client.send(report_request.SerializeToString())
        if resp.status_code == requests.codes["ok"]:
            return sdk.SpanExportResult.SUCCESS
        return sdk.SpanExportResult.FAILURE

    def shutdown(self) -> None:
        """Not currently implemented."""


def LightStepSpanExporter(*args, **kwargs):
    """Backwards compatibility wrapper."""
    import warnings

    warnings.warn(
        "LightStepSpanExporter() is deprecated; use LightstepSpanExporter().",
        DeprecationWarning,
        stacklevel=2,
    )
    return LightstepSpanExporter(*args, **kwargs)

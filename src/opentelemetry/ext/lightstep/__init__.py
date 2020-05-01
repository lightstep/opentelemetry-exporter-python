import math
import os
import typing
from typing import Dict, Union

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


_SPAN_KIND_LIST = [
    "internal",
    "server",
    "client",
    "producer",
    "consumer",
]


def _set_kv_value(key_value: KeyValue, value: any) -> None:
    """Sets the correct value type for a KeyValue.

    Args:
        key_value: the `KeyValue` to modify
        value: the value set
    """
    if isinstance(value, bool):
        key_value.bool_value = value
    elif isinstance(value, int):
        key_value.int_value = value
    elif isinstance(value, float):
        key_value.double_value = value
    else:
        key_value.string_value = str(value)


def _time_to_seconds_nanos(
    nsec: typing.Union[int, None]
) -> typing.Tuple[int, int]:
    """Convert time from nanos to a tuple containing
    seconds and nanoseconds.
    """
    nsec = nsec or 0
    seconds = int(nsec / _NANOS_IN_SECONDS)
    nanos = int(nsec % _NANOS_IN_SECONDS)
    return (seconds, nanos)


def _span_duration(start: Union[int, None], end: Union[int, None]) -> int:
    """Calculate span duration in microseconds.

    Args:
        start: start time in ns
        end: end time in ns

    Returns:
        Duration in microseconds.
    """
    start = start or 0
    end = end or 0
    if end < start:
        return 0
    return math.floor(round((end - start) / 1000))


def _convert_span(span: sdk.Span) -> Span:
    """Translate an OpenTelemetry span into a Lightstep Span.
    Args:
        span: OpenTelemetry Span to translate
    Returns:
        Lightstep span.
    """
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
    span_record.tags.add(
        key="span.kind", string_value=_SPAN_KIND_LIST[span.kind.value]
    )
    if parent_id is not None:
        reference = span_record.references.add()  # pylint: disable=no-member
        reference.relationship = (
            Reference.CHILD_OF  # pylint: disable=no-member
        )
        reference.span_context.span_id = parent_id

    return span_record


def _append_log(
    span_record: Span, attrs: Dict, timestamp: Union[int, None]
) -> None:
    """Appends a log to span by converting an OpenTelemetry event to a log.

    Args:
        span_record: span to append the log to
        attrs: the attributes to append as fields to the log
        timestamp: time associated with the event
    """
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
            "{}://{}:{}/api/v2/report".format(scheme, host, port),
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
            span_record = _convert_span(span)
            span_records.append(span_record)
            attrs = {}
            if span.resource is not None:
                attrs.update(span.resource.labels)
            if span.attributes is not None:
                attrs.update(span.attributes)
            for key, val in attrs.items():
                key_value = span_record.tags.add()  # pylint: disable=no-member
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
        return sdk.SpanExportResult.FAILED_NOT_RETRYABLE

    def shutdown(self) -> None:
        """Not currently implemented."""


# pylint: disable=invalid-name
def LightStepSpanExporter(*args, **kwargs):
    """Backwards compatibility wrapper."""
    import warnings  # pylint: disable=import-outside-toplevel

    warnings.warn(
        "LightStepSpanExporter() is deprecated; use LightstepSpanExporter().",
        DeprecationWarning,
        stacklevel=2,
    )
    return LightstepSpanExporter(*args, **kwargs)

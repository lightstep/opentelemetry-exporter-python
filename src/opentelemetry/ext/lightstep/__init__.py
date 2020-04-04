import typing
import lightstep

from basictracer.span import BasicSpan
from opentelemetry.sdk.trace.export import Span, SpanExporter, SpanExportResult
from opentelemetry.trace import SpanContext


def _nsec_to_sec(nsec=0):
    """Convert nanoseconds to seconds float"""
    nsec = nsec or 0
    return nsec / 1000000000


class LightStepSpanExporter(SpanExporter):
    """LightStep span exporter for OpenTelemetry.
    """

    def __init__(
        self,
        name,
        token="",
        host="ingest.lightstep.com",
        port=443,
        encryption="tls",
        verbosity=0,
    ):
        self.tracer = lightstep.Tracer(
            component_name=name,
            access_token=token,
            collector_host=host,
            collector_port=port,
            collector_encryption=encryption,
            verbosity=verbosity,
            use_http=False,
            use_thrift=True,
        )

    def export(self, spans: typing.Sequence[Span]) -> "SpanExportResult":
        for span in spans:
            ctx = SpanContext(
                trace_id=0xFFFFFFFFFFFFFFFF & span.context.trace_id,
                span_id=0xFFFFFFFFFFFFFFFF & span.context.span_id,
                is_remote=span.context.is_remote,
            )
            lightstep_span = BasicSpan(
                self.tracer,
                operation_name=span.name,
                context=ctx,
                start_time=_nsec_to_sec(span.start_time),
                tags=span.attributes,
            )
            lightstep_span.finish(finish_time=_nsec_to_sec(span.end_time))
        self.tracer.flush()
        return SpanExportResult.SUCCESS

    def shutdown(self) -> None:
        self.tracer.flush()

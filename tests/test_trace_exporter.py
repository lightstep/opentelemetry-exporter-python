import unittest

from unittest.mock import patch


from opentelemetry import trace as trace_api
from opentelemetry.sdk import trace
from opentelemetry.ext.lightstep import LightStepSpanExporter
from opentelemetry.sdk.trace.export import SpanExportResult


class MockTracer:
    """ Used to mock lightstep.Tracer """

    def __init__(
        self,
        component_name,
        access_token,
        collector_host,
        collector_port,
        collector_encryption,
        verbosity,
        use_http=False,
        use_thrift=False,
    ):
        self.name = component_name
        self.token = access_token
        self.host = collector_host
        self.port = collector_port
        self.encryption = collector_encryption
        self.verbosity = verbosity
        self.use_http = use_http
        self.use_thrift = use_thrift
        self.spans = []

    def record(self, span):
        self.spans.append(span)

    def flush(self):
        pass


class TestLightStepSpanExporter(unittest.TestCase):
    @patch("lightstep.Tracer", MockTracer)
    def test_constructor_default(self):
        """Test the default values assigned by constructor."""
        name = "my-service-name"
        host = "ingest.lightstep.com"
        port = 443
        encryption = "tls"
        verbosity = 0
        token = ""
        exporter = LightStepSpanExporter(name)

        self.assertEqual(exporter.tracer.name, name)
        self.assertEqual(exporter.tracer.host, host)
        self.assertEqual(exporter.tracer.port, port)
        self.assertEqual(exporter.tracer.encryption, encryption)
        self.assertEqual(exporter.tracer.verbosity, verbosity)
        self.assertEqual(exporter.tracer.token, token)

    @patch("lightstep.Tracer", MockTracer)
    def test_export(self):
        # pylint: disable=invalid-name
        self.maxDiff = None

        span_names = ("test1", "test2", "test3")
        trace_id = 0x6E0C63257DE34C926F9EFCD03927272E
        trace_id_high = 0x6E0C63257DE34C92
        trace_id_low = 0x6F9EFCD03927272E
        span_id = 0x34BF92DEEFC58C92
        parent_id = 0x1111111111111111
        other_id = 0x2222222222222222

        base_time = 683647322 * 10 ** 9  # in ns
        start_times = (
            base_time,
            base_time + 150 * 10 ** 6,
            base_time + 300 * 10 ** 6,
        )
        durations = (50 * 10 ** 6, 100 * 10 ** 6, 200 * 10 ** 6)
        end_times = (
            start_times[0] + durations[0],
            start_times[1] + durations[1],
            start_times[2] + durations[2],
        )

        span_context = trace_api.SpanContext(trace_id, span_id)
        parent_context = trace_api.SpanContext(trace_id, parent_id)
        other_context = trace_api.SpanContext(trace_id, other_id)

        event_attributes = {
            "annotation_bool": True,
            "annotation_string": "annotation_test",
            "key_float": 0.3,
        }

        event_timestamp = base_time + 50 * 10 ** 6
        event = trace_api.Event(
            name="event0", timestamp=event_timestamp, attributes=event_attributes,
        )

        link_attributes = {"key_bool": True}

        link = trace_api.Link(context=other_context, attributes=link_attributes)

        otel_spans = [
            trace.Span(
                name=span_names[0],
                context=span_context,
                parent=parent_context,
                events=(event,),
                links=(link,),
                kind=trace_api.SpanKind.CLIENT,
            ),
            trace.Span(name=span_names[1], context=parent_context, parent=None),
            trace.Span(name=span_names[2], context=other_context, parent=None),
        ]

        exporter = LightStepSpanExporter("my-service-name")
        self.assertEqual(exporter.export(otel_spans), SpanExportResult.SUCCESS)
        self.assertEqual(len(exporter.tracer.spans), len(otel_spans))
        # TODO: add tests for tags/attributes and span hierarchy

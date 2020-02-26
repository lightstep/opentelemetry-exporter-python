import unittest

from unittest.mock import patch

from opentelemetry import trace as trace_api
from opentelemetry.sdk import trace
from opentelemetry.ext.lightstep import LightStepSpanExporter
from opentelemetry.sdk.trace.export import SpanExportResult
from opentelemetry.trace.status import Status, StatusCanonicalCode


# TODO: add tests for tags/attributes and span hierarchy
class TestLightStepSpanExporter(unittest.TestCase):
    @patch("lightstep.Tracer")
    def test_constructor_default(self, mock_tracer):
        """Test the default values assigned by constructor."""
        name = "my-service-name"
        LightStepSpanExporter(name)
        mock_tracer.assert_called_once_with(
            component_name=name,
            access_token="",
            collector_host="ingest.lightstep.com",
            collector_port=443,
            collector_encryption="tls",
            verbosity=0,
            use_http=False,
            use_thrift=True,
        )

    @patch("lightstep.Tracer")
    def test_export(self, mock_tracer):
        # pylint: disable=invalid-name
        span_names = ("test1", "test2", "test3")
        trace_id = 0x6E0C63257DE34C926F9EFCD03927272E
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

        otel_spans[0].start(start_time=start_times[0])
        # added here to preserve order
        otel_spans[0].set_attribute("key_bool", False)
        otel_spans[0].set_attribute("key_string", "hello_world")
        otel_spans[0].set_attribute("key_float", 111.22)
        otel_spans[0].set_status(
            Status(StatusCanonicalCode.UNKNOWN, "Example description")
        )
        otel_spans[0].end(end_time=end_times[0])

        otel_spans[1].start(start_time=start_times[1])
        otel_spans[1].end(end_time=end_times[1])

        otel_spans[2].start(start_time=start_times[2])
        otel_spans[2].end(end_time=end_times[2])

        exporter = LightStepSpanExporter("my-service-name")
        result_spans = []

        with patch.object(
            exporter.tracer, "record", side_effect=lambda x: result_spans.append(x)
        ):
            self.assertEqual(exporter.export(otel_spans), SpanExportResult.SUCCESS)
        self.assertEqual(len(result_spans), len(otel_spans))
        for index, _ in enumerate(span_names):
            self.assertEqual(result_spans[index].operation_name, span_names[index])
            self.assertEqual(
                result_spans[index].start_time, start_times[index] / 1000000000
            )
            self.assertEqual(
                round(result_spans[index].duration, 2), durations[index] / 1000000000,
            )

import unittest

from unittest.mock import patch

from opentelemetry import trace as trace_api
from opentelemetry.sdk import trace
import opentelemetry.ext.lightstep
from opentelemetry.ext.lightstep import LightStepSpanExporter
from opentelemetry.sdk.trace.export import SpanExportResult
from opentelemetry.trace.status import Status, StatusCanonicalCode


class TestLightStepSpanExporter(unittest.TestCase):
    def setUp(self):
        self._trace_id = 0x6E0C63257DE34C926F9EFCD03927272E
        self._exporter = LightStepSpanExporter(
            "my-service-name", service_version="1.2.3"
        )
        self._exporter.tracer = unittest.mock.Mock()
        self._span_context = trace_api.SpanContext(
            self._trace_id, 0x2222222222222222, is_remote=False
        )

    def _process_spans(self, otel_spans):
        result_spans = []

        with patch.object(
            self._exporter.tracer,
            "record",
            side_effect=lambda x: result_spans.append(x),
        ):
            self.assertEqual(
                self._exporter.export(otel_spans), SpanExportResult.SUCCESS
            )

        return result_spans

    @patch("lightstep.Tracer")
    def test_constructor_default(self, mock_tracer):
        # pylint: disable=unused-argument
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
            tags={
                "lightstep.tracer_platform": "otel-ls-python",
                "lightstep.tracer_platform_version": opentelemetry.ext.lightstep.__version__,
            },
        )

    @patch("lightstep.Tracer")
    def test_export(self, mock_tracer):
        # pylint: disable=unused-argument
        span_names = ("test1", "test2", "test3")

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

        span_context = trace_api.SpanContext(
            self._trace_id, 0x34BF92DEEFC58C92, is_remote=False
        )
        parent_context = trace_api.SpanContext(
            self._trace_id, 0x1111111111111111, is_remote=False
        )
        other_context = trace_api.SpanContext(
            self._trace_id, 0x2222222222222222, is_remote=False
        )

        otel_spans = [
            trace.Span(
                name=span_names[0],
                context=span_context,
                parent=parent_context,
                kind=trace_api.SpanKind.CLIENT,
            ),
            trace.Span(name=span_names[1], context=parent_context, parent=None),
            trace.Span(name=span_names[2], context=other_context, parent=None),
        ]

        otel_spans[0].start(start_time=start_times[0])
        # added here to preserve order
        otel_spans[0].set_status(
            Status(StatusCanonicalCode.UNKNOWN, "Example description")
        )
        otel_spans[0].end(end_time=end_times[0])

        otel_spans[1].start(start_time=start_times[1])
        otel_spans[1].end(end_time=end_times[1])

        otel_spans[2].start(start_time=start_times[2])
        otel_spans[2].end(end_time=end_times[2])

        result_spans = self._process_spans(otel_spans)
        self.assertEqual(len(result_spans), len(otel_spans))
        for index, _ in enumerate(span_names):
            self.assertEqual(result_spans[index].operation_name, span_names[index])
            self.assertEqual(
                result_spans[index].start_time, start_times[index] / 1000000000
            )
            self.assertEqual(
                round(result_spans[index].duration, 2), durations[index] / 1000000000,
            )

        # test parent hierarchy
        self.assertIsNotNone(result_spans[0].parent_id)
        self.assertEqual(result_spans[0].parent_id, result_spans[1].context.span_id)
        self.assertIsNone(result_spans[1].parent_id)

    @patch("lightstep.Tracer")
    def test_span_attributes(self, mock_tracer):
        """ ensure span attributes are passed as tags """
        otel_span = trace.Span(name=__name__, context=self._span_context)
        otel_span.set_attribute("key_bool", False)
        otel_span.set_attribute("key_string", "hello_world")
        otel_span.set_attribute("key_float", 111.22)
        result_spans = self._process_spans([otel_span])
        self.assertEqual(len(result_spans), 1)
        self.assertEqual(len(result_spans[0].tags), 3)
        self.assertFalse(result_spans[0].tags.get("key_bool"))
        self.assertEqual(result_spans[0].tags.get("key_string"), "hello_world")
        self.assertEqual(result_spans[0].tags.get("key_float"), 111.22)

    @patch("lightstep.Tracer")
    def test_events(self, mock_tracer):
        """ test events are translated into logs """
        base_time = 683647322 * 10 ** 9  # in ns
        event_attributes = {
            "annotation_bool": True,
            "annotation_string": "annotation_test",
            "key_float": 0.3,
        }

        event_timestamp = base_time + 50 * 10 ** 6
        event = trace.Event(
            name="event0", timestamp=event_timestamp, attributes=event_attributes,
        )
        otel_span = trace.Span(
            name=__name__, context=self._span_context, events=(event,),
        )
        result_spans = self._process_spans([otel_span])
        self.assertEqual(len(result_spans), 1)
        self.assertEqual(len(result_spans[0].logs), 1)
        log = result_spans[0].logs[0]
        # timestamp is in seconds, event_timestamp in ns
        self.assertEqual(log.timestamp, (event_timestamp / 1000000000))
        self.assertEqual(log.key_values, event_attributes)

    @patch("lightstep.Tracer")
    def test_links(self, mock_tracer):
        """ test links are translated into references """
        # TODO

    #     link_attributes = {"key_bool": True}

    #     link = trace_api.Link(context=self._span_context, attributes=link_attributes)
    #     otel_span = trace.Span(
    #         name=__name__, context=self._span_context, links=(link,),
    #     )
    #     result_spans = self._process_spans([otel_span])
    #     self.assertEqual(len(result_spans), 1)
    #     self.assertEqual(len(result_spans[0].references), 1)

    @patch("lightstep.Tracer")
    def test_resources(self, mock_tracer):
        """ test resources """
        resource = trace.Resource(labels={"test": "123", "other": "456"})
        otel_span = trace.Span(
            name=__name__, context=self._span_context, resource=resource,
        )
        otel_span.set_attribute("test", "789")
        otel_span.set_attribute("one-more", "000")
        result_spans = self._process_spans([otel_span])
        self.assertEqual(len(result_spans), 1)
        self.assertEqual(result_spans[0].tags.get("test"), "789")
        self.assertEqual(result_spans[0].tags.get("other"), "456")
        self.assertEqual(result_spans[0].tags.get("one-more"), "000")

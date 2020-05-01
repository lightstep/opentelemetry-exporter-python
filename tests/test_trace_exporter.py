import unittest
from test.support import EnvironmentVarGuard  # Python >=3
from unittest.mock import patch

import httpretty

from opentelemetry import trace as trace_api
from opentelemetry.ext.lightstep import (
    TRACING_URL_ENV_VAR,
    LightstepSpanExporter,
)
from opentelemetry.ext.lightstep.protobuf.collector_pb2 import ReportRequest
from opentelemetry.sdk import trace
from opentelemetry.sdk.trace.export import SpanExportResult
from opentelemetry.trace.status import Status, StatusCanonicalCode


class TestLightStepSpanExporter(unittest.TestCase):
    def setUp(self):
        self.env = EnvironmentVarGuard()
        self.env.unset(TRACING_URL_ENV_VAR)
        self._trace_id = 0x6E0C63257DE34C926F9EFCD03927272E
        self._exporter = LightstepSpanExporter(
            "my-service-name",
            service_version="1.2.3",
            host="localhost",
            port="443",
        )
        self._exporter.tracer = unittest.mock.Mock()
        self._span_context = trace_api.SpanContext(
            self._trace_id, 0x2222222222222222, is_remote=False
        )
        httpretty.enable()
        httpretty.register_uri(
            httpretty.POST, "https://localhost:443/api/v2/report",
        )

    def tearDown(self):
        httpretty.disable()
        httpretty.reset()

    def _process_spans(self, otel_spans):
        self.assertEqual(
            self._exporter.export(otel_spans), SpanExportResult.SUCCESS
        )
        self.assertEqual(len(httpretty.latest_requests()), 1)

        report_request = ReportRequest()
        report_request.ParseFromString(httpretty.last_request().body)

        return report_request.spans

    def test_constructor_default(self):
        # pylint: disable=unused-argument
        """Test the default values assigned by constructor."""
        name = "my-service-name"
        exporter = LightstepSpanExporter(name)
        self.assertEqual(
            exporter._client._url,
            "https://ingest.lightstep.com:443/api/v2/report",
        )

    def test_export_failed(self):
        httpretty.disable()
        httpretty.reset()
        httpretty.enable()
        httpretty.register_uri(
            httpretty.POST, "https://localhost:443/api/v2/report", status=404,
        )
        self.assertEqual(
            self._exporter.export(
                [trace.Span("fail-test", trace.SpanContext(1, 2, False))]
            ),
            SpanExportResult.FAILED_NOT_RETRYABLE,
        )

    def test_export(self):
        # pylint: disable=unused-argument
        span_names = ("test1", "test2", "test3")

        base_time = 683647322 * 10 ** 9  # in ns
        start_times = (
            base_time,
            base_time + 150 * 10 ** 6,
            base_time + 300 * 10 ** 6,
        )
        durations = (50 * 10 ** 6, 100 * 10 ** 6, 0)
        end_times = (
            start_times[0] + durations[0],
            start_times[1] + durations[1],
            start_times[2] - 100 * 10 ** 6,
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
            trace.Span(
                name=span_names[1], context=parent_context, parent=None
            ),
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
            self.assertEqual(
                result_spans[index].operation_name, span_names[index]
            )
            self.assertEqual(
                result_spans[index].start_timestamp.seconds,
                int(start_times[index] / 1000000000),
            )
            self.assertEqual(
                result_spans[index].duration_micros,
                int(durations[index] / 1000),
            )

        # test parent hierarchy
        self.assertEqual(len(result_spans[0].references), 1)
        self.assertEqual(
            result_spans[0].references[0].span_context.span_id,
            result_spans[1].span_context.span_id,
        )
        self.assertEqual(len(result_spans[1].references), 0)

        # ensure tag is set for kind
        self.assertEqual(len(result_spans[0].tags), 1)
        for tag in result_spans[0].tags:
            if tag.key == "span.kind":
                self.assertEqual(tag.string_value, "client")
        for tag in result_spans[1].tags:
            if tag.key == "span.kind":
                self.assertEqual(tag.string_value, "internal")

    def test_span_attributes(self):
        """Ensure span attributes are passed as tags."""
        otel_span = trace.Span(name=__name__, context=self._span_context)
        otel_span.set_attribute("key_bool", False)
        otel_span.set_attribute("key_string", "hello_world")
        otel_span.set_attribute("key_float", 111.22)
        otel_span.set_attribute("key_int", 99)
        result_spans = self._process_spans([otel_span])

        self.assertEqual(len(result_spans), 1)
        self.assertEqual(len(result_spans[0].tags), 5)

        for tag in result_spans[0].tags:
            if tag.key == "key_bool":
                self.assertFalse(tag.bool_value)
            elif tag.key == "key_string":
                self.assertEqual(tag.string_value, "hello_world")
            elif tag.key == "key_float":
                self.assertEqual(tag.double_value, 111.22)
            elif tag.key == "key_int":
                self.assertEqual(tag.int_value, 99)
            elif tag.key == "span.kind":
                self.assertEqual(tag.string_value, "internal")
            else:
                raise Exception("unexpected value in tags")

    def test_events(self):
        """Test events are translated into logs."""
        base_time = 683647322 * 10 ** 9  # in ns
        event_attributes = {
            "annotation_bool": True,
            "annotation_string": "annotation_test",
            "annotation_float": 0.3,
            "annotation_int": 77,
        }

        event_timestamp = base_time + 50 * 10 ** 6
        event = trace.Event(
            name="event0",
            timestamp=event_timestamp,
            attributes=event_attributes,
        )
        otel_span = trace.Span(
            name=__name__, context=self._span_context, events=(event,),
        )
        result_spans = self._process_spans([otel_span])
        self.assertEqual(len(result_spans), 1)
        self.assertEqual(len(result_spans[0].logs), 1)
        log = result_spans[0].logs[0]
        self.assertEqual(
            log.timestamp.seconds, int(event_timestamp / 1000000000)
        )
        self.assertEqual(len(log.fields), 5)
        for tag in log.fields:
            if tag.key == "annotation_bool":
                self.assertTrue(tag.bool_value)
            elif tag.key == "annotation_string":
                self.assertEqual(tag.string_value, "annotation_test")
            elif tag.key == "annotation_float":
                self.assertEqual(tag.double_value, 0.3)
            elif tag.key == "annotation_int":
                self.assertEqual(tag.int_value, 77)
            elif tag.key == "message":
                self.assertEqual(tag.string_value, "event0")
            else:
                raise Exception("unexpected value in fields")

        self.assertEqual(
            log.timestamp.nanos, int(event_timestamp % 1000000000)
        )

    def test_resources(self):
        """Test resources."""
        resource = trace.Resource(labels={"test": "123", "other": "456"})
        otel_span = trace.Span(
            name=__name__, context=self._span_context, resource=resource,
        )

        otel_span.set_attribute("test", "789")
        otel_span.set_attribute("one-more", "000")
        result_spans = self._process_spans([otel_span])

        self.assertEqual(len(result_spans), 1)
        for tag in result_spans[0].tags:
            if tag.key == "test":
                self.assertEqual(tag.string_value, "789")
            elif tag.key == "other":
                self.assertEqual(tag.string_value, "456")
            elif tag.key == "one-more":
                self.assertEqual(tag.string_value, "000")
            elif tag.key == "span.kind":
                self.assertEqual(tag.string_value, "internal")
            else:
                raise Exception("unexpected value in tags")

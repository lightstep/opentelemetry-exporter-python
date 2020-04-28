import time
import unittest

from unittest import mock
from unittest.mock import Mock
from opentelemetry.ext.lightstep.metrics import LightstepMetricsExporter
from opentelemetry.ext.lightstep.protobuf.metrics_pb2 import IngestRequest
from opentelemetry.sdk import metrics
from opentelemetry.sdk.metrics.export import (
    MetricsExporter,
    MetricsExportResult,
    MetricRecord,
    Sequence,
)
from opentelemetry.sdk.metrics.export.aggregate import ObserverAggregator


def ingest_request_from_data(data):
    ingest_request = IngestRequest()
    try:
        ingest_request.ParseFromString(data)
    except:
        pass
    return ingest_request


def get_metric(name="name", desc="description"):
    meter = metrics.MeterProvider().get_meter(__name__)
    labels = (("host", "myhost"),)
    aggregator = ObserverAggregator()
    counter = metrics.Counter(name, desc, "bytes", int, meter, ("environment",),)

    return MetricRecord(aggregator, labels, counter)


class TestLightstepMetricsExporter(unittest.TestCase):
    def setUp(self):
        self.exporter = LightstepMetricsExporter(name="test_exporter", token="invalid")
        self.exporter._last_success = int(time.time()) - 5
        self.metrics = [get_metric("mem.available", "memory available")]

    @mock.patch("requests.post")
    def test_export_failed_not_retryable(self, mock_post):
        args = {"status_code": 404}
        mock_post.return_value = Mock(**args)
        result = self.exporter.export(self.metrics)
        self.assertEqual(result, MetricsExportResult.FAILURE)

    @mock.patch("requests.post")
    def test_request_headers(self, mock_post):
        """Test the token is passed from the constructor to the api request"""
        m = Mock()

        def side_effect(*args, **kwargs):
            m.headers = kwargs.get("headers")
            m.status_code = 200
            return m

        mock_post.side_effect = side_effect
        self.exporter.export(self.metrics)
        expected = {
            "Accept": "application/octet-stream",
            "Content-Type": "application/octet-stream",
            "Lightstep-Access-Token": "invalid",
        }
        mock_post.assert_called()

        self.assertEqual(len(m.headers), len(expected))
        self.assertEqual(m.headers, expected)

    @mock.patch("requests.post")
    def test_filters(self, mock_post):
        metric = [get_metric("cpu.user", "cpu metric")]
        self.exporter.export(metric)
        mock_post.assert_called_once()

        filtered_metric = [get_metric("invalid", "invalid metric")]
        self.exporter.export(filtered_metric)
        # ensure there have not been additional calls to post
        mock_post.assert_called_once()

    @mock.patch("requests.post")
    def test_idempotency_key(self, mock_post):
        m = Mock()

        def side_effect(*args, **kwargs):
            m.data = kwargs.get("data")
            m.headers = kwargs.get("headers")
            m.status_code = 200
            return m

        mock_post.side_effect = side_effect

        self.exporter.export(self.metrics)
        first = ingest_request_from_data(m.data)
        self.exporter.export(self.metrics)
        second = ingest_request_from_data(m.data)
        self.assertNotEqual(first.idempotency_key, second.idempotency_key)

    @mock.patch("requests.post")
    def test_metric_report_to_metric_point(self, mock_post):
        self.exporter._last_success = int(time.time()) - 5
        self.exporter._store["net.bytes_sent"] = 0
        metric = [get_metric("net.bytes_sent", "network metric")]
        m = Mock()

        def side_effect(*args, **kwargs):
            m.data = kwargs.get("data")
            m.headers = kwargs.get("headers")
            m.status_code = 200
            return m

        mock_post.side_effect = side_effect

        self.exporter.export(metric)
        ingest = ingest_request_from_data(m.data)
        self.assertEqual(len(ingest.points), 1)
        self.assertEqual(ingest.points[0].metric_name, "net.bytes_sent")
        self.assertEqual(ingest.points[0].duration.seconds, 5)

    @mock.patch("requests.post")
    def test_sending_failure_increases_duration(self, mock_post):
        # when reporting, if a report failed, duration should reflect this
        pass

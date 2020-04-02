import os
import platform
import random
import string

import backoff
import requests

from google.protobuf.duration_pb2 import Duration
from google.protobuf.timestamp_pb2 import Timestamp
from lightstep.collector_pb2 import KeyValue, Reporter

from opentelemetry.sdk.metrics.export import (
    MetricsExporter,
    MetricsExportResult,
    MetricRecord,
    Sequence,
)

from ..protobuf.metrics_pb2 import IngestRequest, MetricKind, MetricPoint

_COMPONENT_KEY = "lightstep.component_name"
_HOSTNAME_KEY = "lightstep.hostname"
_REPORTER_PLATFORM_KEY = "lightstep.reporter_platform"
_REPORTER_PLATFORM = "python"
_REPORTER_PLATFORM_VERSION_KEY = "lightstep.reporter_platform_version"
_REPORTER_VERSION_KEY = "lightstep.reporter_version"
_SERVICE_VERSION_KEY = "service.version"
_MAX_DURATION = 10 * 60  # ten minutes in seconds

METRICS_URL_ENV_VAR = "LS_METRICS_URL"
_DEFAULT_METRICS_URL = os.environ.get(
    METRICS_URL_ENV_VAR, "https://ingest.lightstep.com:443/metrics"
)
_DEFAULT_SERVICE_VERSION = "0.0.0"

DEFAULT_ACCEPT = "application/octet-stream"
DEFAULT_CONTENT_TYPE = "application/octet-stream"

# TODO: ensure this matches RCA metrics retry codes
_RETRYABLE = [408, 429, 500, 501, 502, 503, 504]


class MetricsReporter:
    """ HTTP client to send data to Lightstep """

    def __init__(
        self, token, url=_DEFAULT_METRICS_URL,
    ):
        self._headers = {
            "Accept": DEFAULT_ACCEPT,
            "Content-Type": DEFAULT_CONTENT_TYPE,
            "Lightstep-Access-Token": token,
        }
        self._url = url

    @backoff.on_exception(backoff.expo, Exception, max_time=5)
    def send(self, content, token=None):
        if token is not None:
            self._headers["Lightstep-Access-Token"] = token

        return requests.post(self._url, headers=self._headers, data=content)


class LightStepMetricsExporter(MetricsExporter):
    def _calc_value(self, key, value):
        if self._filters.get(key, MetricKind.GAUGE) == MetricKind.GAUGE:
            return value
        delta = value - self._store.get(key, 0)
        self._store[key] = value
        return delta

    def __init__(
        self,
        name,
        token,
        url=_DEFAULT_METRICS_URL,
        service_version=_DEFAULT_SERVICE_VERSION,
    ):
        self._store = {}
        # only capture metrics used in Lightstep
        self._filters = {
            "runtime.python.gc.count.gen0": MetricKind.GAUGE,
            "runtime.python.gc.count.gen1": MetricKind.GAUGE,
            "runtime.python.gc.count.gen2": MetricKind.GAUGE,
            "runtime.python.cpu.sys": MetricKind.COUNTER,
            "runtime.python.cpu.user": MetricKind.COUNTER,
            "runtime.python.mem.rss": MetricKind.GAUGE,
            "cpu.sys": MetricKind.COUNTER,
            "cpu.user": MetricKind.COUNTER,
            "cpu.total": MetricKind.COUNTER,
            "cpu.usage": MetricKind.COUNTER,
            "mem.available": MetricKind.GAUGE,
            "mem.total": MetricKind.GAUGE,
            "net.bytes_recv": MetricKind.COUNTER,
            "net.bytes_sent": MetricKind.COUNTER,
        }
        self._component_name = name
        self._service_version = service_version
        self._token = token
        self._client = MetricsReporter(token, url=url)
        self._reporter = Reporter(
            tags=[
                KeyValue(key=_HOSTNAME_KEY, string_value=os.uname()[1]),
                KeyValue(key=_REPORTER_PLATFORM_KEY, string_value=_REPORTER_PLATFORM),
                KeyValue(
                    key=_REPORTER_PLATFORM_VERSION_KEY,
                    string_value=platform.python_version(),
                ),
                KeyValue(key=_COMPONENT_KEY, string_value=self._component_name),
                KeyValue(key=_SERVICE_VERSION_KEY, string_value=self._service_version),
            ]
        )
        self._key_length = 30
        self._last_success = 0
        self._labels = [
            KeyValue(key=_HOSTNAME_KEY, string_value=os.uname()[1]),
            KeyValue(key=_COMPONENT_KEY, string_value=self._component_name),
            KeyValue(key=_SERVICE_VERSION_KEY, string_value=self._service_version),
        ]

    def _ingest_request(self):
        return IngestRequest(
            reporter=self._reporter, idempotency_key=self._generate_idempotency_key()
        )

    def _generate_idempotency_key(self):
        return "".join(
            random.choice(string.ascii_lowercase) for i in range(self._key_length)
        )

    def _converted_labels(self, labels):
        # converts labels from otel to ls format
        converted = []
        for key, val in labels:
            converted.append(KeyValue(key=key, string_value=val))
        return converted

    def _should_discard(self, duration):
        # intentionally throw away first report
        return self._last_success == 0 or duration.ToSeconds() > _MAX_DURATION

    def export(self, metric_records: Sequence[MetricRecord]) -> MetricsExportResult:
        """Exports a batch of telemetry data.

        Args:
            metric_records: A sequence of `MetricRecord` s. A `MetricRecord`
                contains the metric to be exported, the label set associated
                with that metric, as well as the aggregator used to export the
                current checkpointed value.

        Returns:
            The result of the export
        """
        ingest_request = self._ingest_request()
        start_time = Timestamp()
        start_time.GetCurrentTime()
        duration = Duration()
        duration.FromSeconds(start_time.ToSeconds() - self._last_success)

        for record in metric_records:
            if record.metric.name not in self._filters.keys():
                continue
            value = 0.0
            if record.aggregator.checkpoint.last is not None:
                value = float(
                    self._calc_value(
                        record.metric.name, record.aggregator.checkpoint.last
                    )
                )

            ingest_request.points.add(
                duration=duration,
                start=start_time,
                labels=self._converted_labels(record.labels) + self._labels,
                metric_name=record.metric.name,
                double_value=value,
                kind=self._filters.get(record.metric.name),
            )

        if len(ingest_request.points) == 0:
            return MetricsExportResult.SUCCESS

        if self._should_discard(duration):
            self._last_success = start_time.ToSeconds()
            return MetricsExportResult.SUCCESS

        resp = self._client.send(ingest_request.SerializeToString())
        if resp.status_code == requests.codes["ok"]:
            self._last_success = start_time.ToSeconds()
            return MetricsExportResult.SUCCESS
        if resp.status_code in _RETRYABLE:
            return MetricsExportResult.FAILED_RETRYABLE
        return MetricsExportResult.FAILED_NOT_RETRYABLE

    def shutdown(self) -> None:
        """Shuts down the exporter.

        Called when the SDK is shut down.
        """

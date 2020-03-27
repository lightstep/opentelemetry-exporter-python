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

from ..protobuf.metrics_pb2 import IngestRequest, MetricKind

_COMPONENT_KEY = "lightstep.component_name"
_HOSTNAME_KEY = "lightstep.hostname"
_REPORTER_PLATFORM_KEY = "lightstep.reporter_platform"
_REPORTER_PLATFORM_VERSION_KEY = "lightstep.reporter_platform_version"
_REPORTER_VERSION_KEY = "lightstep.reporter_version"

METRICS_URL_ENV_VAR = "LS_METRICS_URL"
DEFAULT_METRICS_URL = os.environ.get(
    METRICS_URL_ENV_VAR, "https://ingest.lightstep.com:443/metrics"
)

DEFAULT_ACCEPT = "application/octet-stream"
DEFAULT_CONTENT_TYPE = "application/octet-stream"

LS_PROCESS_CPU_TIME_SYS = "runtime.python.cpu.sys"
LS_PROCESS_CPU_TIME_USER = "runtime.python.cpu.user"
LS_PROCESS_MEM_RSS = "runtime.python.mem.rss"
LS_SYSTEM_CPU_TIME_SYS = "cpu.sys"
LS_SYSTEM_CPU_TIME_USER = "cpu.user"
LS_SYSTEM_CPU_TIME_TOTAL = "cpu.total"
LS_SYSTEM_CPU_TIME_USAGE = "cpu.usage"
LS_SYSTEM_MEM_AVAIL = "mem.available"
LS_SYSTEM_MEM_TOTAL = "mem.total"
LS_SYSTEM_NET_RECV = "net.bytes_recv"
LS_SYSTEM_NET_SENT = "net.bytes_sent"


class MetricsReporter:
    """ HTTP client to send data to Lightstep """

    def __init__(
        self, token, url=DEFAULT_METRICS_URL,
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
    def __init__(
        self, name, token, url=DEFAULT_METRICS_URL,
    ):
        self._component_name = name
        self._token = token
        self._client = MetricsReporter(token, url=url)
        self._reporter = Reporter(
            tags=[
                KeyValue(key=_HOSTNAME_KEY, string_value=os.uname()[1]),
                KeyValue(
                    key=_REPORTER_PLATFORM_KEY, string_value="opentelemetry-python"
                ),
                KeyValue(
                    key=_REPORTER_PLATFORM_VERSION_KEY,
                    string_value=platform.python_version(),
                ),
                KeyValue(key=_COMPONENT_KEY, string_value=self._component_name),
                # KeyValue(key=SERVICE_VERSION, string_value=self._service_version),
            ]
        )
        self._key_length = 30
        self._intervals = 1
        self._labels = [
            KeyValue(key=_HOSTNAME_KEY, string_value=os.uname()[1]),
            KeyValue(key=_COMPONENT_KEY, string_value=self._component_name),
            # KeyValue(key=SERVICE_VERSION, string_value=self._service_version),
        ]

    def _ingest_request(self):
        return IngestRequest(
            reporter=self._reporter, idempotency_key=self._generate_idempotency_key()
        )

        # for metric in self._runtime_metrics:
        #     metric_type = MetricKind.GAUGE
        #     if len(metric) == 3:
        #         key, value, metric_type = metric
        #     else:
        #         key, value = metric
        #     request.points.add(
        #         duration=duration,
        #         start=start_time,
        #         labels=self._labels,
        #         metric_name=key,
        #         double_value=value,
        #         kind=metric_type,
        #     )

    def _send(self, request):
        print(self._client.send(request))

    def _generate_idempotency_key(self):
        return "".join(
            random.choice(string.ascii_lowercase) for i in range(self._key_length)
        )

    def _converted_labels(self, labels):
        # TODO: convert labels into correct format
        return self._labels

    def export(self, metric_records: Sequence[MetricRecord]) -> "MetricsExportResult":
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
        duration.FromSeconds(30)
        for record in metric_records:
            # TODO: derive metric type from the record
            metric_type = MetricKind.GAUGE
            # TODO: figure out duration
            ingest_request.points.add(
                duration=duration,
                start=start_time,
                labels=self._converted_labels(record.label_set),
                metric_name=record.metric.name,
                double_value=float(record.aggregator.checkpoint.last),
                kind=metric_type,
            )

            print(
                '{}(data="{}", label_set="{}", value={})'.format(
                    type(self).__name__,
                    record.metric,
                    record.label_set.labels,
                    record.aggregator.checkpoint,
                )
            )
            print(ingest_request)

        self._send(ingest_request.SerializeToString())
        return MetricsExportResult.SUCCESS

    def shutdown(self) -> None:
        """Shuts down the exporter.

        Called when the SDK is shut down.
        """
        pass

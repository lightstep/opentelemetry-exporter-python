import os
import platform

from opentelemetry.ext.lightstep.protobuf.collector_pb2 import (
    KeyValue,
    Reporter,
)
from opentelemetry.ext.lightstep.version import __version__

SERVICE_NAME_KEY = "lightstep.component_name"
SERVICE_VERSION_KEY = "service.version"
HOSTNAME_KEY = "lightstep.hostname"
_REPORTER_VERSION_KEY = "lightstep.reporter_version"


def get_reporter(service_name, service_version, guid) -> Reporter:
    """Returns an instance of a `Reporter` with all the tags set
    Args:
        service_name: name of the service to instrument
        service_version: version of the service to instrument
        guid: used to identify the `Reporter`

    Returns:
        a configured `Reporter`
    """

    return Reporter(
        reporter_id=guid,
        tags=[
            KeyValue(key=HOSTNAME_KEY, string_value=os.uname().nodename),
            KeyValue(
                key="lightstep.reporter_platform",
                string_value="otel-ls-python",
            ),
            KeyValue(
                key="lightstep.reporter_platform_version",
                string_value=platform.python_version(),
            ),
            KeyValue(
                key="lightstep.tracer_platform", string_value="otel-ls-python"
            ),
            KeyValue(
                key="lightstep.tracer_platform_version",
                string_value=platform.python_version(),
            ),
            KeyValue(
                key="lightstep.tracer_version",
                string_value="{}".format(__version__),
            ),
            KeyValue(key=SERVICE_NAME_KEY, string_value=service_name),
            KeyValue(key=SERVICE_VERSION_KEY, string_value=service_version),
        ],
    )

import math
import os
import typing
from typing import Dict, Union

import grpc
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
from opentelemetry.ext.otlp.trace_exporter import OTLPSpanExporter
from opentelemetry.sdk.trace import Resource
from opentelemetry.sdk.trace import export as sdk

TRACING_URL_ENV_VAR = "LS_TRACING_URL"
_DEFAULT_TRACING_URL = os.environ.get(
    TRACING_URL_ENV_VAR, "https://ingest.lightstep.com:443/api/v2/report"
)


class LightstepSpanExporter(OTLPSpanExporter):
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
        if secure:
            super().__init__(
                endpoint="{}:{}".format(host, port),
                credentials=grpc.ssl_channel_credentials(),
                metadata=(("lightstep-access-token", token),),
            )
        else:
            super().__init__(
                endpoint="{}:{}".format(host, port),
                metadata=(("lightstep-access-token", token)),
            )

        trace_api.get_tracer_provider().resource = Resource(
            {
                "service.name": name,
                "service.version": service_version,
                "instrument.name": "python",
                "instrument.version": __version__,
            }
        )


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

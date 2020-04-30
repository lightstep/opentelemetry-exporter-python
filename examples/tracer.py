#!/usr/bin/env python3
import os

from opentelemetry import trace
from opentelemetry.ext.lightstep import LightstepSpanExporter
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import BatchExportSpanProcessor

# configure the LightStepSpanExporter as our exporter
exporter = LightstepSpanExporter(
    name=os.getenv("LIGHTSTEP_SERVICE_NAME", "test-service-name"),
    token=os.getenv("LIGHTSTEP_ACCESS_TOKEN", ""),
    host="ingest.staging.lightstep.com",
    service_version=os.getenv("LIGHTSTEP_SERVICE_VERSION", "0.0.1"),
)
span_processor = BatchExportSpanProcessor(exporter)


trace.set_tracer_provider(TracerProvider())
trace.get_tracer_provider().add_span_processor(span_processor)

tracer = trace.get_tracer("lightstep-exporter-example")
with tracer.start_as_current_span("foo") as span:
    span.set_attribute("platform", "osx")
    span.set_attribute("version", "1.2.3")
    span.add_event("event in foo", {"name": "foo1"})
    with tracer.start_as_current_span("bar"):
        with tracer.start_as_current_span("baz") as s:
            s.set_attribute("test", "bah")
            print("Hello world")

span_processor.shutdown()

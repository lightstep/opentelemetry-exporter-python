#!/usr/bin/env python3
import os

from opentelemetry import trace
from opentelemetry.sdk.trace import TracerSource
from opentelemetry.sdk.trace.export import BatchExportSpanProcessor
from opentelemetry.ext.lightstep import LightStepSpanExporter

trace.set_preferred_tracer_source_implementation(lambda T: TracerSource())
# configure the LightStepSpanExporter as our exporter
exporter = LightStepSpanExporter(
    name="test-service", token=os.getenv("LIGHTSTEP_TOKEN", ""), verbosity=5
)
span_processor = BatchExportSpanProcessor(exporter)
trace.tracer_source().add_span_processor(span_processor)

tracer = trace.get_tracer("lightstep-exporter-example")
with tracer.start_as_current_span("foo"):
    with tracer.start_as_current_span("bar"):
        with tracer.start_as_current_span("baz") as s:
            s.set_attribute("test", "bah")
            print("Hello world")

span_processor.shutdown()

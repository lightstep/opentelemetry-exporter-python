#!/usr/bin/env python3
import os

from opentelemetry import trace
from opentelemetry.context import Context
from opentelemetry.sdk.trace import Tracer
from opentelemetry.sdk.trace.export import BatchExportSpanProcessor
from opentelemetry.ext.lightstep import LightStepSpanExporter

trace.set_preferred_tracer_implementation(lambda T: Tracer())
tracer = trace.tracer()
# configure the LightStepSpanExporter as our exporter
exporter = LightStepSpanExporter(
    name="test-service",
    token=(os.getenv("LIGHTSTEP_TOKEN") or ""),
    host="localhost",
    port=8360,
    encryption="none",
    verbosity=0,
)
span_processor = BatchExportSpanProcessor(exporter)
tracer.add_span_processor(span_processor)
with tracer.start_as_current_span("foo"):
    with tracer.start_as_current_span("bar"):
        with tracer.start_as_current_span("baz") as s:
            s.set_attribute("test", "bah")
            print(Context)

span_processor.shutdown()

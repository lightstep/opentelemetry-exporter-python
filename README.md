![build status](https://github.com/lightstep/opentelemetry-exporter-python/workflows/build/badge.svg) [![PyPI version](https://badge.fury.io/py/opentelemetry-ext-lightstep.svg)](https://badge.fury.io/py/opentelemetry-ext-lightstep)
# Lightstep OpenTelemetry Python Exporter

This is the Lightstep exporter for OpenTelemetry

### Install

```bash
pip install opentelemetry-ext-lightstep
```

### Configure

```python
from opentelemetry import trace
from opentelemetry.ext.lightstep import LightStepSpanExporter
from opentelemetry.sdk.trace.export import BatchExportSpanProcessor

exporter = LightstepSpanExporter(
    name="test-service",
    token=<PROJECT_ACCESS_TOKEN>,
    host=<SATELLITE_URL>,
    port=<SATELLITE_PORT>,
    service_version="1.2.3",
)
span_processor = BatchExportSpanProcessor(exporter)
trace.get_tracer_provider().add_span_processor(span_processor)
```

### Examples

See the [examples](https://github.com/lightstep/opentelemetry-exporter-python/tree/master/examples) directory.

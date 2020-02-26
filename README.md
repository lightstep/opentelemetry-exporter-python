# LightStep OpenTelemetry Python Exporter
This is an exporter for opentelemetry-python

### Install

```bash
pip install opentelemetry-ext-lightstep
```

### Initialize

```python
exporter = LightStepSpanExporter(
    name="test-service",
    token=<PROJECT_ACCESS_TOKEN>,
    host=<SATELLITE_URL>,
    port=<SATELLITE_PORT>,
)
span_processor = BatchExportSpanProcessor(exporter)
tracer.add_span_processor(span_processor)
```

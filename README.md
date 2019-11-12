# LightStep OpenTelemetry Python Exporter
This is an experimental exporter for opentelemetry-python

Install
```bash
git clone https://github.com/lightstep/opentelemetry-exporter-python.git && cd opentelemetry-exporter-python
pip install .
```

Initialize
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

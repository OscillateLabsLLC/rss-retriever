"""OpenTelemetry configuration and setup."""

import logging
import os
import sys
from typing import Any

from opentelemetry import trace
from opentelemetry.instrumentation.requests import RequestsInstrumentor
from opentelemetry.sdk.resources import Resource
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import BatchSpanProcessor, ConsoleSpanExporter
from pythonjsonlogger.json import JsonFormatter

from rss_retriever.config import get_env


def setup_telemetry(service_name: str = "rss-retriever") -> None:
    """Set up OpenTelemetry tracing and JSON logging.

    Requires the ``otel`` extra. This installs a global tracer provider and should be
    called from an application entry point, never from library code.

    Configuration comes from the standard OpenTelemetry environment variables:

    - ``OTEL_SERVICE_NAME``: override the service name (default: rss-retriever)
    - ``OTEL_EXPORTER``: ``otlp`` (default) or ``console`` for local debugging
    - ``OTEL_EXPORTER_OTLP_ENDPOINT``: collector endpoint. For OTLP/HTTP include the
      full path, e.g. ``http://localhost:6006/v1/traces``; for gRPC use
      ``http://localhost:4317``.
    - ``OTEL_EXPORTER_OTLP_PROTOCOL``: ``http/protobuf`` (default) or ``grpc``
    - ``OTEL_EXPORTER_OTLP_HEADERS``: additional headers as comma-separated key=value

    Args:
        service_name (str, optional): Name of the service for telemetry.
            Can be overridden by OTEL_SERVICE_NAME env var.
            Defaults to "rss-retriever".
    """
    service_name = os.getenv("OTEL_SERVICE_NAME", service_name)
    resource = Resource.create({"service.name": service_name})
    tracer_provider = TracerProvider(resource=resource)

    exporter_type = os.getenv("OTEL_EXPORTER", "otlp").lower()
    if exporter_type == "console":
        tracer_provider.add_span_processor(BatchSpanProcessor(ConsoleSpanExporter()))
    else:
        tracer_provider.add_span_processor(BatchSpanProcessor(_build_otlp_exporter()))

    trace.set_tracer_provider(tracer_provider)

    RequestsInstrumentor().instrument()
    setup_json_logging()


def _build_otlp_exporter():
    """Construct an OTLP span exporter honouring OTEL_EXPORTER_OTLP_PROTOCOL.

    Phoenix's ``phoenix.otel.register`` is deliberately not used here: it ignores
    OTEL_EXPORTER_OTLP_ENDPOINT and derives its own collector address, which silently
    sends HTTP/protobuf traffic to the gRPC port and makes every export time out.
    Building the exporter directly keeps the standard OTEL variables authoritative,
    and Phoenix ingests plain OTLP on either transport.
    """
    protocol = os.getenv("OTEL_EXPORTER_OTLP_PROTOCOL", "http/protobuf").lower()
    endpoint = os.getenv("OTEL_EXPORTER_OTLP_ENDPOINT")

    if protocol == "grpc":
        from opentelemetry.exporter.otlp.proto.grpc.trace_exporter import OTLPSpanExporter as GRPCExporter

        return GRPCExporter(endpoint=endpoint) if endpoint else GRPCExporter()

    from opentelemetry.exporter.otlp.proto.http.trace_exporter import OTLPSpanExporter as HTTPExporter

    return HTTPExporter(endpoint=endpoint) if endpoint else HTTPExporter()


def setup_json_logging() -> None:
    """Configure JSON format logging."""
    # Set root logger level from environment or default to INFO
    log_level = get_env("LOG_LEVEL", "INFO").upper()
    root_logger = logging.getLogger()
    root_logger.setLevel(log_level)

    # Configure JSON stdout handler
    json_handler = logging.StreamHandler(sys.stdout)
    json_formatter = CustomJsonFormatter("%(timestamp)s %(level)s %(name)s %(message)s")
    json_handler.setFormatter(json_formatter)

    # Remove existing handlers and add JSON handler
    root_logger.handlers.clear()
    root_logger.addHandler(json_handler)

    # Log initial setup
    root_logger.info("Logging system initialized", extra={"log_level": log_level})


class CustomJsonFormatter(JsonFormatter):
    """Custom JSON formatter with additional fields."""

    def add_fields(
        self,
        log_record: dict[str, Any],
        record: logging.LogRecord,
        message_dict: dict[str, Any],
    ) -> None:
        """Add custom fields to the log record.

        Args:
            log_record (dict[str, Any]): The log record to modify
            record (logging.LogRecord): The original log record
            message_dict (dict[str, Any]): Additional message dictionary
        """
        super().add_fields(log_record, record, message_dict)

        # Rename some fields
        log_record["level"] = record.levelname
        log_record["timestamp"] = self.formatTime(record)

        # Add trace context if available
        span_context = trace.get_current_span().get_span_context()
        if span_context and span_context.is_valid:
            log_record["trace_id"] = format(span_context.trace_id, "032x")
            log_record["span_id"] = format(span_context.span_id, "016x")

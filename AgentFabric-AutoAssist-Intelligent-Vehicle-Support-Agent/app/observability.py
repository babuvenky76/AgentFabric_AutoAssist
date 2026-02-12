"""
Observability Module - Structured Logging and Metrics Collection
================================================================

This module provides enterprise-grade observability capabilities for the AutoAssist
application, including structured JSON logging and Prometheus-compatible metrics.

Components:
    - JSONFormatter: Formats logs as structured JSON for easy parsing
    - RequestTracker: Decorator for automatic request tracking and timing
    - MetricsCollector: Collects and exposes metrics in Prometheus format

Key Features:
    - Structured JSON logging with ISO timestamps
    - Automatic request ID generation for distributed tracing
    - Latency tracking for performance monitoring
    - Prometheus-compatible metrics endpoint
    - Success rate and error rate tracking
    - Zero-dependency metrics collection (no Prometheus client library needed)

Metrics Exposed:
    - autoassist_requests_total: Total number of requests (counter)
    - autoassist_errors_total: Total number of errors (counter)
    - autoassist_request_latency_ms: Average request latency (gauge)
    - autoassist_success_rate: Success rate percentage (gauge)

Integration:
    - Logs are written to stdout in JSON format (Docker-friendly)
    - Metrics are exposed via /metrics/prometheus endpoint
    - Prometheus scrapes metrics every 15 seconds
    - Grafana visualizes metrics via pre-configured dashboards

Usage Example:
    ```python
    # Setup logging
    logger = setup_logging(app_name="AutoAssist", log_level="INFO")
    
    # Track requests
    tracker = RequestTracker(logger)
    
    @tracker
    def my_endpoint():
        # Automatically tracked with request_id and latency
        return {"status": "ok"}
    
    # Record metrics
    metrics.record_request(latency_ms=123.45, error=False)
    
    # Export metrics
    prometheus_text = metrics.get_prometheus_format()
    ```

Production Notes:
    - Logs are JSON-formatted for easy ingestion by log aggregators (ELK, Splunk)
    - Metrics are stored in-memory (resets on restart)
    - For production, consider persistent metrics storage (Redis, InfluxDB)
    - Request IDs enable distributed tracing across microservices

Author: AutoAssist Development Team
License: MIT
"""

import json
import logging
import time
import uuid
from typing import Any, Callable, Optional
from functools import wraps
from datetime import datetime
from collections import defaultdict


# ============================================================================
# STRUCTURED JSON LOGGING
# ============================================================================
class JSONFormatter(logging.Formatter):
    """
    JSON Formatter for Structured Logging
    
    Converts Python log records into structured JSON format for easy parsing
    by log aggregation systems (ELK Stack, Splunk, CloudWatch, etc.).
    
    JSON Structure:
        {
            "timestamp": "2026-02-12T10:30:45.123456",  # ISO 8601 UTC
            "level": "INFO",                             # Log level
            "logger": "AutoAssist",                      # Logger name
            "message": "Request completed",              # Log message
            "module": "main",                            # Python module
            "request_id": "uuid-here",                   # Optional: Request ID
            "latency_ms": 123.45,                        # Optional: Latency
            "exception": "Traceback..."                  # Optional: Exception
        }
    
    Benefits:
        - Machine-readable logs (easy to parse and query)
        - Consistent structure across all log entries
        - Supports custom fields via LogRecord attributes
        - Compatible with log aggregation tools
        - Enables powerful log analytics and alerting
    
    Example:
        ```python
        handler = logging.StreamHandler()
        handler.setFormatter(JSONFormatter())
        logger.addHandler(handler)
        
        # Basic log
        logger.info("User logged in")
        
        # Log with custom fields
        logger.info("Request completed", extra={
            "request_id": "abc-123",
            "latency_ms": 45.67
        })
        ```
    """
    
    def format(self, record: logging.LogRecord) -> str:
        """
        Format log record as JSON string.
        
        Args:
            record (logging.LogRecord): Python log record to format
        
        Returns:
            str: JSON-formatted log entry as a single-line string
        
        Custom Fields:
            - request_id: Unique identifier for request tracing
            - latency_ms: Request processing time in milliseconds
            - Any other attributes added via extra={} parameter
        """
        # Step 1: Build base log structure with standard fields
        log_data = {
            "timestamp": datetime.utcnow().isoformat(),  # ISO 8601 format
            "level": record.levelname,                    # INFO, WARNING, ERROR, etc.
            "logger": record.name,                        # Logger name (e.g., "AutoAssist")
            "message": record.getMessage(),               # Formatted log message
            "module": record.module,                      # Python module name
        }
        
        # Step 2: Add exception traceback if present
        if record.exc_info:
            log_data["exception"] = self.formatException(record.exc_info)
        
        # Step 3: Add custom request_id field if present (for distributed tracing)
        if hasattr(record, "request_id"):
            log_data["request_id"] = record.request_id
        
        # Step 4: Add custom latency_ms field if present (for performance monitoring)
        if hasattr(record, "latency_ms"):
            log_data["latency_ms"] = record.latency_ms
        
        # Step 5: Serialize to JSON (single line for easy log parsing)
        return json.dumps(log_data)


def setup_logging(app_name: str = "AutoAssist", log_level: str = "INFO"):
    """
    Setup structured JSON logging for the application.
    
    Configures a logger with JSON formatting that writes to stdout.
    This is Docker-friendly and works well with container orchestration.
    
    Args:
        app_name (str): Name of the application (used as logger name)
        log_level (str): Logging level (DEBUG, INFO, WARNING, ERROR, CRITICAL)
    
    Returns:
        logging.Logger: Configured logger instance with JSON formatting
    
    Log Levels:
        - DEBUG: Detailed diagnostic information (verbose)
        - INFO: General informational messages (default)
        - WARNING: Warning messages for potentially harmful situations
        - ERROR: Error messages for serious problems
        - CRITICAL: Critical messages for very serious errors
    
    Docker Integration:
        - Logs to stdout (captured by Docker logs)
        - JSON format enables easy parsing by log drivers
        - Compatible with Docker logging drivers (json-file, syslog, etc.)
    
    Example:
        ```python
        logger = setup_logging(app_name="AutoAssist", log_level="INFO")
        logger.info("Application started")
        logger.error("Database connection failed", extra={"db": "postgres"})
        ```
    """
    # Step 1: Get or create logger with specified name
    logger = logging.getLogger(app_name)
    
    # Step 2: Set minimum log level (messages below this level are ignored)
    logger.setLevel(getattr(logging, log_level))
    
    # Step 3: Create handler that writes to stdout (Docker-friendly)
    handler = logging.StreamHandler()
    
    # Step 4: Attach JSON formatter to handler
    handler.setFormatter(JSONFormatter())
    
    # Step 5: Attach handler to logger
    logger.addHandler(handler)
    
    return logger


# ============================================================================
# REQUEST TRACKING AND TIMING
# ============================================================================
class RequestTracker:
    """
    Decorator for Automatic Request Tracking and Timing
    
    Wraps functions to automatically track execution time, generate request IDs,
    and log success/failure with structured data. Useful for API endpoints.
    
    Features:
        - Automatic request ID generation (UUID v4)
        - Precise latency measurement in milliseconds
        - Automatic success/error logging
        - Exception propagation (doesn't swallow errors)
        - Structured log output with request_id and latency_ms
    
    Use Cases:
        - API endpoint monitoring
        - Database query timing
        - External service call tracking
        - Performance bottleneck identification
    
    Example:
        ```python
        logger = setup_logging()
        tracker = RequestTracker(logger)
        
        @tracker
        def process_order(order_id: str):
            # Function is automatically tracked
            # Logs: request_id, latency_ms, status
            return {"order_id": order_id, "status": "processed"}
        
        # Logs on success:
        # {"timestamp": "...", "message": "Request process_order completed",
        #  "request_id": "abc-123", "latency_ms": 45.67, "status": "success"}
        
        # Logs on error:
        # {"timestamp": "...", "message": "Request process_order failed: ...",
        #  "request_id": "abc-123", "latency_ms": 12.34, "status": "error"}
        ```
    """
    
    def __init__(self, logger: logging.Logger):
        """
        Initialize request tracker with logger.
        
        Args:
            logger (logging.Logger): Logger instance for writing tracking logs
        """
        self.logger = logger
    
    def __call__(self, func: Callable) -> Callable:
        """
        Wrap function with request tracking logic.
        
        Args:
            func (Callable): Function to wrap with tracking
        
        Returns:
            Callable: Wrapped function with automatic tracking
        """
        @wraps(func)  # Preserves original function metadata (__name__, __doc__, etc.)
        def wrapper(*args, **kwargs):
            # Step 1: Generate unique request ID for distributed tracing
            request_id = str(uuid.uuid4())
            
            # Step 2: Record start time for latency calculation
            start_time = time.time()
            
            try:
                # Step 3: Execute the wrapped function
                result = func(*args, **kwargs)
                
                # Step 4: Calculate latency in milliseconds
                latency_ms = (time.time() - start_time) * 1000
                
                # Step 5: Log successful completion with metrics
                log_record = {
                    "request_id": request_id,
                    "latency_ms": latency_ms,
                    "status": "success"
                }
                
                self.logger.info(
                    f"Request {func.__name__} completed",
                    extra=log_record
                )
                
                return result
                
            except Exception as e:
                # Step 6: Log error with metrics (still calculate latency)
                latency_ms = (time.time() - start_time) * 1000
                self.logger.error(
                    f"Request {func.__name__} failed: {str(e)}",
                    extra={
                        "request_id": request_id,
                        "latency_ms": latency_ms,
                        "status": "error"
                    }
                )
                # Re-raise exception (don't swallow errors)
                raise
        
        return wrapper


# ============================================================================
# PROMETHEUS-COMPATIBLE METRICS COLLECTION
# ============================================================================
class MetricsCollector:
    """
    Metrics Collector with Prometheus-Compatible Output
    
    Collects application metrics in-memory and exposes them in Prometheus text format.
    This is a lightweight alternative to the official Prometheus client library.
    
    Metrics Tracked:
        - request_count: Total number of requests processed (counter)
        - error_count: Total number of failed requests (counter)
        - total_latency: Cumulative latency across all requests (internal)
        - request_latencies: List of individual request latencies (for future percentile calculations)
    
    Derived Metrics:
        - avg_latency_ms: Average request latency in milliseconds
        - success_rate: Percentage of successful requests (0-100)
    
    Prometheus Integration:
        - Metrics exposed via /metrics/prometheus endpoint
        - Prometheus scrapes endpoint every 15 seconds (configurable)
        - Grafana visualizes metrics via pre-configured dashboards
    
    Limitations:
        - Metrics stored in-memory (reset on application restart)
        - No histogram or percentile support (p50, p95, p99)
        - Single-instance only (no distributed metrics aggregation)
    
    Production Considerations:
        - For production, consider using official prometheus_client library
        - For distributed systems, use external metrics storage (Redis, InfluxDB)
        - For percentiles, implement histogram buckets or use summary metrics
    
    Example:
        ```python
        # Record successful request
        metrics.record_request(latency_ms=123.45, error=False)
        
        # Record failed request
        metrics.record_request(latency_ms=45.67, error=True)
        
        # Get metrics as JSON
        snapshot = metrics.get_metrics()
        # {"total_requests": 2, "total_errors": 1, "avg_latency_ms": 84.56, "success_rate": 50.0}
        
        # Get metrics in Prometheus format
        prometheus_text = metrics.get_prometheus_format()
        # autoassist_requests_total 2
        # autoassist_errors_total 1
        # ...
        ```
    """
    
    def __init__(self):
        """
        Initialize metrics collector with zero values.
        
        All metrics start at zero and increment as requests are processed.
        """
        self.request_count = 0        # Total requests processed
        self.error_count = 0          # Total errors encountered
        self.total_latency = 0.0      # Cumulative latency (for average calculation)
        self.request_latencies = []   # Individual latencies (for future percentile support)
    
    def record_request(self, latency_ms: float, error: bool = False):
        """
        Record a request metric.
        
        Call this method after each request completes to track metrics.
        
        Args:
            latency_ms (float): Request processing time in milliseconds
            error (bool): Whether the request failed (default: False)
        
        Thread Safety:
            This implementation is NOT thread-safe. For production use with
            multiple workers, consider using atomic operations or locks.
        
        Example:
            ```python
            start = time.time()
            try:
                process_request()
                latency = (time.time() - start) * 1000
                metrics.record_request(latency_ms=latency, error=False)
            except Exception:
                latency = (time.time() - start) * 1000
                metrics.record_request(latency_ms=latency, error=True)
            ```
        """
        # Increment total request counter
        self.request_count += 1
        
        # Add latency to cumulative total (for average calculation)
        self.total_latency += latency_ms
        
        # Store individual latency (for future percentile calculations)
        self.request_latencies.append(latency_ms)
        
        # Increment error counter if request failed
        if error:
            self.error_count += 1
    
    def get_metrics(self) -> dict:
        """
        Get current metrics snapshot as dictionary.
        
        Returns:
            dict: Metrics snapshot with keys:
                - total_requests (int): Total requests processed
                - total_errors (int): Total errors encountered
                - avg_latency_ms (float): Average latency in milliseconds
                - success_rate (float): Success rate percentage (0-100)
        
        Calculations:
            - avg_latency_ms = total_latency / max(request_count, 1)
            - success_rate = ((request_count - error_count) / request_count) * 100
        
        Edge Cases:
            - If no requests processed, avg_latency_ms = 0.0, success_rate = 0.0
            - Division by zero prevented using max(request_count, 1)
        """
        # Calculate average latency (avoid division by zero)
        avg_latency = self.total_latency / max(self.request_count, 1)
        
        # Calculate success rate as percentage (0-100)
        success_rate = ((self.request_count - self.error_count) / max(self.request_count, 1)) * 100 if self.request_count > 0 else 0
        
        return {
            "total_requests": self.request_count,
            "total_errors": self.error_count,
            "avg_latency_ms": round(avg_latency, 2),  # Round to 2 decimal places
            "success_rate": round(success_rate, 2),   # Round to 2 decimal places
        }
    
    def get_prometheus_format(self) -> str:
        """
        Get metrics in Prometheus text exposition format.
        
        Returns:
            str: Metrics in Prometheus text format (multi-line string)
        
        Prometheus Text Format:
            # HELP <metric_name> <description>
            # TYPE <metric_name> <type>
            <metric_name> <value>
        
        Metric Types:
            - counter: Monotonically increasing value (requests_total, errors_total)
            - gauge: Value that can go up or down (latency_ms, success_rate)
        
        Example Output:
            ```
            # HELP autoassist_requests_total Total number of requests
            # TYPE autoassist_requests_total counter
            autoassist_requests_total 42
            
            # HELP autoassist_errors_total Total number of errors
            # TYPE autoassist_errors_total counter
            autoassist_errors_total 3
            
            # HELP autoassist_request_latency_ms Average request latency in milliseconds
            # TYPE autoassist_request_latency_ms gauge
            autoassist_request_latency_ms 123.45
            
            # HELP autoassist_success_rate Success rate percentage
            # TYPE autoassist_success_rate gauge
            autoassist_success_rate 92.86
            ```
        
        Integration:
            This format is scraped by Prometheus via /metrics/prometheus endpoint.
            Prometheus stores time-series data and Grafana visualizes it.
        """
        # Get current metrics snapshot
        metrics = self.get_metrics()
        
        # Build Prometheus text format output
        output = []
        
        # Metric 1: Total requests (counter)
        output.append("# HELP autoassist_requests_total Total number of requests")
        output.append("# TYPE autoassist_requests_total counter")
        output.append(f"autoassist_requests_total {metrics['total_requests']}")
        
        # Metric 2: Total errors (counter)
        output.append("# HELP autoassist_errors_total Total number of errors")
        output.append("# TYPE autoassist_errors_total counter")
        output.append(f"autoassist_errors_total {metrics['total_errors']}")
        
        # Metric 3: Average latency (gauge)
        output.append("# HELP autoassist_request_latency_ms Average request latency in milliseconds")
        output.append("# TYPE autoassist_request_latency_ms gauge")
        output.append(f"autoassist_request_latency_ms {metrics['avg_latency_ms']}")
        
        # Metric 4: Success rate (gauge)
        output.append("# HELP autoassist_success_rate Success rate percentage")
        output.append("# TYPE autoassist_success_rate gauge")
        output.append(f"autoassist_success_rate {metrics['success_rate']}")
        
        # Join with newlines (Prometheus expects line-delimited format)
        return "\n".join(output)


# ============================================================================
# GLOBAL METRICS INSTANCE
# ============================================================================

# Global singleton instance for application-wide metrics collection
# Import this instance in other modules: from app.observability import metrics
metrics = MetricsCollector()
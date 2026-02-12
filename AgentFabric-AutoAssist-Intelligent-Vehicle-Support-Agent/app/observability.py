"""
Observability module for AutoAssist
Handles logging, metrics, and tracing
"""

import json
import logging
import time
import uuid
from typing import Any, Callable, Optional
from functools import wraps
from datetime import datetime
from collections import defaultdict

# Structured logging setup
class JSONFormatter(logging.Formatter):
    """JSON formatter for structured logging"""
    
    def format(self, record: logging.LogRecord) -> str:
        log_data = {
            "timestamp": datetime.utcnow().isoformat(),
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
            "module": record.module,
        }
        
        if record.exc_info:
            log_data["exception"] = self.formatException(record.exc_info)
        
        if hasattr(record, "request_id"):
            log_data["request_id"] = record.request_id
        
        if hasattr(record, "latency_ms"):
            log_data["latency_ms"] = record.latency_ms
        
        return json.dumps(log_data)


def setup_logging(app_name: str = "AutoAssist", log_level: str = "INFO"):
    """Setup structured logging for the application"""
    logger = logging.getLogger(app_name)
    logger.setLevel(getattr(logging, log_level))
    
    handler = logging.StreamHandler()
    handler.setFormatter(JSONFormatter())
    logger.addHandler(handler)
    
    return logger


# Request tracking
class RequestTracker:
    """Decorator for tracking request latency and errors"""
    
    def __init__(self, logger: logging.Logger):
        self.logger = logger
    
    def __call__(self, func: Callable) -> Callable:
        @wraps(func)
        def wrapper(*args, **kwargs):
            request_id = str(uuid.uuid4())
            start_time = time.time()
            
            try:
                result = func(*args, **kwargs)
                latency_ms = (time.time() - start_time) * 1000
                
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
                latency_ms = (time.time() - start_time) * 1000
                self.logger.error(
                    f"Request {func.__name__} failed: {str(e)}",
                    extra={
                        "request_id": request_id,
                        "latency_ms": latency_ms,
                        "status": "error"
                    }
                )
                raise
        
        return wrapper


# Prometheus-compatible metrics
class MetricsCollector:
    """Metrics collector with Prometheus-compatible output"""
    
    def __init__(self):
        self.request_count = 0
        self.error_count = 0
        self.total_latency = 0.0
        self.request_latencies = []
    
    def record_request(self, latency_ms: float, error: bool = False):
        """Record a request metric"""
        self.request_count += 1
        self.total_latency += latency_ms
        self.request_latencies.append(latency_ms)
        
        if error:
            self.error_count += 1
    
    def get_metrics(self) -> dict:
        """Get current metrics snapshot"""
        avg_latency = self.total_latency / max(self.request_count, 1)
        success_rate = ((self.request_count - self.error_count) / max(self.request_count, 1)) * 100 if self.request_count > 0 else 0
        
        return {
            "total_requests": self.request_count,
            "total_errors": self.error_count,
            "avg_latency_ms": round(avg_latency, 2),
            "success_rate": round(success_rate, 2),
        }
    
    def get_prometheus_format(self) -> str:
        """Get metrics in Prometheus text format"""
        metrics = self.get_metrics()
        
        output = []
        output.append("# HELP autoassist_requests_total Total number of requests")
        output.append("# TYPE autoassist_requests_total counter")
        output.append(f"autoassist_requests_total {metrics['total_requests']}")
        
        output.append("# HELP autoassist_errors_total Total number of errors")
        output.append("# TYPE autoassist_errors_total counter")
        output.append(f"autoassist_errors_total {metrics['total_errors']}")
        
        output.append("# HELP autoassist_request_latency_ms Average request latency in milliseconds")
        output.append("# TYPE autoassist_request_latency_ms gauge")
        output.append(f"autoassist_request_latency_ms {metrics['avg_latency_ms']}")
        
        output.append("# HELP autoassist_success_rate Success rate percentage")
        output.append("# TYPE autoassist_success_rate gauge")
        output.append(f"autoassist_success_rate {metrics['success_rate']}")
        
        return "\n".join(output)

# Global metrics instance
metrics = MetricsCollector()
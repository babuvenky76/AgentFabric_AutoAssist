"""
FastAPI Application for AutoAssist - Main Entry Point

This module serves as the main entry point for the AutoAssist API service.
It provides RESTful endpoints for vehicle support queries with full observability.

Endpoints:
    - POST /chat: Process vehicle support queries through LLM
    - GET /health: Health check for container orchestration
    - GET /metrics: JSON-formatted metrics for monitoring
    - GET /metrics/prometheus: Prometheus-compatible metrics endpoint
    - GET /: Root endpoint with service information

Security Features:
    - CORS restrictions (whitelist-only origins)
    - Input validation with regex patterns
    - Error message sanitization
    - Request/response logging with request IDs

Author: Babu Srinivasan
Project: AgentFabric AutoAssist
"""

from fastapi import FastAPI, HTTPException
from fastapi.responses import JSONResponse
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field
from typing import Optional
import logging
import json
import time

from app.config import AppConfig, config
from app.agent import AutoAssistAgent
from app.observability import setup_logging, metrics


# ============================================================================
# APPLICATION INITIALIZATION
# ============================================================================

# Setup structured logging with JSON format
logger = setup_logging(config.app_name, config.log_level)

# Initialize FastAPI application with metadata
app = FastAPI(
    title=config.app_name,
    description="Intelligent Vehicle Support Agent - Production-Grade LLM Application",
    version="0.1.0",
    docs_url="/docs",  # Swagger UI
    redoc_url="/redoc",  # ReDoc UI
)

# ============================================================================
# SECURITY: CORS MIDDLEWARE CONFIGURATION
# ============================================================================
# PRODUCTION NOTE: Remove "*" and add only trusted domains
# Example: ["https://yourdomain.com", "https://app.yourdomain.com"]

# Add CORS middleware - PRODUCTION: Restrict origins
# ============================================================================
# SECURITY: CORS MIDDLEWARE CONFIGURATION
# ============================================================================
# PRODUCTION NOTE: Remove "*" and add only trusted domains
# Example: ["https://yourdomain.com", "https://app.yourdomain.com"]

app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:3000",  # Frontend UI
        "http://localhost:3001",  # Grafana Dashboard
        # TODO: Add production domains here
    ],
    allow_credentials=True,
    allow_methods=["GET", "POST"],  # Restrict to only needed methods
    allow_headers=["Content-Type", "Authorization"],  # Restrict headers
    max_age=600,  # Cache preflight requests for 10 minutes
)

# ============================================================================
# AGENT INITIALIZATION
# ============================================================================

# Initialize the AutoAssist agent with configuration
# This handles LLM communication and prompt management
agent = AutoAssistAgent(config)


# ============================================================================
# REQUEST/RESPONSE MODELS (Pydantic Schemas)
# ============================================================================

class ChatRequest(BaseModel):
    """
    Chat request schema with strict validation.
    
    Attributes:
        query: User's vehicle support question (1-1000 chars)
        session_id: Optional session identifier for tracking (max 100 chars)
    
    Security:
        - Regex validation prevents injection attacks
        - Length limits prevent DoS attacks
    """
    query: str = Field(
        ..., 
        min_length=1, 
        max_length=1000, 
        description="User query",
        pattern=r'^[\w\s\?\.\,\!\-\'\"\(\)]+$'  # Alphanumeric + basic punctuation only
    )
    session_id: Optional[str] = Field(
        None, 
        description="Optional session ID for tracking",
        max_length=100,
        pattern=r'^[a-zA-Z0-9\-_]+$'  # Alphanumeric, hyphens, underscores only
    )


class ChatResponse(BaseModel):
    """
    Chat response schema.
    
    Attributes:
        status: Response status ("success" or "error")
        query: Echo of the original user query
        response: LLM-generated response (if successful)
        error: Error message (if failed)
        model: Name of the LLM model used
    """
    status: str = Field(..., description="Response status (success/error)")
    query: str = Field(..., description="Original user query")
    response: Optional[str] = Field(None, description="Agent response")
    error: Optional[str] = Field(None, description="Error message if status is error")
    model: str = Field(..., description="LLM model used")


class HealthResponse(BaseModel):
    """
    Health check response schema.
    
    Used by container orchestration systems (Kubernetes, Docker)
    to determine if the service is ready to accept traffic.
    """
    status: str
    service: str
    version: str


# ============================================================================
# LIFECYCLE EVENTS
# ============================================================================

@app.on_event("startup")
async def startup_event():
    """
    Application startup event handler.
    
    Validates configuration and initializes resources before
    accepting any requests. Fails fast if configuration is invalid.
    
    Raises:
        RuntimeError: If agent configuration validation fails
    """
    logger.info(f"Starting {config.app_name} service")
    if not agent.validate_config():
        logger.error("Agent configuration validation failed")
        raise RuntimeError("Invalid agent configuration")
    logger.info("Agent configuration validated successfully")


# ============================================================================
# API ENDPOINTS
# ============================================================================

@app.get("/health", response_model=HealthResponse)
async def health_check():
    """
    Health check endpoint for container orchestration.
    
    Returns:
        HealthResponse: Service health status
        
    Status Codes:
        200: Service is healthy and ready
    """
    return HealthResponse(
        status="healthy",
        service=config.app_name,
        version="0.1.0"
    )


@app.post("/chat", response_model=ChatResponse)
async def chat(request: ChatRequest):
    """
    Process vehicle support queries through LLM.
    
    This endpoint handles user queries about vehicle issues, maintenance,
    and troubleshooting. It includes retry logic, timeout handling, and
    comprehensive error handling.
    
    Args:
        request: ChatRequest with user query and optional session_id
        
    Returns:
        ChatResponse: LLM-generated response or error details
        
    Status Codes:
        200: Successful response
        400: Invalid request format
        500: Internal server error or LLM failure
        
    Security:
        - Input validation with regex patterns
        - Input sanitization (strip whitespace)
        - Error message sanitization (no internal details exposed)
        - Request tracking with latency metrics
    """
    start_time = time.time()
    
    try:
        # Sanitize input - remove any potential injection attempts
        sanitized_query = request.query.strip()
        
        logger.info(f"Chat request received: {sanitized_query[:50]}...")
        
        # Process query through agent (includes retry logic)
        result = await agent.process_query(sanitized_query)
        
        # Calculate latency for monitoring
        latency_ms = (time.time() - start_time) * 1000
        
        # Record metrics for Prometheus/Grafana
        metrics.record_request(
            latency_ms=latency_ms,
            error=(result.get("status") == "error")
        )
        
        if result["status"] == "error":
            logger.warning(f"Agent returned error: {result.get('error')} (latency: {latency_ms:.2f}ms)")
            # Don't expose internal error details to client
            raise HTTPException(
                status_code=500,
                detail="Failed to process query. Please try again."
            )
        
        logger.info(f"Chat request processed successfully (latency: {latency_ms:.2f}ms)")
        return ChatResponse(**result)
        
    except HTTPException:
        raise
    except ValueError as e:
        latency_ms = (time.time() - start_time) * 1000
        metrics.record_request(latency_ms=latency_ms, error=True)
        logger.error(f"Validation error: {str(e)}")
        raise HTTPException(status_code=400, detail="Invalid request format")
    except Exception as e:
        latency_ms = (time.time() - start_time) * 1000
        metrics.record_request(latency_ms=latency_ms, error=True)
        logger.error(f"Unexpected error in /chat: {str(e)}", exc_info=True)
        raise HTTPException(status_code=500, detail="Internal server error")


@app.get("/metrics")
async def metrics_endpoint():
    """
    Metrics endpoint in JSON format.
    
    Returns current metrics including request count, error count,
    average latency, and success rate.
    
    Returns:
        JSONResponse: Metrics in JSON format
        
    Example Response:
        {
            "total_requests": 42,
            "total_errors": 0,
            "avg_latency_ms": 25000.0,
            "success_rate": 100.0
        }
    """
    return JSONResponse(content=metrics.get_metrics())


@app.get("/metrics/prometheus")
async def prometheus_metrics():
    """
    Metrics endpoint in Prometheus text format.
    
    This endpoint is scraped by Prometheus every 15 seconds
    (configured in observability/prometheus.yml).
    
    Returns:
        PlainTextResponse: Metrics in Prometheus exposition format
        
    Example Response:
        # HELP autoassist_requests_total Total number of requests
        # TYPE autoassist_requests_total counter
        autoassist_requests_total 42
    """
    from fastapi.responses import PlainTextResponse
    return PlainTextResponse(content=metrics.get_prometheus_format(), media_type="text/plain")


@app.get("/")
async def root():
    """
    Root endpoint with service information.
    
    Provides basic service information and available endpoints.
    Useful for API discovery and health checks.
    
    Returns:
        dict: Service information and endpoint list
    """
    return {
        "service": config.app_name,
        "status": "running",
        "endpoints": [
            "/health - Health check",
            "/chat - Chat endpoint (POST)",
            "/metrics - Metrics endpoint (JSON)",
            "/metrics/prometheus - Prometheus-format metrics",
            "/docs - API documentation"
        ]
    }


# ============================================================================
# APPLICATION ENTRY POINT
# ============================================================================

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(
        app,
        host="0.0.0.0",  # Listen on all interfaces
        port=8000,
        log_config=None  # Use our custom logging configuration
    )

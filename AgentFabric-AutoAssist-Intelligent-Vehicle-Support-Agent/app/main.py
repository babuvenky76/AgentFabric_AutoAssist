"""
FastAPI Application for AutoAssist
Main entry point with endpoints: /chat, /health, /metrics
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


# Setup logging
logger = setup_logging(config.app_name, config.log_level)

# Initialize app
app = FastAPI(
    title=config.app_name,
    description="Intelligent Vehicle Support Agent",
    version="0.1.0",
)

# Add CORS middleware - PRODUCTION: Restrict origins
app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:3000",
        "http://localhost:3001",
        # TODO: Add production domains here
    ],
    allow_credentials=True,
    allow_methods=["GET", "POST"],  # Restrict to only needed methods
    allow_headers=["Content-Type", "Authorization"],  # Restrict headers
    max_age=600,  # Cache preflight requests for 10 minutes
)

# Initialize agent
agent = AutoAssistAgent(config)


# Request/Response models
class ChatRequest(BaseModel):
    """Chat request schema with strict validation"""
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
    """Chat response schema"""
    status: str = Field(..., description="Response status (success/error)")
    query: str = Field(..., description="Original user query")
    response: Optional[str] = Field(None, description="Agent response")
    error: Optional[str] = Field(None, description="Error message if status is error")
    model: str = Field(..., description="LLM model used")


class HealthResponse(BaseModel):
    """Health check response"""
    status: str
    service: str
    version: str


@app.on_event("startup")
async def startup_event():
    """Initialize on application startup"""
    logger.info(f"Starting {config.app_name} service")
    if not agent.validate_config():
        logger.error("Agent configuration validation failed")
        raise RuntimeError("Invalid agent configuration")
    logger.info("Agent configuration validated successfully")


@app.get("/health", response_model=HealthResponse)
async def health_check():
    """Health check endpoint"""
    return HealthResponse(
        status="healthy",
        service=config.app_name,
        version="0.1.0"
    )


@app.post("/chat", response_model=ChatResponse)
async def chat(request: ChatRequest):
    """Chat endpoint for vehicle support queries"""
    start_time = time.time()
    
    try:
        # Sanitize input - remove any potential injection attempts
        sanitized_query = request.query.strip()
        
        logger.info(f"Chat request received: {sanitized_query[:50]}...")
        
        # Process query through agent
        result = await agent.process_query(sanitized_query)
        
        # Calculate latency
        latency_ms = (time.time() - start_time) * 1000
        
        # Record metrics
        metrics.record_request(
            latency_ms=latency_ms,
            error=(result.get("status") == "error")
        )
        
        if result["status"] == "error":
            logger.warning(f"Agent returned error: {result.get('error')} (latency: {latency_ms:.2f}ms)")
            raise HTTPException(
                status_code=500,
                detail="Failed to process query. Please try again."  # Don't expose internal errors
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
    """Metrics endpoint for monitoring (JSON format)"""
    return JSONResponse(content=metrics.get_metrics())


@app.get("/metrics/prometheus")
async def prometheus_metrics():
    """Prometheus-format metrics endpoint"""
    from fastapi.responses import PlainTextResponse
    return PlainTextResponse(content=metrics.get_prometheus_format(), media_type="text/plain")



@app.get("/")
async def root():
    """Root endpoint"""
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


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(
        app,
        host="0.0.0.0",
        port=8000,
        log_config=None  # Use our custom logging
    )

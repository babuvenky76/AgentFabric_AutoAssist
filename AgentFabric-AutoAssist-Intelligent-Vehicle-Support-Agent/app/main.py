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

# Add CORS middleware to allow cross-origin requests from frontend
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000", "http://localhost:3001", "*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Initialize agent
agent = AutoAssistAgent(config)


# Request/Response models
class ChatRequest(BaseModel):
    """Chat request schema"""
    query: str = Field(..., min_length=1, max_length=1000, description="User query")
    session_id: Optional[str] = Field(None, description="Optional session ID for tracking")


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
        logger.info(f"Chat request received: {request.query[:50]}...")
        
        # Process query through agent
        result = await agent.process_query(request.query)
        
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
                detail=result.get("error", "Failed to process query")
            )
        
        logger.info(f"Chat request processed successfully (latency: {latency_ms:.2f}ms)")
        return ChatResponse(**result)
        
    except HTTPException:
        # Re-raise HTTP exceptions without further processing
        raise
    except ValueError as e:
        latency_ms = (time.time() - start_time) * 1000
        metrics.record_request(latency_ms=latency_ms, error=True)
        logger.error(f"Validation error: {str(e)}")
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        latency_ms = (time.time() - start_time) * 1000
        metrics.record_request(latency_ms=latency_ms, error=True)
        logger.error(f"Unexpected error in /chat: {str(e)}")
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

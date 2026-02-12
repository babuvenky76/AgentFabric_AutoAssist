"""
LLM Adapter Layer - Abstracts LLM backend
Supports local models (LMStudio) and API-based models
"""

import asyncio
import httpx
from abc import ABC, abstractmethod
from typing import Optional, Dict, Any
from app.config import LLMConfig


class LLMAdapter(ABC):
    """Abstract base class for LLM adapters"""
    
    def __init__(self, config: LLMConfig):
        self.config = config
    
    @abstractmethod
    async def generate(self, prompt: str) -> str:
        """Generate text response from LLM"""
        pass
    
    @abstractmethod
    def validate_config(self) -> bool:
        """Validate adapter configuration"""
        pass


class LocalLLMAdapter(LLMAdapter):
    """Adapter for local LLM models (e.g., LMStudio)"""
    
    def __init__(self, config: LLMConfig):
        super().__init__(config)
        self.endpoint = config.api_endpoint or "http://localhost:1234/v1"
    
    async def generate(self, prompt: str) -> str:
        """Generate text from local LLM"""
        try:
            headers = {}
            if self.config.api_token:
                headers["Authorization"] = f"Bearer {self.config.api_token}"
            
            async with httpx.AsyncClient(timeout=self.config.timeout_seconds) as client:
                response = await client.post(
                    f"{self.endpoint}/completions",
                    headers=headers,
                    json={
                        "model": self.config.model_name,
                        "prompt": prompt,
                        "temperature": self.config.temperature,
                        "max_tokens": self.config.max_tokens,
                    }
                )
                response.raise_for_status()
                data = response.json()
                return data.get("choices", [{}])[0].get("text", "").strip()
        except Exception as e:
            raise RuntimeError(f"Local LLM generation failed: {str(e)}")
    
    def validate_config(self) -> bool:
        """Validate local LLM configuration"""
        return bool(self.config.model_name and self.endpoint)



class APILLMAdapter(LLMAdapter):
    """Adapter for cloud-based LLM APIs"""
    
    async def generate(self, prompt: str) -> str:
        """Generate text from API-based LLM"""
        try:
            headers = {}
            if self.config.api_token:
                headers["Authorization"] = f"Bearer {self.config.api_token}"
            
            async with httpx.AsyncClient(timeout=self.config.timeout_seconds) as client:
                response = await client.post(
                    self.config.api_endpoint,
                    headers=headers,
                    json={
                        "model": self.config.model_name,
                        "prompt": prompt,
                        "temperature": self.config.temperature,
                        "max_tokens": self.config.max_tokens,
                    }
                )
                response.raise_for_status()
                data = response.json()
                return data.get("choices", [{}])[0].get("text", "").strip()
        except Exception as e:
            raise RuntimeError(f"API LLM generation failed: {str(e)}")
    
    def validate_config(self) -> bool:
        """Validate API LLM configuration"""
        return bool(self.config.model_name and self.config.api_endpoint)



class LLMAdapterFactory:
    """Factory for creating appropriate LLM adapter"""
    
    @staticmethod
    def create_adapter(config: LLMConfig) -> LLMAdapter:
        """Create LLM adapter based on provider type"""
        if config.provider == "local":
            return LocalLLMAdapter(config)
        elif config.provider == "api":
            return APILLMAdapter(config)
        else:
            raise ValueError(f"Unknown LLM provider: {config.provider}")

"""
Configuration loader for AutoAssist
Handles environment-based configuration with validation
"""

import os
from dataclasses import dataclass
from typing import Optional
from dotenv import load_dotenv

# Load .env file
load_dotenv()


@dataclass
class LLMConfig:
    """LLM Configuration"""
    provider: str  # "local" or "api"
    model_name: str
    api_endpoint: Optional[str] = None
    api_token: Optional[str] = None
    temperature: float = 0.7
    max_tokens: int = 1024
    timeout_seconds: int = 30


@dataclass
class AppConfig:
    """Application Configuration"""
    app_name: str = "AutoAssist"
    debug: bool = False
    log_level: str = "INFO"
    llm: LLMConfig = None
    
    def __post_init__(self):
        if self.llm is None:
            self.llm = self._load_llm_config()
    
    @classmethod
    def from_env(cls) -> "AppConfig":
        """Load configuration from environment variables"""
        return cls(
            app_name=os.getenv("APP_NAME", "AutoAssist"),
            debug=os.getenv("DEBUG", "false").lower() == "true",
            log_level=os.getenv("LOG_LEVEL", "INFO"),
            llm=LLMConfig(
                provider=os.getenv("MODEL_PROVIDER", "local"),
                model_name=os.getenv("MODEL_NAME", "mistral"),
                api_endpoint=os.getenv("API_ENDPOINT"),
                api_token=os.getenv("API_TOKEN"),
                temperature=float(os.getenv("TEMPERATURE", "0.7")),
                max_tokens=int(os.getenv("MAX_TOKENS", "1024")),
                timeout_seconds=int(os.getenv("TIMEOUT_SECONDS", "30")),
            )
        )
    
    def _load_llm_config(self) -> LLMConfig:
        """Load LLM configuration from environment"""
        return LLMConfig(
            provider=os.getenv("MODEL_PROVIDER", "local"),
            model_name=os.getenv("MODEL_NAME", "mistral"),
            api_endpoint=os.getenv("API_ENDPOINT"),
            api_token=os.getenv("API_TOKEN"),
            temperature=float(os.getenv("TEMPERATURE", "0.7")),
            max_tokens=int(os.getenv("MAX_TOKENS", "1024")),
            timeout_seconds=int(os.getenv("TIMEOUT_SECONDS", "30")),
        )


# Global config instance
config = AppConfig.from_env()

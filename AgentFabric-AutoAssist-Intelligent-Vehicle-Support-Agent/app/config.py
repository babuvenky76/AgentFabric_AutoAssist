"""
Configuration Module - Environment-Based Application Settings
=============================================================

This module handles all application configuration using environment variables
and the 12-factor app methodology. Configuration is loaded from .env files
and environment variables, with sensible defaults for development.

Architecture:
    - LLMConfig: Configuration for LLM backend (model, endpoint, tokens)
    - AppConfig: Main application configuration (app name, debug, logging)
    - Global config instance: Singleton loaded at module import time

Configuration Sources (in order of precedence):
    1. Environment variables (highest priority)
    2. .env file in project root
    3. Default values (lowest priority)

12-Factor App Principles:
    - Store config in environment (not in code)
    - Strict separation of config from code
    - Config varies between deployments (dev, staging, prod)
    - No secrets in version control

Environment Variables:
    Application:
        - APP_NAME: Application name (default: "AutoAssist")
        - DEBUG: Enable debug mode (default: "false")
        - LOG_LEVEL: Logging level (default: "INFO")
    
    LLM Configuration:
        - MODEL_PROVIDER: "local" or "api" (default: "local")
        - MODEL_NAME: Model identifier (default: "mistral")
        - API_ENDPOINT: LLM API endpoint URL (optional)
        - API_TOKEN: Authentication token (optional, keep secret!)
        - TEMPERATURE: Sampling temperature 0.0-1.0 (default: 0.7)
        - MAX_TOKENS: Maximum response length (default: 1024)
        - TIMEOUT_SECONDS: Request timeout in seconds (default: 30)

Security Best Practices:
    - Never commit .env files to version control (use .env.example instead)
    - Store API tokens in environment variables, not in code
    - Use different .env files for dev/staging/prod environments
    - Rotate API tokens regularly
    - Use secrets management in production (AWS Secrets Manager, HashiCorp Vault)

Usage Example:
    ```python
    from app.config import config
    
    # Access configuration
    print(config.app_name)  # "AutoAssist"
    print(config.llm.model_name)  # "qwen-2.5-coder"
    print(config.llm.timeout_seconds)  # 270
    
    # Configuration is immutable (dataclass with frozen=False by default)
    # For production, consider using frozen=True to prevent accidental changes
    ```

Docker Integration:
    - Environment variables passed via docker-compose.yml
    - .env file loaded automatically by docker-compose
    - Secrets can be passed via Docker secrets or environment variables

Author: AutoAssist Development Team
License: MIT
"""

import os
from dataclasses import dataclass
from typing import Optional
from dotenv import load_dotenv

# Load environment variables from .env file (if present)
# This is idempotent - safe to call multiple times
# Variables already set in environment take precedence over .env file
load_dotenv()


# ============================================================================
# LLM CONFIGURATION
# ============================================================================


@dataclass
class LLMConfig:
    """
    LLM Configuration Settings
    
    Encapsulates all configuration needed to communicate with LLM backends
    (local models via LMStudio or cloud APIs like OpenAI).
    
    Attributes:
        provider (str): LLM provider type - "local" or "api"
        model_name (str): Model identifier (e.g., "qwen-2.5-coder", "gpt-4")
        api_endpoint (Optional[str]): API endpoint URL (e.g., "http://localhost:1234/v1")
        api_token (Optional[str]): Authentication token (Bearer token for API calls)
        temperature (float): Sampling temperature 0.0-1.0 (controls randomness)
        max_tokens (int): Maximum response length in tokens
        timeout_seconds (int): Request timeout in seconds (prevents indefinite hangs)
    
    Provider Types:
        - "local": Local LLM server (LMStudio, Ollama, etc.)
        - "api": Cloud-based API (OpenAI, Anthropic, etc.)
    
    Temperature Guide:
        - 0.0: Deterministic, focused responses (best for factual queries)
        - 0.7: Balanced creativity and coherence (default, good for most use cases)
        - 1.0: Maximum creativity and randomness (best for creative writing)
    
    Timeout Considerations:
        - Local models: 30-60s usually sufficient
        - Cloud APIs: 30-90s depending on model size
        - Large context windows: May need 120-300s
        - Production: Set based on p99 latency + buffer
    
    Security Notes:
        - api_token should NEVER be hardcoded or committed to version control
        - Always load from environment variables or secrets management
        - Use HTTPS endpoints in production (not HTTP)
        - Rotate tokens regularly
    
    Example:
        ```python
        # Local LMStudio configuration
        local_config = LLMConfig(
            provider="local",
            model_name="qwen-2.5-coder",
            api_endpoint="http://host.docker.internal:1234/v1",
            temperature=0.7,
            max_tokens=2000,
            timeout_seconds=270
        )
        
        # Cloud API configuration
        api_config = LLMConfig(
            provider="api",
            model_name="gpt-4",
            api_endpoint="https://api.openai.com/v1/completions",
            api_token=os.getenv("OPENAI_API_KEY"),
            temperature=0.7,
            max_tokens=1024,
            timeout_seconds=60
        )
        ```
    """
    provider: str  # "local" or "api"
    model_name: str  # Model identifier
    api_endpoint: Optional[str] = None  # API endpoint URL
    api_token: Optional[str] = None  # Authentication token (keep secret!)
    temperature: float = 0.7  # Sampling temperature (0.0-1.0)
    max_tokens: int = 1024  # Maximum response length
    timeout_seconds: int = 30  # Request timeout


# ============================================================================
# APPLICATION CONFIGURATION
# ============================================================================


@dataclass
class AppConfig:
    """
    Main Application Configuration
    
    Encapsulates all application-level settings including app metadata,
    debug settings, logging configuration, and LLM configuration.
    
    Attributes:
        app_name (str): Application name (used in logs and metrics)
        debug (bool): Enable debug mode (verbose logging, detailed errors)
        log_level (str): Logging level (DEBUG, INFO, WARNING, ERROR, CRITICAL)
        llm (LLMConfig): LLM configuration object
    
    Configuration Loading:
        - Use from_env() class method to load from environment variables
        - Automatically loads .env file if present
        - Provides sensible defaults for development
    
    Debug Mode:
        - When enabled: Verbose logging, detailed error messages, auto-reload
        - When disabled: Production logging, sanitized errors, no auto-reload
        - NEVER enable debug mode in production (security risk!)
    
    Log Levels:
        - DEBUG: Detailed diagnostic information (very verbose)
        - INFO: General informational messages (default)
        - WARNING: Warning messages for potentially harmful situations
        - ERROR: Error messages for serious problems
        - CRITICAL: Critical messages for very serious errors
    
    Example:
        ```python
        # Load from environment
        config = AppConfig.from_env()
        
        # Access configuration
        print(config.app_name)  # "AutoAssist"
        print(config.debug)  # False
        print(config.llm.model_name)  # "qwen-2.5-coder"
        ```
    """
    app_name: str = "AutoAssist"
    debug: bool = False
    log_level: str = "INFO"
    llm: LLMConfig = None
    
    def __post_init__(self):
        """
        Post-initialization hook (called after __init__).
        
        Ensures LLM configuration is loaded if not provided explicitly.
        This allows creating AppConfig without specifying llm parameter.
        """
        if self.llm is None:
            self.llm = self._load_llm_config()
    
    @classmethod
    def from_env(cls) -> "AppConfig":
        """
        Load configuration from environment variables.
        
        This is the recommended way to create AppConfig instances.
        Reads from environment variables with sensible defaults.
        
        Returns:
            AppConfig: Configured application instance
        
        Environment Variables:
            - APP_NAME: Application name (default: "AutoAssist")
            - DEBUG: Enable debug mode - "true" or "false" (default: "false")
            - LOG_LEVEL: Logging level (default: "INFO")
            - MODEL_PROVIDER: LLM provider - "local" or "api" (default: "local")
            - MODEL_NAME: Model identifier (default: "mistral")
            - API_ENDPOINT: LLM API endpoint URL (optional)
            - API_TOKEN: Authentication token (optional)
            - TEMPERATURE: Sampling temperature (default: "0.7")
            - MAX_TOKENS: Maximum response length (default: "1024")
            - TIMEOUT_SECONDS: Request timeout (default: "30")
        
        Example:
            ```python
            # Set environment variables
            os.environ["APP_NAME"] = "AutoAssist"
            os.environ["MODEL_PROVIDER"] = "local"
            os.environ["MODEL_NAME"] = "qwen-2.5-coder"
            os.environ["TIMEOUT_SECONDS"] = "270"
            
            # Load configuration
            config = AppConfig.from_env()
            ```
        """
        return cls(
            # Application settings
            app_name=os.getenv("APP_NAME", "AutoAssist"),
            debug=os.getenv("DEBUG", "false").lower() == "true",  # Parse boolean
            log_level=os.getenv("LOG_LEVEL", "INFO"),
            
            # LLM settings
            llm=LLMConfig(
                provider=os.getenv("MODEL_PROVIDER", "local"),
                model_name=os.getenv("MODEL_NAME", "mistral"),
                api_endpoint=os.getenv("API_ENDPOINT"),
                api_token=os.getenv("API_TOKEN"),
                temperature=float(os.getenv("TEMPERATURE", "0.7")),  # Parse float
                max_tokens=int(os.getenv("MAX_TOKENS", "1024")),  # Parse int
                timeout_seconds=int(os.getenv("TIMEOUT_SECONDS", "30")),  # Parse int
            )
        )
    
    def _load_llm_config(self) -> LLMConfig:
        """
        Load LLM configuration from environment variables.
        
        Internal helper method called by __post_init__ if llm is not provided.
        
        Returns:
            LLMConfig: LLM configuration loaded from environment
        """
        return LLMConfig(
            provider=os.getenv("MODEL_PROVIDER", "local"),
            model_name=os.getenv("MODEL_NAME", "mistral"),
            api_endpoint=os.getenv("API_ENDPOINT"),
            api_token=os.getenv("API_TOKEN"),
            temperature=float(os.getenv("TEMPERATURE", "0.7")),
            max_tokens=int(os.getenv("MAX_TOKENS", "1024")),
            timeout_seconds=int(os.getenv("TIMEOUT_SECONDS", "30")),
        )


# ============================================================================
# GLOBAL CONFIGURATION INSTANCE
# ============================================================================

# Global singleton configuration instance
# Loaded once at module import time from environment variables
# Import this instance in other modules: from app.config import config
config = AppConfig.from_env()

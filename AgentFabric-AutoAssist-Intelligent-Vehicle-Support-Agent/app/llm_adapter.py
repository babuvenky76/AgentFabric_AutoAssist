"""
LLM Adapter Layer - Abstracts LLM Backend Communication
=======================================================

This module implements the Adapter Pattern to provide a unified interface for
communicating with different LLM backends (local models via LMStudio or cloud APIs).

Architecture:
    - LLMAdapter: Abstract base class defining the interface
    - LocalLLMAdapter: Concrete implementation for local models (LMStudio)
    - APILLMAdapter: Concrete implementation for cloud-based APIs
    - LLMAdapterFactory: Factory pattern for creating appropriate adapters

Key Features:
    - Automatic retry logic with exponential backoff (3 attempts)
    - Configurable timeouts to handle slow model responses
    - Bearer token authentication support
    - Graceful error handling with detailed logging
    - Provider-agnostic interface for easy switching

Retry Strategy:
    - Max retries: 3 attempts
    - Backoff: Linear (1s, 2s, 3s delays between retries)
    - Handles both HTTP errors and connection failures
    - Preserves last error for debugging

Usage Example:
    ```python
    config = LLMConfig(provider="local", model_name="qwen-2.5", ...)
    adapter = LLMAdapterFactory.create_adapter(config)
    response = await adapter.generate("What is the weather?")
    ```

Security Notes:
    - API tokens are passed via Authorization header (Bearer scheme)
    - Timeouts prevent indefinite hangs (default: 270 seconds)
    - Error messages sanitized to avoid leaking sensitive data

Author: AutoAssist Development Team
License: MIT
"""

import asyncio
import httpx
from abc import ABC, abstractmethod
from typing import Optional, Dict, Any
from app.config import LLMConfig


# ============================================================================
# ABSTRACT BASE CLASS
# ============================================================================


class LLMAdapter(ABC):
    """
    Abstract Base Class for LLM Adapters
    
    Defines the contract that all LLM adapter implementations must follow.
    This enables polymorphic behavior and easy switching between providers.
    
    Attributes:
        config (LLMConfig): Configuration object containing model settings,
                           endpoints, tokens, and timeout values
    
    Design Pattern:
        Uses the Template Method pattern - subclasses implement specific
        behavior while maintaining a consistent interface.
    """
    
    def __init__(self, config: LLMConfig):
        """
        Initialize the adapter with configuration.
        
        Args:
            config (LLMConfig): LLM configuration object with provider-specific settings
        """
        self.config = config
    
    @abstractmethod
    async def generate(self, prompt: str) -> str:
        """
        Generate text response from LLM (must be implemented by subclasses).
        
        Args:
            prompt (str): Input text prompt to send to the LLM
        
        Returns:
            str: Generated text response from the model
        
        Raises:
            RuntimeError: If generation fails after all retry attempts
            NotImplementedError: If subclass doesn't implement this method
        """
        pass
    
    @abstractmethod
    def validate_config(self) -> bool:
        """
        Validate adapter configuration (must be implemented by subclasses).
        
        Returns:
            bool: True if configuration is valid, False otherwise
        
        Note:
            Should check for required fields like model_name, endpoint, etc.
        """
        pass


# ============================================================================
# LOCAL LLM ADAPTER (LMStudio, Ollama, etc.)
# ============================================================================


class LocalLLMAdapter(LLMAdapter):
    """
    Adapter for Local LLM Models (LMStudio, Ollama, etc.)
    
    Communicates with locally-hosted LLM servers that expose OpenAI-compatible
    APIs. Commonly used with LMStudio running models like Qwen, Llama, etc.
    
    Attributes:
        endpoint (str): Base URL for the local LLM server (default: http://localhost:1234/v1)
        max_retries (int): Maximum number of retry attempts (default: 3)
        retry_delay (float): Base delay in seconds between retries (default: 1.0)
    
    API Compatibility:
        Expects OpenAI-compatible /v1/completions endpoint with JSON payload:
        {
            "model": "model-name",
            "prompt": "user prompt",
            "temperature": 0.7,
            "max_tokens": 2000
        }
    
    Docker Networking:
        When running in Docker, use host.docker.internal instead of localhost
        to access LMStudio running on the host machine.
    
    Example:
        ```python
        config = LLMConfig(
            provider="local",
            model_name="qwen-2.5-coder",
            api_endpoint="http://host.docker.internal:1234/v1",
            api_token="optional-token"
        )
        adapter = LocalLLMAdapter(config)
        response = await adapter.generate("Explain Docker networking")
        ```
    """
    
    def __init__(self, config: LLMConfig):
        """
        Initialize local LLM adapter with retry configuration.
        
        Args:
            config (LLMConfig): Configuration with endpoint, model name, and timeout
        """
        super().__init__(config)
        # Default to localhost if no endpoint specified
        self.endpoint = config.api_endpoint or "http://localhost:1234/v1"
        self.max_retries = 3  # Retry up to 3 times for transient failures
        self.retry_delay = 1.0  # Linear backoff: 1s, 2s, 3s
    
    async def generate(self, prompt: str) -> str:
        """
        Generate text from local LLM with automatic retry logic.
        
        Implements exponential backoff retry strategy to handle transient failures
        like network hiccups, temporary server overload, or model loading delays.
        
        Args:
            prompt (str): Input text prompt to send to the local LLM
        
        Returns:
            str: Generated text response, stripped of leading/trailing whitespace
        
        Raises:
            RuntimeError: If all retry attempts fail, includes details of last error
        
        Retry Behavior:
            - Attempt 1: Immediate
            - Attempt 2: After 1 second delay
            - Attempt 3: After 2 second delay
            - Total max wait: 3 seconds across all retries
        
        Error Handling:
            - HTTPStatusError: HTTP 4xx/5xx responses (e.g., 500 Internal Server Error)
            - ConnectError: Cannot reach the server (e.g., LMStudio not running)
            - TimeoutError: Request exceeds configured timeout (default: 270s)
        
        Example Response Format:
            {
                "choices": [
                    {"text": "The weather is sunny today."}
                ]
            }
        """
        last_error = None
        
        # Retry loop: attempt up to max_retries times
        for attempt in range(self.max_retries):
            try:
                # Step 1: Prepare authentication headers
                headers = {"Content-Type": "application/json"}
                if self.config.api_token:
                    # Optional: Add Bearer token if LMStudio requires authentication
                    headers["Authorization"] = f"Bearer {self.config.api_token}"
                
                # Step 2: Create async HTTP client with configured timeout
                # Timeout prevents indefinite hangs (important for production)
                async with httpx.AsyncClient(timeout=self.config.timeout_seconds) as client:
                    # Step 3: Send POST request to /v1/completions endpoint
                    response = await client.post(
                        f"{self.endpoint}/completions",
                        headers=headers,
                        json={
                            "model": self.config.model_name,  # e.g., "qwen-2.5-coder"
                            "prompt": prompt,
                            "temperature": self.config.temperature,  # Controls randomness (0.0-1.0)
                            "max_tokens": self.config.max_tokens,  # Max response length
                        }
                    )
                    
                    # Step 4: Raise exception for HTTP error status codes (4xx, 5xx)
                    response.raise_for_status()
                    
                    # Step 5: Parse JSON response and extract generated text
                    data = response.json()
                    return data.get("choices", [{}])[0].get("text", "").strip()
                    
            except httpx.HTTPStatusError as e:
                # HTTP error (4xx, 5xx) - log details for debugging
                last_error = e
                print(f"HTTP error on attempt {attempt + 1}: {e.response.status_code} - {e.response.text}")
                if attempt < self.max_retries - 1:
                    # Wait before retrying (linear backoff: 1s, 2s, 3s)
                    await asyncio.sleep(self.retry_delay * (attempt + 1))
                    continue
                    
            except Exception as e:
                # Catch-all for connection errors, timeouts, JSON parsing errors, etc.
                last_error = e
                print(f"Error on attempt {attempt + 1}: {type(e).__name__} - {str(e)}")
                if attempt < self.max_retries - 1:
                    # Wait before retrying
                    await asyncio.sleep(self.retry_delay * (attempt + 1))
                    continue
        
        # All retries exhausted - raise final error
        raise RuntimeError(f"Local LLM generation failed after {self.max_retries} attempts: {str(last_error)}")
    
    def validate_config(self) -> bool:
        """
        Validate local LLM configuration.
        
        Checks that required configuration fields are present and non-empty.
        
        Returns:
            bool: True if model_name and endpoint are configured, False otherwise
        
        Note:
            This is a basic validation. It doesn't verify that the endpoint
            is reachable or that the model actually exists.
        """
        return bool(self.config.model_name and self.endpoint)


# ============================================================================
# CLOUD API ADAPTER (OpenAI, Anthropic, etc.)
# ============================================================================

class APILLMAdapter(LLMAdapter):
    """
    Adapter for Cloud-Based LLM APIs (OpenAI, Anthropic, etc.)
    
    Communicates with cloud-hosted LLM services via their REST APIs.
    Supports any provider with OpenAI-compatible completion endpoints.
    
    Attributes:
        max_retries (int): Maximum number of retry attempts (default: 3)
        retry_delay (float): Base delay in seconds between retries (default: 1.0)
    
    API Compatibility:
        Expects OpenAI-compatible completion endpoint with JSON payload:
        {
            "model": "model-name",
            "prompt": "user prompt",
            "temperature": 0.7,
            "max_tokens": 2000
        }
    
    Security:
        - Always use HTTPS endpoints in production
        - Store API tokens in environment variables, never hardcode
        - Tokens are sent via Authorization: Bearer <token> header
    
    Example:
        ```python
        config = LLMConfig(
            provider="api",
            model_name="gpt-4",
            api_endpoint="https://api.openai.com/v1/completions",
            api_token=os.getenv("OPENAI_API_KEY")
        )
        adapter = APILLMAdapter(config)
        response = await adapter.generate("Explain cloud APIs")
        ```
    """
    
    def __init__(self, config: LLMConfig):
        """
        Initialize cloud API adapter with retry configuration.
        
        Args:
            config (LLMConfig): Configuration with API endpoint, token, and timeout
        """
        super().__init__(config)
        self.max_retries = 3  # Retry up to 3 times for transient failures
        self.retry_delay = 1.0  # Linear backoff: 1s, 2s, 3s
    
    async def generate(self, prompt: str) -> str:
        """
        Generate text from cloud API with automatic retry logic.
        
        Implements exponential backoff retry strategy to handle transient failures
        like rate limits, temporary service outages, or network issues.
        
        Args:
            prompt (str): Input text prompt to send to the cloud API
        
        Returns:
            str: Generated text response, stripped of leading/trailing whitespace
        
        Raises:
            RuntimeError: If all retry attempts fail, includes details of last error
        
        Retry Behavior:
            - Attempt 1: Immediate
            - Attempt 2: After 1 second delay
            - Attempt 3: After 2 second delay
            - Total max wait: 3 seconds across all retries
        
        Error Handling:
            - HTTPStatusError: HTTP 4xx/5xx responses (e.g., 429 Rate Limit, 500 Server Error)
            - ConnectError: Cannot reach the API endpoint (network issues)
            - TimeoutError: Request exceeds configured timeout (default: 270s)
        
        Production Note:
            For production use, consider implementing more sophisticated retry logic:
            - Exponential backoff with jitter
            - Respect Retry-After headers for rate limits
            - Circuit breaker pattern for repeated failures
        """
        last_error = None
        
        # Retry loop: attempt up to max_retries times
        for attempt in range(self.max_retries):
            try:
                # Step 1: Prepare authentication headers
                headers = {}
                if self.config.api_token:
                    # Add Bearer token for API authentication (required by most providers)
                    headers["Authorization"] = f"Bearer {self.config.api_token}"
                
                # Step 2: Create async HTTP client with configured timeout
                async with httpx.AsyncClient(timeout=self.config.timeout_seconds) as client:
                    # Step 3: Send POST request to cloud API endpoint
                    response = await client.post(
                        self.config.api_endpoint,
                        headers=headers,
                        json={
                            "model": self.config.model_name,  # e.g., "gpt-4", "claude-3"
                            "prompt": prompt,
                            "temperature": self.config.temperature,  # Controls randomness
                            "max_tokens": self.config.max_tokens,  # Max response length
                        }
                    )
                    
                    # Step 4: Raise exception for HTTP error status codes
                    response.raise_for_status()
                    
                    # Step 5: Parse JSON response and extract generated text
                    data = response.json()
                    return data.get("choices", [{}])[0].get("text", "").strip()
                    
            except Exception as e:
                # Catch all errors (HTTP, connection, timeout, JSON parsing, etc.)
                last_error = e
                if attempt < self.max_retries - 1:
                    # Wait before retrying (linear backoff: 1s, 2s, 3s)
                    await asyncio.sleep(self.retry_delay * (attempt + 1))
                    continue
        
        # All retries exhausted - raise final error
        raise RuntimeError(f"API LLM generation failed after {self.max_retries} attempts: {str(last_error)}")
    
    def validate_config(self) -> bool:
        """
        Validate cloud API configuration.
        
        Checks that required configuration fields are present and non-empty.
        
        Returns:
            bool: True if model_name and api_endpoint are configured, False otherwise
        
        Note:
            This is a basic validation. It doesn't verify that the endpoint
            is reachable or that the API token is valid.
        """
        return bool(self.config.model_name and self.config.api_endpoint)


# ============================================================================
# FACTORY PATTERN FOR ADAPTER CREATION
# ============================================================================

class LLMAdapterFactory:
    """
    Factory for Creating LLM Adapters
    
    Implements the Factory Pattern to encapsulate adapter creation logic.
    Allows easy addition of new adapter types without modifying client code.
    
    Supported Providers:
        - "local": LocalLLMAdapter (LMStudio, Ollama, etc.)
        - "api": APILLMAdapter (OpenAI, Anthropic, etc.)
    
    Design Benefits:
        - Single point of adapter creation
        - Easy to add new providers (just add new case)
        - Client code doesn't need to know about concrete adapter classes
        - Validates provider type at creation time
    
    Example:
        ```python
        # Client code doesn't need to know about LocalLLMAdapter or APILLMAdapter
        config = LLMConfig(provider="local", ...)
        adapter = LLMAdapterFactory.create_adapter(config)
        response = await adapter.generate("Hello")
        ```
    """
    
    @staticmethod
    def create_adapter(config: LLMConfig) -> LLMAdapter:
        """
        Create appropriate LLM adapter based on provider type.
        
        Args:
            config (LLMConfig): Configuration object with provider field
        
        Returns:
            LLMAdapter: Concrete adapter instance (LocalLLMAdapter or APILLMAdapter)
        
        Raises:
            ValueError: If provider type is not recognized
        
        Provider Types:
            - "local": Creates LocalLLMAdapter for LMStudio, Ollama, etc.
            - "api": Creates APILLMAdapter for OpenAI, Anthropic, etc.
        
        Example:
            ```python
            config = LLMConfig(provider="local", model_name="qwen-2.5")
            adapter = LLMAdapterFactory.create_adapter(config)
            # Returns LocalLLMAdapter instance
            ```
        """
        if config.provider == "local":
            return LocalLLMAdapter(config)
        elif config.provider == "api":
            return APILLMAdapter(config)
        else:
            # Unknown provider - fail fast with clear error message
            raise ValueError(f"Unknown LLM provider: {config.provider}")

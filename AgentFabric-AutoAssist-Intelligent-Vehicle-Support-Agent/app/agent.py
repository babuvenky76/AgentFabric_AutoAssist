"""
Agent Core Logic - AutoAssist Agent

This module implements the core agent logic for AutoAssist, managing
system prompts, guardrails, and the request lifecycle for vehicle support queries.

Key Features:
    - Domain-restricted system prompts (automotive only)
    - Safety guardrails (no financial/medical advice)
    - Input validation and sanitization
    - LLM adapter abstraction (swap models easily)
    - Comprehensive error handling

Architecture:
    The agent acts as an orchestrator between the API layer and the LLM,
    constructing prompts, managing context, and ensuring responses meet
    safety and quality standards.

Author: Babu Srinivasan
Project: AgentFabric AutoAssist
"""

import logging
from typing import Optional, Dict, Any
from app.config import AppConfig
from app.llm_adapter import LLMAdapterFactory

logger = logging.getLogger(__name__)


# ============================================================================
# SYSTEM PROMPT - SAFETY GUARDRAILS
# ============================================================================
# This prompt defines the agent's behavior, constraints, and safety rules.
# IMPORTANT: Modify carefully - changes affect all responses

SYSTEM_PROMPT = """You are AutoAssist, an automotive support agent for vehicle owners and service technicians.

Your responsibilities:
1. Provide contextual vehicle troubleshooting guidance
2. Explain vehicle features and maintenance procedures
3. Interpret warning indicators and error codes
4. Offer safe, practical solutions

GUARDRAILS:
- ONLY provide automotive-related assistance
- NEVER provide financial or medical advice
- NEVER speculate about unknown vehicle specifications
- ALWAYS prioritize safety in troubleshooting guidance
- ALWAYS recommend professional service for complex issues

Response Style:
- Be concise and clear
- Use numbered steps for procedures
- Recommend professional service when appropriate
- Maintain a professional, helpful tone
"""


# ============================================================================
# AGENT CLASS
# ============================================================================

class AutoAssistAgent:
    """
    Core agent logic for AutoAssist.
    
    This class orchestrates the interaction between user queries and the LLM,
    managing prompt construction, validation, and response processing.
    
    Attributes:
        config: Application configuration (LLM settings, timeouts, etc.)
        llm_adapter: Abstraction layer for LLM communication
        logger: Logger instance for tracking agent operations
        
    Example:
        >>> agent = AutoAssistAgent(config)
        >>> result = await agent.process_query("What is tire pressure?")
        >>> print(result["response"])
    """
    
    def __init__(self, config: AppConfig):
        """
        Initialize the AutoAssist agent.
        
        Args:
            config: Application configuration with LLM settings
        """
        self.config = config
        self.llm_adapter = LLMAdapterFactory.create_adapter(config.llm)
        self.logger = logging.getLogger(__name__)
    
    def construct_prompt(self, user_query: str) -> str:
        """
        Construct the complete prompt with system instructions and user query.
        
        This method combines the system prompt (guardrails and instructions)
        with the user's query to create the final prompt sent to the LLM.
        
        Args:
            user_query: The user's vehicle support question
            
        Returns:
            str: Complete prompt ready for LLM processing
            
        Example:
            >>> prompt = agent.construct_prompt("How do I check oil?")
            >>> # Returns: SYSTEM_PROMPT + "\n\nUser Query: How do I check oil?\n\n..."
        """
        return f"""{SYSTEM_PROMPT}

User Query: {user_query}

Provide a helpful, safety-first response:"""
    
    async def process_query(self, user_query: str) -> Dict[str, Any]:
        """
        Process user query through the agent pipeline.
        
        This is the main entry point for query processing. It handles:
        1. Input validation
        2. Prompt construction
        3. LLM communication (with retry logic)
        4. Response validation
        5. Error handling
        
        Args:
            user_query: User's vehicle support question (1-1000 chars)
            
        Returns:
            Dict containing:
                - status: "success" or "error"
                - query: Original user query
                - response: LLM-generated response (if successful)
                - error: Error message (if failed)
                - model: LLM model name used
                
        Raises:
            ValueError: If query is invalid (empty, too long, wrong type)
            RuntimeError: If LLM communication fails after retries
            
        Example:
            >>> result = await agent.process_query("What is tire pressure?")
            >>> if result["status"] == "success":
            ...     print(result["response"])
        """
        try:
            # ================================================================
            # STEP 1: INPUT VALIDATION
            # ================================================================
            # Validate query is non-empty string
            if not user_query or not isinstance(user_query, str):
                raise ValueError("Invalid query: must be non-empty string")
            
            # Enforce maximum length to prevent DoS attacks
            if len(user_query) > 1000:
                raise ValueError("Query too long: maximum 1000 characters")
            
            # ================================================================
            # STEP 2: PROMPT CONSTRUCTION
            # ================================================================
            # Combine system prompt with user query
            full_prompt = self.construct_prompt(user_query)
            
            # ================================================================
            # STEP 3: LLM GENERATION
            # ================================================================
            # Send to LLM (includes automatic retry logic in adapter)
            self.logger.info(f"Processing query: {user_query[:100]}...")
            response_text = await self.llm_adapter.generate(full_prompt)
            
            # ================================================================
            # STEP 4: RESPONSE VALIDATION
            # ================================================================
            # Ensure LLM returned a non-empty response
            if not response_text:
                raise RuntimeError("Empty response from LLM")
            
            # ================================================================
            # STEP 5: STRUCTURE RESPONSE
            # ================================================================
            # Return structured response for API
            result = {
                "status": "success",
                "query": user_query,
                "response": response_text,
                "model": self.config.llm.model_name,
            }
            
            return result
            
        except Exception as e:
            # ================================================================
            # ERROR HANDLING
            # ================================================================
            # Log error details for debugging (server-side only)
            self.logger.error(f"Query processing failed: {str(e)}")
            
            # Return structured error response
            return {
                "status": "error",
                "query": user_query,
                "error": str(e),
                "model": self.config.llm.model_name,
            }
    
    def validate_config(self) -> bool:
        """
        Validate agent configuration.
        
        Checks that the LLM adapter is properly configured with
        required settings (model name, endpoint, etc.).
        
        Returns:
            bool: True if configuration is valid, False otherwise
            
        Example:
            >>> if not agent.validate_config():
            ...     raise RuntimeError("Invalid configuration")
        """
        return self.llm_adapter.validate_config()

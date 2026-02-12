"""
Agent Core Logic - AutoAssist Agent
Manages system prompt, guardrails, and request lifecycle
"""

import logging
from typing import Optional, Dict, Any
from app.config import AppConfig
from app.llm_adapter import LLMAdapterFactory

logger = logging.getLogger(__name__)


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


class AutoAssistAgent:
    """Core agent logic for AutoAssist"""
    
    def __init__(self, config: AppConfig):
        self.config = config
        self.llm_adapter = LLMAdapterFactory.create_adapter(config.llm)
        self.logger = logging.getLogger(__name__)
    
    def construct_prompt(self, user_query: str) -> str:
        """Construct the complete prompt with system instructions"""
        return f"""{SYSTEM_PROMPT}

User Query: {user_query}

Provide a helpful, safety-first response:"""
    
    async def process_query(self, user_query: str) -> Dict[str, Any]:
        """Process user query through the agent pipeline"""
        try:
            # Validate input
            if not user_query or not isinstance(user_query, str):
                raise ValueError("Invalid query: must be non-empty string")
            
            if len(user_query) > 1000:
                raise ValueError("Query too long: maximum 1000 characters")
            
            # Construct prompt
            full_prompt = self.construct_prompt(user_query)
            
            # Generate response from LLM
            self.logger.info(f"Processing query: {user_query[:100]}...")
            response_text = await self.llm_adapter.generate(full_prompt)
            
            # Validate response
            if not response_text:
                raise RuntimeError("Empty response from LLM")
            
            # Structure response
            result = {
                "status": "success",
                "query": user_query,
                "response": response_text,
                "model": self.config.llm.model_name,
            }
            
            return result
            
        except Exception as e:
            self.logger.error(f"Query processing failed: {str(e)}")
            return {
                "status": "error",
                "query": user_query,
                "error": str(e),
                "model": self.config.llm.model_name,
            }
    
    def validate_config(self) -> bool:
        """Validate agent configuration"""
        return self.llm_adapter.validate_config()

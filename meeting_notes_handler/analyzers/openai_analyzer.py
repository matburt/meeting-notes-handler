"""OpenAI and OpenRouter LLM analyzer implementation."""

import json
import os
import time
from typing import List, Dict, Any, Optional
from datetime import datetime
import asyncio

import tiktoken
from openai import OpenAI, AsyncOpenAI
from jinja2 import Template

from .base_analyzer import (
    BaseAnalyzer, 
    MeetingContent, 
    AnalysisResult,
    WeeklySummary,
    PersonalSummary
)


class OpenAIAnalyzer(BaseAnalyzer):
    """OpenAI and OpenRouter analyzer implementation."""
    
    def __init__(self, config: Dict[str, Any]):
        """Initialize OpenAI analyzer.
        
        Args:
            config: Configuration containing api_key_env, model, base_url, etc.
        """
        super().__init__(config)
        
        # Get API key from environment
        api_key_env = config.get("api_key_env", "OPENAI_API_KEY")
        api_key = os.getenv(api_key_env)
        if not api_key:
            raise ValueError(f"API key not found in environment variable: {api_key_env}")
        
        # Set up base URL for OpenRouter if specified
        base_url = config.get("base_url")
        
        # Initialize OpenAI client
        if base_url:
            # OpenRouter or custom endpoint
            self.client = AsyncOpenAI(api_key=api_key, base_url=base_url)
            self.sync_client = OpenAI(api_key=api_key, base_url=base_url)
        else:
            # Standard OpenAI
            self.client = AsyncOpenAI(api_key=api_key)
            self.sync_client = OpenAI(api_key=api_key)
        
        # Initialize tokenizer for cost estimation
        try:
            self.tokenizer = tiktoken.encoding_for_model(self.model)
        except KeyError:
            # Fallback to cl100k_base for unknown models
            self.tokenizer = tiktoken.get_encoding("cl100k_base")
    
    async def analyze_single_meeting(
        self, 
        meeting: MeetingContent, 
        prompt_template: str,
        user_context: Optional[Dict[str, Any]] = None
    ) -> AnalysisResult:
        """Analyze a single meeting using OpenAI.
        
        Args:
            meeting: Meeting content to analyze
            prompt_template: Jinja2 template string for the prompt
            user_context: Optional user context (name, aliases, etc.)
            
        Returns:
            Structured analysis result
        """
        start_time = time.time()
        
        # Render prompt template
        template = Template(prompt_template)
        prompt = template.render(
            meeting=meeting,
            user_context=user_context or {}
        )
        
        try:
            # Make API call to OpenAI
            response = await self.client.chat.completions.create(
                model=self.model,
                messages=[
                    {
                        "role": "system",
                        "content": "You are an expert meeting analyst. Provide clear, actionable insights from meeting content. Return responses in valid JSON format when requested."
                    },
                    {
                        "role": "user", 
                        "content": prompt
                    }
                ],
                temperature=self.temperature,
                max_tokens=self.max_tokens
            )
            
            processing_time = time.time() - start_time
            
            # Extract response content
            content = response.choices[0].message.content
            
            # Try to parse as JSON, fallback to plain text
            try:
                parsed_response = json.loads(content)
                
                return AnalysisResult(
                    summary=parsed_response.get("summary", ""),
                    action_items=parsed_response.get("action_items", []),
                    key_decisions=parsed_response.get("key_decisions", []),
                    important_points=parsed_response.get("important_points", []),
                    personal_mentions=parsed_response.get("personal_mentions", []),
                    confidence_score=parsed_response.get("confidence_score", 0.8),
                    processing_time=processing_time,
                    model_used=self.model,
                    timestamp=datetime.now()
                )
                
            except json.JSONDecodeError:
                # Fallback to plain text response
                return AnalysisResult(
                    summary=content,
                    action_items=[],
                    key_decisions=[],
                    important_points=[],
                    personal_mentions=[],
                    confidence_score=0.7,
                    processing_time=processing_time,
                    model_used=self.model,
                    timestamp=datetime.now()
                )
                
        except Exception as e:
            raise RuntimeError(f"OpenAI API call failed: {str(e)}")
    
    async def analyze_meetings_batch(
        self,
        meetings: List[MeetingContent],
        prompt_template: str,
        user_context: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """Analyze multiple meetings in a batch.
        
        Args:
            meetings: List of meetings to analyze
            prompt_template: Jinja2 template string for the prompt
            user_context: Optional user context
            
        Returns:
            Structured analysis result
        """
        start_time = time.time()
        
        # Render prompt template with all meetings
        template = Template(prompt_template)
        prompt = template.render(
            meetings=meetings,
            user_context=user_context or {}
        )
        
        try:
            # Make API call to OpenAI
            response = await self.client.chat.completions.create(
                model=self.model,
                messages=[
                    {
                        "role": "system",
                        "content": "You are an expert meeting analyst. Analyze multiple meetings and provide comprehensive insights. Return responses in valid JSON format when requested."
                    },
                    {
                        "role": "user",
                        "content": prompt
                    }
                ],
                temperature=self.temperature,
                max_tokens=self.max_tokens
            )
            
            processing_time = time.time() - start_time
            
            # Extract and parse response
            content = response.choices[0].message.content
            
            try:
                parsed_response = json.loads(content)
                parsed_response["processing_time"] = processing_time
                parsed_response["model_used"] = self.model
                parsed_response["timestamp"] = datetime.now().isoformat()
                return parsed_response
                
            except json.JSONDecodeError:
                # Fallback structure
                return {
                    "summary": content,
                    "processing_time": processing_time,
                    "model_used": self.model,
                    "timestamp": datetime.now().isoformat()
                }
                
        except Exception as e:
            raise RuntimeError(f"OpenAI API call failed: {str(e)}")
    
    def count_tokens(self, text: str) -> int:
        """Count tokens in text for cost estimation.
        
        Args:
            text: Text to count tokens for
            
        Returns:
            Number of tokens
        """
        return len(self.tokenizer.encode(text))
    
    def estimate_cost(self, prompt_tokens: int, completion_tokens: int) -> float:
        """Estimate cost for token usage.
        
        Args:
            prompt_tokens: Number of input tokens
            completion_tokens: Number of output tokens
            
        Returns:
            Estimated cost in USD
        """
        # Default pricing for GPT-4 (can be customized per model)
        pricing = {
            "gpt-4": {"input": 0.03, "output": 0.06},  # per 1K tokens
            "gpt-4-turbo": {"input": 0.01, "output": 0.03},
            "gpt-4-turbo-preview": {"input": 0.01, "output": 0.03},
            "gpt-3.5-turbo": {"input": 0.001, "output": 0.002},
        }
        
        # Get pricing for current model, fallback to GPT-4 pricing
        model_pricing = pricing.get(self.model, pricing["gpt-4"])
        
        input_cost = (prompt_tokens / 1000) * model_pricing["input"]
        output_cost = (completion_tokens / 1000) * model_pricing["output"]
        
        return input_cost + output_cost
    
    def validate_config(self) -> bool:
        """Validate that required configuration is present.
        
        Returns:
            True if configuration is valid
        """
        if not super().validate_config():
            return False
        
        # Check if API key exists in environment
        api_key_env = self.config.get("api_key_env", "OPENAI_API_KEY")
        return os.getenv(api_key_env) is not None
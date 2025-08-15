"""Base abstract class for LLM analyzers."""

from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import List, Dict, Any, Optional
from datetime import datetime


@dataclass
class MeetingContent:
    """Container for meeting content and metadata."""
    title: str
    date: datetime
    content: str
    file_path: str
    attendees: Optional[List[str]] = None


@dataclass
class AnalysisResult:
    """Structured result from LLM analysis."""
    summary: str
    action_items: List[Dict[str, Any]]
    key_decisions: List[str]
    important_points: List[str]
    personal_mentions: List[str]
    confidence_score: float
    processing_time: float
    model_used: str
    timestamp: datetime


@dataclass
class WeeklySummary:
    """Summary of a week's worth of meetings."""
    week_identifier: str
    most_important_decisions: List[str]
    key_themes: List[str]
    critical_action_items: List[Dict[str, Any]]
    notable_risks: List[str]
    meetings_analyzed: int
    analysis_timestamp: datetime


@dataclass
class PersonalSummary:
    """Personal action items and discussions for a user."""
    user_name: str
    action_items: List[Dict[str, Any]]
    discussions_involved: List[Dict[str, Any]]
    meetings_with_involvement: List[str]
    total_meetings_analyzed: int
    analysis_timestamp: datetime


class BaseAnalyzer(ABC):
    """Abstract base class for LLM analyzers."""
    
    def __init__(self, config: Dict[str, Any]):
        """Initialize analyzer with configuration.
        
        Args:
            config: Configuration dictionary containing API keys, models, etc.
        """
        self.config = config
        self.model = config.get("model", "default")
        self.temperature = config.get("temperature", 0.3)
        self.max_tokens = config.get("max_tokens", 4000)
    
    @abstractmethod
    async def analyze_single_meeting(
        self, 
        meeting: MeetingContent, 
        prompt_template: str,
        user_context: Optional[Dict[str, Any]] = None
    ) -> AnalysisResult:
        """Analyze a single meeting with given prompt template.
        
        Args:
            meeting: Meeting content to analyze
            prompt_template: Jinja2 template string for the prompt
            user_context: Optional user context (name, aliases, etc.)
            
        Returns:
            Structured analysis result
        """
        pass
    
    @abstractmethod
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
            Structured analysis result (format depends on prompt)
        """
        pass
    
    @abstractmethod
    def count_tokens(self, text: str) -> int:
        """Count tokens in text for cost estimation.
        
        Args:
            text: Text to count tokens for
            
        Returns:
            Number of tokens
        """
        pass
    
    @abstractmethod
    def estimate_cost(self, prompt_tokens: int, completion_tokens: int) -> float:
        """Estimate cost for token usage.
        
        Args:
            prompt_tokens: Number of input tokens
            completion_tokens: Number of output tokens
            
        Returns:
            Estimated cost in USD
        """
        pass
    
    def validate_config(self) -> bool:
        """Validate that required configuration is present.
        
        Returns:
            True if configuration is valid
        """
        required_keys = ["api_key_env", "model"]
        return all(key in self.config for key in required_keys)
    
    def get_provider_name(self) -> str:
        """Get the name of this provider.
        
        Returns:
            Provider name string
        """
        return self.__class__.__name__.replace("Analyzer", "").lower()
"""Factory for creating LLM analyzer instances."""

from typing import Dict, Any, Type
import logging

from .base_analyzer import BaseAnalyzer
from .openai_analyzer import OpenAIAnalyzer

logger = logging.getLogger(__name__)


class AnalyzerFactory:
    """Factory class for creating analyzer instances."""
    
    # Registry of available analyzers
    _analyzers: Dict[str, Type[BaseAnalyzer]] = {
        "openai": OpenAIAnalyzer,
        "openrouter": OpenAIAnalyzer,  # OpenRouter uses OpenAI-compatible API
    }
    
    @classmethod
    def create_analyzer(cls, provider: str, config: Dict[str, Any]) -> BaseAnalyzer:
        """Create an analyzer instance for the specified provider.
        
        Args:
            provider: LLM provider name (openai, anthropic, gemini, openrouter)
            config: Configuration dictionary for the provider
            
        Returns:
            Configured analyzer instance
            
        Raises:
            ValueError: If provider is not supported
            RuntimeError: If analyzer creation fails
        """
        provider = provider.lower()
        
        if provider not in cls._analyzers:
            available = ", ".join(cls._analyzers.keys())
            raise ValueError(
                f"Unsupported provider: {provider}. "
                f"Available providers: {available}"
            )
        
        analyzer_class = cls._analyzers[provider]
        
        try:
            analyzer = analyzer_class(config)
            
            # Validate configuration
            if not analyzer.validate_config():
                raise RuntimeError(
                    f"Invalid configuration for {provider} provider. "
                    f"Check API keys and required settings."
                )
            
            logger.info(f"Created {provider} analyzer with model: {analyzer.model}")
            return analyzer
            
        except Exception as e:
            raise RuntimeError(f"Failed to create {provider} analyzer: {str(e)}")
    
    @classmethod
    def register_analyzer(cls, provider: str, analyzer_class: Type[BaseAnalyzer]) -> None:
        """Register a new analyzer provider.
        
        Args:
            provider: Provider name
            analyzer_class: Analyzer class that implements BaseAnalyzer
        """
        if not issubclass(analyzer_class, BaseAnalyzer):
            raise ValueError(
                f"Analyzer class must inherit from BaseAnalyzer, "
                f"got: {analyzer_class.__name__}"
            )
        
        cls._analyzers[provider.lower()] = analyzer_class
        logger.info(f"Registered analyzer for provider: {provider}")
    
    @classmethod
    def get_available_providers(cls) -> list[str]:
        """Get list of available provider names.
        
        Returns:
            List of supported provider names
        """
        return list(cls._analyzers.keys())
    
    @classmethod
    def get_analyzer_info(cls, provider: str) -> Dict[str, Any]:
        """Get information about a specific analyzer.
        
        Args:
            provider: Provider name
            
        Returns:
            Dictionary with analyzer information
            
        Raises:
            ValueError: If provider is not supported
        """
        provider = provider.lower()
        
        if provider not in cls._analyzers:
            raise ValueError(f"Unsupported provider: {provider}")
        
        analyzer_class = cls._analyzers[provider]
        
        return {
            "provider": provider,
            "class_name": analyzer_class.__name__,
            "module": analyzer_class.__module__,
            "description": analyzer_class.__doc__ or "No description available",
        }


# Convenience function for quick analyzer creation
def create_analyzer(provider: str, config: Dict[str, Any]) -> BaseAnalyzer:
    """Convenience function to create an analyzer.
    
    Args:
        provider: LLM provider name
        config: Configuration dictionary
        
    Returns:
        Configured analyzer instance
    """
    return AnalyzerFactory.create_analyzer(provider, config)
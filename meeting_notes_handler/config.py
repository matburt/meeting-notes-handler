"""Configuration management for the meeting notes summarizer."""

import os
import yaml
from pathlib import Path
from typing import Dict, Any, Optional
from dotenv import load_dotenv

class Config:
    """Configuration manager for the meeting notes summarizer."""
    
    def __init__(self, config_file: Optional[str] = None):
        """Initialize configuration.
        
        Args:
            config_file: Path to configuration file. Defaults to config.yaml in project root.
        """
        load_dotenv()
        
        self.project_root = Path(__file__).parent.parent
        self.config_file = config_file or self.project_root / "config.yaml"
        self.meeting_notes_dir = self.project_root / "meeting_notes"
        
        self._config = self._load_config()
    
    def _load_config(self) -> Dict[str, Any]:
        """Load configuration from file and environment variables."""
        config = {
            # Default configuration
            "google": {
                "credentials_file": os.getenv("GOOGLE_CREDENTIALS_FILE", "credentials.json"),
                "token_file": os.getenv("GOOGLE_TOKEN_FILE", "token.json"),
                "scopes": [
                    "https://www.googleapis.com/auth/calendar.readonly",
                    "https://www.googleapis.com/auth/drive.readonly",
                    "https://www.googleapis.com/auth/documents.readonly"
                ]
            },
            "output": {
                "directory": str(self.meeting_notes_dir),
                "file_format": "meeting_{date}_{time}.md",
                "date_format": "%Y%m%d",
                "time_format": "%H%M%S"
            },
            "calendar": {
                "keywords": ["meet.google.com", "Google Meet"],
                "days_back": 7
            },
            "docs": {
                "use_native_export": True,  # Use Google Docs native Markdown export
                "fallback_to_manual": True  # Fall back to manual parsing if native export fails
            },
            "logging": {
                "level": os.getenv("LOG_LEVEL", "INFO"),
                "format": "%(asctime)s - %(name)s - %(levelname)s - %(message)s"
            },
            "analysis": {
                "provider": os.getenv("LLM_PROVIDER", "openai"),
                "templates_dir": str(self.project_root / "meeting_notes_handler" / "templates"),
                
                # Content filtering settings (NEW)
                "content_filter": "gemini-only",     # Default to Gemini notes only
                "include_embedded_docs": False,      # Exclude embedded documents by default
                "exclude_transcripts": True,         # Always exclude transcripts by default
                
                # Cost protection settings (NEW)
                "max_input_tokens": 100000,          # Safety limit for input tokens
                "cost_warning_threshold": 5.0,       # Warn if cost > $5
                "require_confirmation": True,        # Require confirmation for expensive ops
                
                # Chunking settings (NEW)
                "chunk_strategy": "by-meeting",      # Process meetings individually
                "max_chunk_size": 50000,             # Max tokens per chunk
                
                "openai": {
                    "api_key_env": "OPENAI_API_KEY",
                    "model": "gpt-4-turbo-preview", 
                    "temperature": 0.3,
                    "max_tokens": 16000                # Increased from 4000
                },
                "anthropic": {
                    "api_key_env": "ANTHROPIC_API_KEY",
                    "model": "claude-3-opus-20240229",
                    "temperature": 0.3,
                    "max_tokens": 16000                # Increased from 4000
                },
                "gemini": {
                    "api_key_env": "GEMINI_API_KEY",
                    "model": "gemini-pro",
                    "temperature": 0.3,
                    "max_tokens": 16000                # Increased from 4000
                },
                "openrouter": {
                    "api_key_env": "OPENROUTER_API_KEY",
                    "model": "anthropic/claude-3-opus",
                    "base_url": "https://openrouter.ai/api/v1",
                    "temperature": 0.3,
                    "max_tokens": 16000                # Increased from 4000
                },
                "user_context": {
                    "user_name": os.getenv("USER_NAME", ""),
                    "user_aliases": []
                }
            }
        }
        
        # Load from file if it exists
        if self.config_file.exists():
            with open(self.config_file, 'r') as f:
                file_config = yaml.safe_load(f) or {}
                config.update(file_config)
        
        return config
    
    def get(self, key: str, default: Any = None) -> Any:
        """Get configuration value by dot notation key."""
        keys = key.split('.')
        value = self._config
        
        for k in keys:
            if isinstance(value, dict) and k in value:
                value = value[k]
            else:
                return default
        
        return value
    
    def save(self) -> None:
        """Save current configuration to file."""
        with open(self.config_file, 'w') as f:
            yaml.safe_dump(self._config, f, default_flow_style=False)
    
    @property
    def google_credentials_file(self) -> Path:
        """Path to Google credentials file."""
        creds_file = self.get("google.credentials_file")
        if not os.path.isabs(creds_file):
            return self.project_root / creds_file
        return Path(creds_file)
    
    @property
    def google_token_file(self) -> Path:
        """Path to Google token file."""
        token_file = self.get("google.token_file")
        if not os.path.isabs(token_file):
            return self.project_root / token_file
        return Path(token_file)
    
    @property
    def google_scopes(self) -> list:
        """Google API scopes."""
        return self.get("google.scopes", [])
    
    @property
    def output_directory(self) -> Path:
        """Output directory for meeting notes."""
        return Path(self.get("output.directory"))
    
    @property
    def calendar_keywords(self) -> list:
        """Keywords to identify Google Meet meetings."""
        return self.get("calendar.keywords", [])
    
    @property
    def days_back(self) -> int:
        """Number of days back to search for meetings."""
        return self.get("calendar.days_back", 7)
    
    @property
    def use_native_export(self) -> bool:
        """Whether to use Google Docs native Markdown export."""
        return self.get("docs.use_native_export", True)
    
    @property
    def fallback_to_manual(self) -> bool:
        """Whether to fall back to manual parsing if native export fails."""
        return self.get("docs.fallback_to_manual", True)
    
    # Analysis configuration properties
    
    @property
    def analysis_provider(self) -> str:
        """Current LLM provider for analysis."""
        return self.get("analysis.provider", "openai")
    
    @property
    def templates_directory(self) -> Path:
        """Directory containing prompt templates."""
        return Path(self.get("analysis.templates_dir"))
    
    def get_provider_config(self, provider: Optional[str] = None) -> Dict[str, Any]:
        """Get configuration for a specific LLM provider.
        
        Args:
            provider: Provider name. If None, uses current provider.
            
        Returns:
            Provider configuration dictionary
        """
        provider = provider or self.analysis_provider
        return self.get(f"analysis.{provider}", {})
    
    @property
    def user_context(self) -> Dict[str, Any]:
        """User context for personalized analysis."""
        return self.get("analysis.user_context", {})
    
    # Content filtering configuration properties
    
    @property
    def content_filter(self) -> str:
        """Default content filtering mode."""
        return self.get("analysis.content_filter", "gemini-only")
    
    @property
    def include_embedded_docs(self) -> bool:
        """Whether to include embedded documents by default."""
        return self.get("analysis.include_embedded_docs", False)
    
    @property
    def exclude_transcripts(self) -> bool:
        """Whether to exclude transcripts by default."""
        return self.get("analysis.exclude_transcripts", True)
    
    @property
    def max_input_tokens(self) -> int:
        """Maximum number of input tokens allowed per analysis."""
        return self.get("analysis.max_input_tokens", 100000)
    
    @property
    def cost_warning_threshold(self) -> float:
        """Cost threshold for displaying warnings (USD)."""
        return self.get("analysis.cost_warning_threshold", 5.0)
    
    @property
    def require_confirmation(self) -> bool:
        """Whether to require user confirmation for expensive operations."""
        return self.get("analysis.require_confirmation", True)
    
    @property
    def chunk_strategy(self) -> str:
        """Strategy for chunking large content."""
        return self.get("analysis.chunk_strategy", "by-meeting")
    
    @property
    def max_chunk_size(self) -> int:
        """Maximum tokens per chunk."""
        return self.get("analysis.max_chunk_size", 50000)
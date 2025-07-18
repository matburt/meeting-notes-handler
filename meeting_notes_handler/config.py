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
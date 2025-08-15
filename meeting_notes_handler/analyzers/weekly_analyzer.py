"""Weekly meeting summary analyzer."""

import os
import logging
from pathlib import Path
from typing import List, Dict, Any, Optional
from datetime import datetime, timedelta
import json

from .base_analyzer import BaseAnalyzer, MeetingContent, WeeklySummary
from .content_extractor import MeetingContentExtractor

logger = logging.getLogger(__name__)


class WeeklyAnalyzer:
    """Analyzer for generating weekly summaries of meetings."""
    
    def __init__(self, llm_analyzer: BaseAnalyzer, templates_dir: str, 
                 content_filter: str = "gemini-only", include_docs: bool = False):
        """Initialize weekly analyzer.
        
        Args:
            llm_analyzer: Configured LLM analyzer instance
            templates_dir: Path to prompt templates directory
            content_filter: Type of content filtering ('gemini-only', 'no-transcripts', 'all')
            include_docs: Whether to include embedded documents
        """
        self.llm_analyzer = llm_analyzer
        self.templates_dir = Path(templates_dir)
        self.content_filter = content_filter
        self.include_docs = include_docs
        
        # Initialize content extractor
        self.content_extractor = MeetingContentExtractor()
        
        # Load the weekly summary template
        template_path = self.templates_dir / "weekly_summary.jinja2"
        if not template_path.exists():
            raise FileNotFoundError(f"Weekly summary template not found: {template_path}")
        
        with open(template_path, 'r', encoding='utf-8') as f:
            self.prompt_template = f.read()
    
    def load_meetings_from_directory(self, directory_path: str) -> List[MeetingContent]:
        """Load all meeting files from a directory.
        
        Args:
            directory_path: Path to directory containing meeting files
            
        Returns:
            List of MeetingContent objects
        """
        meetings = []
        directory = Path(directory_path)
        
        if not directory.exists():
            logger.warning(f"Directory not found: {directory_path}")
            return meetings
        
        # Find all markdown files that look like meeting notes
        for file_path in directory.glob("meeting_*.md"):
            try:
                meeting = self._parse_meeting_file(file_path)
                if meeting:
                    meetings.append(meeting)
            except Exception as e:
                logger.error(f"Failed to parse meeting file {file_path}: {str(e)}")
        
        # Sort by date
        meetings.sort(key=lambda m: m.date)
        return meetings
    
    def _parse_meeting_file(self, file_path: Path) -> Optional[MeetingContent]:
        """Parse a meeting file into MeetingContent with content filtering.
        
        Args:
            file_path: Path to meeting file
            
        Returns:
            MeetingContent object or None if parsing fails
        """
        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                raw_content = f.read()
            
            # Apply content filtering
            filtered_content = self.content_extractor.extract_content(
                raw_content, 
                self.content_filter, 
                self.include_docs
            )
            
            # Extract title and date from filename
            # Expected format: meeting_YYYYMMDD_HHMMSS_title.md
            filename = file_path.stem
            parts = filename.split('_')
            
            if len(parts) >= 3:
                date_str = parts[1]
                time_str = parts[2]
                title = '_'.join(parts[3:]) if len(parts) > 3 else "Meeting"
                
                # Parse date and time
                date_time_str = f"{date_str}_{time_str}"
                meeting_date = datetime.strptime(date_time_str, "%Y%m%d_%H%M%S")
                
                return MeetingContent(
                    title=title.replace('_', ' ').title(),
                    date=meeting_date,
                    content=filtered_content,
                    file_path=str(file_path)
                )
            else:
                logger.warning(f"Unexpected filename format: {filename}")
                return None
                
        except Exception as e:
            logger.error(f"Error parsing meeting file {file_path}: {str(e)}")
            return None
    
    async def analyze_week(
        self, 
        week_directory: str,
        output_file: Optional[str] = None
    ) -> WeeklySummary:
        """Analyze all meetings in a week directory.
        
        Args:
            week_directory: Path to week directory (e.g., "2024-W15")
            output_file: Optional path to save analysis results
            
        Returns:
            WeeklySummary object with analysis results
        """
        logger.info(f"Analyzing meetings in week directory: {week_directory}")
        
        # Load meetings from directory
        meetings = self.load_meetings_from_directory(week_directory)
        
        if not meetings:
            logger.warning(f"No meetings found in directory: {week_directory}")
            return WeeklySummary(
                week_identifier=Path(week_directory).name,
                most_important_decisions=[],
                key_themes=[],
                critical_action_items=[],
                notable_risks=[],
                meetings_analyzed=0,
                analysis_timestamp=datetime.now()
            )
        
        logger.info(f"Found {len(meetings)} meetings to analyze")
        
        # Analyze using LLM
        try:
            result = await self.llm_analyzer.analyze_meetings_batch(
                meetings=meetings,
                prompt_template=self.prompt_template
            )
            
            # Parse the structured response
            week_summary = WeeklySummary(
                week_identifier=Path(week_directory).name,
                most_important_decisions=result.get("most_important_decisions", []),
                key_themes=result.get("key_themes", []),
                critical_action_items=result.get("critical_action_items", []),
                notable_risks=result.get("notable_risks", []),
                meetings_analyzed=len(meetings),
                analysis_timestamp=datetime.now()
            )
            
            # Save to file if requested
            if output_file:
                await self._save_analysis(week_summary, result, output_file)
            
            logger.info(f"Successfully analyzed {len(meetings)} meetings")
            return week_summary
            
        except Exception as e:
            logger.error(f"Failed to analyze meetings: {str(e)}")
            raise
    
    async def analyze_last_n_days(
        self, 
        base_directory: str,
        days: int = 7,
        output_file: Optional[str] = None
    ) -> WeeklySummary:
        """Analyze meetings from the last N days across multiple week directories.
        
        Args:
            base_directory: Base directory containing week subdirectories
            days: Number of days back to analyze
            output_file: Optional path to save analysis results
            
        Returns:
            WeeklySummary object with analysis results
        """
        end_date = datetime.now()
        start_date = end_date - timedelta(days=days)
        
        logger.info(f"Analyzing meetings from {start_date.date()} to {end_date.date()}")
        
        # Collect meetings from relevant week directories
        all_meetings = []
        base_path = Path(base_directory)
        
        # Find all week directories that might contain relevant meetings
        for week_dir in base_path.glob("????-W??"):
            meetings = self.load_meetings_from_directory(str(week_dir))
            
            # Filter meetings within date range
            for meeting in meetings:
                if start_date <= meeting.date <= end_date:
                    all_meetings.append(meeting)
        
        if not all_meetings:
            logger.warning(f"No meetings found in the last {days} days")
            return WeeklySummary(
                week_identifier=f"Last {days} days",
                most_important_decisions=[],
                key_themes=[],
                critical_action_items=[],
                notable_risks=[],
                meetings_analyzed=0,
                analysis_timestamp=datetime.now()
            )
        
        # Sort by date
        all_meetings.sort(key=lambda m: m.date)
        logger.info(f"Found {len(all_meetings)} meetings in the last {days} days")
        
        # Analyze using LLM
        try:
            result = await self.llm_analyzer.analyze_meetings_batch(
                meetings=all_meetings,
                prompt_template=self.prompt_template
            )
            
            # Parse the structured response
            week_summary = WeeklySummary(
                week_identifier=f"Last {days} days",
                most_important_decisions=result.get("most_important_decisions", []),
                key_themes=result.get("key_themes", []),
                critical_action_items=result.get("critical_action_items", []),
                notable_risks=result.get("notable_risks", []),
                meetings_analyzed=len(all_meetings),
                analysis_timestamp=datetime.now()
            )
            
            # Save to file if requested
            if output_file:
                await self._save_analysis(week_summary, result, output_file)
            
            logger.info(f"Successfully analyzed {len(all_meetings)} meetings from last {days} days")
            return week_summary
            
        except Exception as e:
            logger.error(f"Failed to analyze meetings: {str(e)}")
            raise
    
    async def _save_analysis(
        self, 
        summary: WeeklySummary, 
        raw_result: Dict[str, Any], 
        output_file: str
    ) -> None:
        """Save analysis results to file.
        
        Args:
            summary: WeeklySummary object
            raw_result: Raw LLM response
            output_file: Path to output file
        """
        try:
            output_path = Path(output_file)
            output_path.parent.mkdir(parents=True, exist_ok=True)
            
            # Create comprehensive output
            output_data = {
                "week_identifier": summary.week_identifier,
                "analysis_timestamp": summary.analysis_timestamp.isoformat(),
                "meetings_analyzed": summary.meetings_analyzed,
                "most_important_decisions": summary.most_important_decisions,
                "key_themes": summary.key_themes,
                "critical_action_items": summary.critical_action_items,
                "notable_risks": summary.notable_risks,
                "summary": raw_result.get("summary", ""),
                "confidence_score": raw_result.get("confidence_score", 0.0),
                "model_used": raw_result.get("model_used", "unknown"),
                "processing_time": raw_result.get("processing_time", 0.0)
            }
            
            with open(output_path, 'w', encoding='utf-8') as f:
                json.dump(output_data, f, indent=2, ensure_ascii=False)
            
            logger.info(f"Analysis saved to: {output_file}")
            
        except Exception as e:
            logger.error(f"Failed to save analysis to {output_file}: {str(e)}")
            raise
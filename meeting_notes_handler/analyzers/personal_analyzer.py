"""Personal action item and discussion analyzer."""

import os
import logging
from pathlib import Path
from typing import List, Dict, Any, Optional
from datetime import datetime, timedelta
import json

from .base_analyzer import BaseAnalyzer, MeetingContent, PersonalSummary
from .content_extractor import MeetingContentExtractor

logger = logging.getLogger(__name__)


class PersonalAnalyzer:
    """Analyzer for finding user's action items and discussions."""
    
    def __init__(self, llm_analyzer: BaseAnalyzer, templates_dir: str, 
                 content_filter: str = "gemini-only", include_docs: bool = False):
        """Initialize personal analyzer.
        
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
        
        # Load the personal actions template
        template_path = self.templates_dir / "personal_actions.jinja2"
        if not template_path.exists():
            raise FileNotFoundError(f"Personal actions template not found: {template_path}")
        
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
        
        # Sort by date (newest first for personal analysis)
        meetings.sort(key=lambda m: m.date, reverse=True)
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
    
    async def find_personal_meetings(
        self,
        meetings: List[MeetingContent],
        user_context: Dict[str, Any],
        min_relevance: float = 0.3,
        output_file: Optional[str] = None
    ) -> PersonalSummary:
        """Find meetings with personal relevance for the user.
        
        Args:
            meetings: List of meetings to analyze
            user_context: User context with name and aliases
            min_relevance: Minimum relevance score to include (0.0-1.0)
            output_file: Optional path to save analysis results
            
        Returns:
            PersonalSummary object with relevant meetings and actions
        """
        logger.info(f"Analyzing {len(meetings)} meetings for personal relevance")
        
        all_action_items = []
        all_discussions = []
        relevant_meetings = []
        
        # Analyze each meeting individually for personal relevance
        for meeting in meetings:
            try:
                logger.debug(f"Analyzing meeting: {meeting.title}")
                
                result = await self.llm_analyzer.analyze_single_meeting(
                    meeting=meeting,
                    prompt_template=self.prompt_template,
                    user_context=user_context
                )
                
                # Parse the structured response
                if hasattr(result, 'summary') and result.summary:
                    try:
                        # Try to parse as JSON from the summary field
                        parsed = json.loads(result.summary)
                    except json.JSONDecodeError:
                        # If not JSON, skip this meeting
                        logger.warning(f"Could not parse JSON response for meeting: {meeting.title}")
                        continue
                else:
                    logger.warning(f"No summary in result for meeting: {meeting.title}")
                    continue
                
                # Check relevance score
                relevance_score = parsed.get("relevance_score", 0.0)
                
                if relevance_score >= min_relevance:
                    relevant_meetings.append(meeting.title)
                    
                    # Collect action items
                    action_items = parsed.get("action_items", [])
                    for item in action_items:
                        item["source_meeting"] = meeting.title
                        item["meeting_date"] = meeting.date.isoformat()
                        all_action_items.append(item)
                    
                    # Collect discussions
                    discussions = parsed.get("discussions_involved", [])
                    for discussion in discussions:
                        discussion["source_meeting"] = meeting.title
                        discussion["meeting_date"] = meeting.date.isoformat()
                        all_discussions.append(discussion)
                    
                    logger.info(f"Found relevant meeting: {meeting.title} (relevance: {relevance_score:.2f})")
                
            except Exception as e:
                logger.error(f"Failed to analyze meeting {meeting.title}: {str(e)}")
                continue
        
        # Create personal summary
        personal_summary = PersonalSummary(
            user_name=user_context.get("user_name", "Unknown"),
            action_items=all_action_items,
            discussions_involved=all_discussions,
            meetings_with_involvement=relevant_meetings,
            total_meetings_analyzed=len(meetings),
            analysis_timestamp=datetime.now()
        )
        
        # Save to file if requested
        if output_file:
            await self._save_personal_analysis(personal_summary, output_file)
        
        logger.info(f"Found {len(relevant_meetings)} relevant meetings with {len(all_action_items)} action items")
        return personal_summary
    
    async def analyze_personal_week(
        self,
        week_directory: str,
        user_context: Dict[str, Any],
        min_relevance: float = 0.3,
        output_file: Optional[str] = None
    ) -> PersonalSummary:
        """Analyze personal involvement in a week's meetings.
        
        Args:
            week_directory: Path to week directory
            user_context: User context with name and aliases
            min_relevance: Minimum relevance score to include
            output_file: Optional path to save analysis results
            
        Returns:
            PersonalSummary object
        """
        logger.info(f"Analyzing personal involvement in week: {week_directory}")
        
        # Load meetings from directory
        meetings = self.load_meetings_from_directory(week_directory)
        
        if not meetings:
            logger.warning(f"No meetings found in directory: {week_directory}")
            return PersonalSummary(
                user_name=user_context.get("user_name", "Unknown"),
                action_items=[],
                discussions_involved=[],
                meetings_with_involvement=[],
                total_meetings_analyzed=0,
                analysis_timestamp=datetime.now()
            )
        
        return await self.find_personal_meetings(
            meetings=meetings,
            user_context=user_context,
            min_relevance=min_relevance,
            output_file=output_file
        )
    
    async def analyze_personal_last_n_days(
        self,
        base_directory: str,
        user_context: Dict[str, Any],
        days: int = 30,
        min_relevance: float = 0.3,
        output_file: Optional[str] = None
    ) -> PersonalSummary:
        """Analyze personal involvement in meetings from the last N days.
        
        Args:
            base_directory: Base directory containing week subdirectories
            user_context: User context with name and aliases
            days: Number of days back to analyze
            min_relevance: Minimum relevance score to include
            output_file: Optional path to save analysis results
            
        Returns:
            PersonalSummary object
        """
        end_date = datetime.now()
        start_date = end_date - timedelta(days=days)
        
        logger.info(f"Analyzing personal meetings from {start_date.date()} to {end_date.date()}")
        
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
            return PersonalSummary(
                user_name=user_context.get("user_name", "Unknown"),
                action_items=[],
                discussions_involved=[],
                meetings_with_involvement=[],
                total_meetings_analyzed=0,
                analysis_timestamp=datetime.now()
            )
        
        # Sort by date (newest first)
        all_meetings.sort(key=lambda m: m.date, reverse=True)
        
        return await self.find_personal_meetings(
            meetings=all_meetings,
            user_context=user_context,
            min_relevance=min_relevance,
            output_file=output_file
        )
    
    async def _save_personal_analysis(
        self,
        summary: PersonalSummary,
        output_file: str
    ) -> None:
        """Save personal analysis results to file.
        
        Args:
            summary: PersonalSummary object
            output_file: Path to output file
        """
        try:
            output_path = Path(output_file)
            output_path.parent.mkdir(parents=True, exist_ok=True)
            
            # Create comprehensive output
            output_data = {
                "user_name": summary.user_name,
                "analysis_timestamp": summary.analysis_timestamp.isoformat(),
                "total_meetings_analyzed": summary.total_meetings_analyzed,
                "meetings_with_involvement": summary.meetings_with_involvement,
                "action_items": summary.action_items,
                "discussions_involved": summary.discussions_involved,
                "summary_stats": {
                    "total_action_items": len(summary.action_items),
                    "total_discussions": len(summary.discussions_involved),
                    "involvement_rate": len(summary.meetings_with_involvement) / max(summary.total_meetings_analyzed, 1)
                }
            }
            
            with open(output_path, 'w', encoding='utf-8') as f:
                json.dump(output_data, f, indent=2, ensure_ascii=False)
            
            logger.info(f"Personal analysis saved to: {output_file}")
            
        except Exception as e:
            logger.error(f"Failed to save personal analysis to {output_file}: {str(e)}")
            raise
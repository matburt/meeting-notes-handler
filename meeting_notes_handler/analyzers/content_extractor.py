"""Content extraction utilities for meeting analysis.

This module provides tools to extract different types of content from meeting files,
allowing users to analyze only Gemini notes, exclude transcripts, or filter other content.
"""

import re
import tiktoken
from typing import Dict, Any, List, Tuple
from pathlib import Path


class MeetingContentExtractor:
    """Extracts and filters different types of content from meeting files."""
    
    def __init__(self, model_name: str = "gpt-4"):
        """Initialize the content extractor.
        
        Args:
            model_name: Model name for token counting (default: gpt-4)
        """
        self.encoder = tiktoken.encoding_for_model(model_name)
    
    def extract_content(self, content: str, content_filter: str = "gemini-only", 
                       include_docs: bool = False) -> str:
        """Extract content based on filter settings.
        
        Args:
            content: Raw meeting file content
            content_filter: Type of filtering ('gemini-only', 'no-transcripts', 'all')
            include_docs: Whether to include embedded documents
            
        Returns:
            Filtered content string
        """
        if content_filter == "gemini-only":
            return self.extract_gemini_only(content)
        elif content_filter == "no-transcripts":
            return self.extract_no_transcripts(content, include_docs)
        else:
            return content  # 'all' - no filtering
    
    def extract_gemini_only(self, content: str) -> str:
        """Extract only Gemini-generated notes sections.
        
        This extracts:
        - Summary section
        - Details section  
        - Suggested next steps section
        
        Excludes:
        - Transcripts
        - Embedded documents
        - Other meeting materials
        
        Args:
            content: Raw meeting file content
            
        Returns:
            Content containing only Gemini notes
        """
        # Start with YAML frontmatter and basic meeting info
        yaml_match = re.search(r'^---\n(.*?)\n---\n', content, re.DOTALL)
        if yaml_match:
            result = yaml_match.group(0)
            content_after_yaml = content[yaml_match.end():]
        else:
            result = ""
            content_after_yaml = content
        
        # Add basic meeting header info (title, date, organizer, etc.)
        header_match = re.search(r'^# [^\n]+\n\n\*\*Date:\*\*.*?(?=\n\n|\n#)', 
                                content_after_yaml, re.DOTALL | re.MULTILINE)
        if header_match:
            result += "\n" + header_match.group(0) + "\n\n"
        
        # Extract Gemini notes sections
        gemini_sections = []
        
        # Find Summary section
        summary_match = re.search(r'### Summary\n(.*?)(?=###|\*You should review|$)', 
                                 content, re.DOTALL)
        if summary_match:
            gemini_sections.append("### Summary\n" + summary_match.group(1))
        
        # Find Details section
        details_match = re.search(r'### Details\n(.*?)(?=###|\*You should review|$)', 
                                 content, re.DOTALL)
        if details_match:
            gemini_sections.append("### Details\n" + details_match.group(1))
        
        # Find Suggested next steps section
        steps_match = re.search(r'### Suggested next steps\n(.*?)(?=###|\*You should review|$)', 
                               content, re.DOTALL)
        if steps_match:
            gemini_sections.append("### Suggested next steps\n" + steps_match.group(1))
        
        if gemini_sections:
            result += "# 📝 Gemini Notes\n\n" + "\n\n".join(gemini_sections)
        
        return result.strip()
    
    def extract_no_transcripts(self, content: str, include_docs: bool = False) -> str:
        """Extract all content except transcripts.
        
        Args:
            content: Raw meeting file content
            include_docs: Whether to include embedded documents
            
        Returns:
            Content without transcript sections
        """
        # Find transcript markers
        transcript_markers = [
            r'# 📖 Transcript',
            r'## Transcript',
            r'# Transcript',
            r'## Meeting Transcript'
        ]
        
        # Split at the first transcript marker found
        for marker in transcript_markers:
            if re.search(marker, content):
                parts = re.split(marker, content, maxsplit=1)
                content_without_transcript = parts[0]
                break
        else:
            # No transcript found, return full content
            content_without_transcript = content
        
        # If not including docs, remove embedded documents
        if not include_docs:
            content_without_transcript = self._remove_embedded_documents(content_without_transcript)
        
        return content_without_transcript.strip()
    
    def _remove_embedded_documents(self, content: str) -> str:
        """Remove embedded document sections from content.
        
        Args:
            content: Content to filter
            
        Returns:
            Content with embedded documents removed
        """
        # Remove Document sections (## Document 1, ## Document 2, etc.)
        # Keep everything up to the first document or to Gemini notes
        
        # Find where documents start
        doc_pattern = r'\n## Document \d+'
        doc_match = re.search(doc_pattern, content)
        
        if doc_match:
            # Keep everything before the first document
            before_docs = content[:doc_match.start()]
            
            # Look for Gemini notes after documents
            notes_pattern = r'\n# 📝 Notes|### Summary'
            notes_match = re.search(notes_pattern, content[doc_match.start():])
            
            if notes_match:
                # Add back the Gemini notes section
                notes_start = doc_match.start() + notes_match.start()
                after_docs = content[notes_start:]
                return before_docs + "\n" + after_docs
            else:
                return before_docs
        
        return content
    
    def count_tokens(self, content: str) -> int:
        """Count tokens in content.
        
        Args:
            content: Content to count tokens for
            
        Returns:
            Number of tokens
        """
        return len(self.encoder.encode(content))
    
    def analyze_content_breakdown(self, content: str) -> Dict[str, Any]:
        """Analyze the token breakdown of different content types.
        
        Args:
            content: Raw meeting file content
            
        Returns:
            Dictionary with token counts for different content types
        """
        breakdown = {
            'total': self.count_tokens(content),
            'gemini_only': self.count_tokens(self.extract_gemini_only(content)),
            'no_transcripts': self.count_tokens(self.extract_no_transcripts(content)),
            'no_transcripts_with_docs': self.count_tokens(self.extract_no_transcripts(content, include_docs=True))
        }
        
        # Calculate percentages
        total = breakdown['total']
        if total > 0:
            breakdown['gemini_percentage'] = (breakdown['gemini_only'] / total) * 100
            breakdown['transcript_percentage'] = ((total - breakdown['no_transcripts']) / total) * 100
            breakdown['documents_percentage'] = ((breakdown['no_transcripts_with_docs'] - breakdown['no_transcripts']) / total) * 100
        
        return breakdown
    
    def extract_week_content(self, week_directory: str, content_filter: str = "gemini-only",
                           include_docs: bool = False) -> List[Tuple[str, str]]:
        """Extract content from all meetings in a week directory.
        
        Args:
            week_directory: Path to week directory
            content_filter: Type of filtering to apply
            include_docs: Whether to include embedded documents
            
        Returns:
            List of (filename, filtered_content) tuples
        """
        week_path = Path(week_directory)
        results = []
        
        for md_file in week_path.glob("*.md"):
            try:
                with open(md_file, 'r', encoding='utf-8') as f:
                    content = f.read()
                
                filtered_content = self.extract_content(content, content_filter, include_docs)
                results.append((md_file.name, filtered_content))
                
            except Exception as e:
                print(f"Warning: Could not process {md_file}: {e}")
                continue
        
        return results
    
    def estimate_cost(self, content: str, model_pricing: Dict[str, float]) -> float:
        """Estimate the cost of processing content with a given model.
        
        Args:
            content: Content to analyze
            model_pricing: Dictionary with 'input' and 'output' prices per 1K tokens
            
        Returns:
            Estimated cost in USD
        """
        input_tokens = self.count_tokens(content)
        # Estimate output tokens as 20% of input (rough approximation)
        output_tokens = int(input_tokens * 0.2)
        
        input_cost = (input_tokens / 1000) * model_pricing.get('input', 0)
        output_cost = (output_tokens / 1000) * model_pricing.get('output', 0)
        
        return input_cost + output_cost
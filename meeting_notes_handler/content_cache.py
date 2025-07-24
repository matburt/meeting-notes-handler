"""Content cache for storing meeting content signatures."""

import json
import gzip
import logging
from pathlib import Path
from datetime import datetime, timedelta
from typing import Dict, List, Optional
from dataclasses import asdict

from .content_hasher import ContentSignature, Section, Paragraph

logger = logging.getLogger(__name__)


class MeetingContentCache:
    """Manages storage and retrieval of meeting content signatures."""
    
    def __init__(self, cache_directory: str):
        """
        Initialize the content cache.
        
        Args:
            cache_directory: Base directory for cache storage
        """
        self.cache_dir = Path(cache_directory)
        self.cache_subdir = self.cache_dir / ".meeting_content_cache"
        self.cache_subdir.mkdir(parents=True, exist_ok=True)
        
        # Cache settings
        self.use_compression = True
        self.archive_after_days = 180  # Archive old entries after 6 months
        
    def store_content_signature(self, series_id: str, meeting_date: str, 
                              signature: ContentSignature) -> bool:
        """
        Store a content signature for a meeting.
        
        Args:
            series_id: Meeting series identifier
            meeting_date: Meeting date (YYYY-MM-DD format)
            signature: Content signature to store
            
        Returns:
            True if successfully stored
        """
        try:
            # Create series directory if needed
            series_dir = self.cache_subdir / series_id
            series_dir.mkdir(exist_ok=True)
            
            # Prepare filename
            filename = f"{meeting_date}_content.json"
            if self.use_compression:
                filename += ".gz"
            
            filepath = series_dir / filename
            
            # Convert signature to dict
            signature_dict = self._signature_to_dict(signature)
            
            # Write to file
            if self.use_compression:
                with gzip.open(filepath, 'wt', encoding='utf-8') as f:
                    json.dump(signature_dict, f, indent=2, ensure_ascii=False)
            else:
                with open(filepath, 'w', encoding='utf-8') as f:
                    json.dump(signature_dict, f, indent=2, ensure_ascii=False)
            
            logger.debug(f"Stored content signature for {series_id}/{meeting_date}")
            return True
            
        except Exception as e:
            logger.error(f"Error storing content signature: {e}")
            return False
    
    def get_content_signature(self, series_id: str, meeting_date: str) -> Optional[ContentSignature]:
        """
        Retrieve a content signature for a meeting.
        
        Args:
            series_id: Meeting series identifier
            meeting_date: Meeting date (YYYY-MM-DD format)
            
        Returns:
            ContentSignature if found, None otherwise
        """
        try:
            series_dir = self.cache_subdir / series_id
            if not series_dir.exists():
                return None
            
            # Try compressed file first
            filename = f"{meeting_date}_content.json"
            filepath = series_dir / f"{filename}.gz"
            
            if filepath.exists() and self.use_compression:
                with gzip.open(filepath, 'rt', encoding='utf-8') as f:
                    signature_dict = json.load(f)
            else:
                # Try uncompressed
                filepath = series_dir / filename
                if filepath.exists():
                    with open(filepath, 'r', encoding='utf-8') as f:
                        signature_dict = json.load(f)
                else:
                    return None
            
            # Convert dict back to ContentSignature
            return self._dict_to_signature(signature_dict)
            
        except Exception as e:
            logger.error(f"Error retrieving content signature: {e}")
            return None
    
    def get_latest_signatures(self, series_id: str, limit: int = 10) -> List[ContentSignature]:
        """
        Get the most recent content signatures for a series.
        
        Args:
            series_id: Meeting series identifier
            limit: Maximum number of signatures to return
            
        Returns:
            List of ContentSignatures, most recent first
        """
        signatures = []
        
        try:
            series_dir = self.cache_subdir / series_id
            if not series_dir.exists():
                return signatures
            
            # Find all content files
            content_files = []
            for file in series_dir.iterdir():
                if file.name.endswith('_content.json') or file.name.endswith('_content.json.gz'):
                    # Extract date from filename
                    date_str = file.name.split('_')[0]
                    try:
                        date = datetime.strptime(date_str, '%Y-%m-%d')
                        content_files.append((date, date_str, file))
                    except ValueError:
                        logger.warning(f"Invalid date format in filename: {file.name}")
            
            # Sort by date, most recent first
            content_files.sort(key=lambda x: x[0], reverse=True)
            
            # Load signatures up to limit
            for _, date_str, _ in content_files[:limit]:
                signature = self.get_content_signature(series_id, date_str)
                if signature:
                    signatures.append(signature)
            
        except Exception as e:
            logger.error(f"Error getting latest signatures: {e}")
        
        return signatures
    
    def get_signatures_in_range(self, series_id: str, start_date: str, 
                               end_date: str) -> List[ContentSignature]:
        """
        Get content signatures within a date range.
        
        Args:
            series_id: Meeting series identifier
            start_date: Start date (YYYY-MM-DD format)
            end_date: End date (YYYY-MM-DD format)
            
        Returns:
            List of ContentSignatures in date range
        """
        signatures = []
        
        try:
            start = datetime.strptime(start_date, '%Y-%m-%d')
            end = datetime.strptime(end_date, '%Y-%m-%d')
            
            series_dir = self.cache_subdir / series_id
            if not series_dir.exists():
                return signatures
            
            # Check each date in range
            current = start
            while current <= end:
                date_str = current.strftime('%Y-%m-%d')
                signature = self.get_content_signature(series_id, date_str)
                if signature:
                    signatures.append(signature)
                current += timedelta(days=1)
            
        except Exception as e:
            logger.error(f"Error getting signatures in range: {e}")
        
        return signatures
    
    def has_content_signature(self, series_id: str, meeting_date: str) -> bool:
        """
        Check if a content signature exists for a meeting.
        
        Args:
            series_id: Meeting series identifier
            meeting_date: Meeting date (YYYY-MM-DD format)
            
        Returns:
            True if signature exists
        """
        series_dir = self.cache_subdir / series_id
        if not series_dir.exists():
            return False
        
        filename = f"{meeting_date}_content.json"
        compressed_path = series_dir / f"{filename}.gz"
        uncompressed_path = series_dir / filename
        
        return compressed_path.exists() or uncompressed_path.exists()
    
    def cleanup_old_entries(self, days: Optional[int] = None):
        """
        Clean up cache entries older than specified days.
        
        Args:
            days: Number of days to keep (default: self.archive_after_days)
        """
        if days is None:
            days = self.archive_after_days
        
        cutoff_date = datetime.now() - timedelta(days=days)
        removed_count = 0
        
        try:
            for series_dir in self.cache_subdir.iterdir():
                if not series_dir.is_dir():
                    continue
                
                for file in series_dir.iterdir():
                    if file.name.endswith('_content.json') or file.name.endswith('_content.json.gz'):
                        # Extract date from filename
                        date_str = file.name.split('_')[0]
                        try:
                            file_date = datetime.strptime(date_str, '%Y-%m-%d')
                            if file_date < cutoff_date:
                                file.unlink()
                                removed_count += 1
                        except ValueError:
                            logger.warning(f"Invalid date format in filename: {file.name}")
                
                # Remove empty directories
                if not any(series_dir.iterdir()):
                    series_dir.rmdir()
            
            logger.info(f"Cleaned up {removed_count} old cache entries")
            
        except Exception as e:
            logger.error(f"Error cleaning up cache: {e}")
    
    def get_cache_statistics(self) -> Dict:
        """Get statistics about the cache."""
        stats = {
            'total_series': 0,
            'total_signatures': 0,
            'total_size_bytes': 0,
            'series_details': {}
        }
        
        try:
            for series_dir in self.cache_subdir.iterdir():
                if not series_dir.is_dir():
                    continue
                
                stats['total_series'] += 1
                series_id = series_dir.name
                series_count = 0
                series_size = 0
                
                for file in series_dir.iterdir():
                    if file.name.endswith('_content.json') or file.name.endswith('_content.json.gz'):
                        series_count += 1
                        series_size += file.stat().st_size
                
                stats['total_signatures'] += series_count
                stats['total_size_bytes'] += series_size
                stats['series_details'][series_id] = {
                    'signature_count': series_count,
                    'size_bytes': series_size
                }
                
        except Exception as e:
            logger.error(f"Error getting cache statistics: {e}")
        
        return stats
    
    def _signature_to_dict(self, signature: ContentSignature) -> Dict:
        """Convert ContentSignature to dictionary for storage."""
        # Convert dataclass to dict
        sig_dict = asdict(signature)
        
        # Ensure all fields are serializable
        return sig_dict
    
    def _dict_to_signature(self, data: Dict) -> ContentSignature:
        """Convert dictionary back to ContentSignature."""
        # Reconstruct sections
        sections = []
        for section_data in data.get('sections', []):
            # Reconstruct paragraphs
            paragraphs = []
            for para_data in section_data.get('paragraphs', []):
                paragraphs.append(Paragraph(**para_data))
            
            # Create section
            section = Section(
                header=section_data['header'],
                header_hash=section_data['header_hash'],
                paragraphs=paragraphs,
                position=section_data['position']
            )
            sections.append(section)
        
        # Create ContentSignature
        return ContentSignature(
            meeting_id=data['meeting_id'],
            content_version=data.get('content_version', '1.0'),
            extracted_at=data.get('extracted_at', ''),
            full_content_hash=data.get('full_content_hash', ''),
            sections=sections,
            total_words=data.get('total_words', 0),
            total_paragraphs=data.get('total_paragraphs', 0)
        )
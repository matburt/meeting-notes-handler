"""Diff engine for comparing meeting content."""

from dataclasses import dataclass
from typing import List, Dict, Tuple, Optional, Set
from enum import Enum
import logging
from difflib import SequenceMatcher

from .content_hasher import ContentSignature, Section, Paragraph

logger = logging.getLogger(__name__)


class ChangeType(Enum):
    """Types of changes detected."""
    ADDED = "added"
    REMOVED = "removed"
    MODIFIED = "modified"
    MOVED = "moved"
    REORDERED = "reordered"


@dataclass
class ParagraphChange:
    """Represents a change to a paragraph."""
    change_type: ChangeType
    old_paragraph: Optional[Paragraph] = None
    new_paragraph: Optional[Paragraph] = None
    old_section: Optional[str] = None
    new_section: Optional[str] = None
    similarity_score: float = 0.0


@dataclass
class SectionChange:
    """Represents changes to a section."""
    change_type: ChangeType
    old_section: Optional[Section] = None
    new_section: Optional[Section] = None
    paragraph_changes: List[ParagraphChange] = None
    
    def __post_init__(self):
        if self.paragraph_changes is None:
            self.paragraph_changes = []


@dataclass
class MeetingDiff:
    """Complete diff between two meetings."""
    old_meeting_id: str
    new_meeting_id: str
    section_changes: List[SectionChange]
    moved_paragraphs: List[ParagraphChange]
    summary: 'DiffSummary'


@dataclass
class DiffSummary:
    """Summary statistics for a diff."""
    total_sections_added: int = 0
    total_sections_removed: int = 0
    total_sections_modified: int = 0
    total_paragraphs_added: int = 0
    total_paragraphs_removed: int = 0
    total_paragraphs_modified: int = 0
    total_paragraphs_moved: int = 0
    total_words_added: int = 0
    total_words_removed: int = 0
    similarity_percentage: float = 0.0


class DiffEngine:
    """Engine for comparing meeting content and generating diffs."""
    
    def __init__(self, similarity_threshold: float = 0.85):
        """
        Initialize the diff engine.
        
        Args:
            similarity_threshold: Minimum similarity to consider paragraphs as modified vs added/removed
        """
        self.similarity_threshold = similarity_threshold
    
    def compare_meetings(self, old_signature: ContentSignature, 
                        new_signature: ContentSignature) -> MeetingDiff:
        """
        Compare two meeting content signatures.
        
        Args:
            old_signature: Previous meeting content
            new_signature: New meeting content
            
        Returns:
            MeetingDiff with all detected changes
        """
        # Compare sections
        section_changes = self._compare_sections(old_signature.sections, new_signature.sections)
        
        # Find moved paragraphs
        moved_paragraphs = self._find_moved_paragraphs(old_signature.sections, new_signature.sections)
        
        # Generate summary
        summary = self._generate_summary(section_changes, moved_paragraphs, 
                                       old_signature, new_signature)
        
        return MeetingDiff(
            old_meeting_id=old_signature.meeting_id,
            new_meeting_id=new_signature.meeting_id,
            section_changes=section_changes,
            moved_paragraphs=moved_paragraphs,
            summary=summary
        )
    
    def _compare_sections(self, old_sections: List[Section], 
                         new_sections: List[Section]) -> List[SectionChange]:
        """Compare sections between two meetings."""
        section_changes = []
        
        # Create maps for easier lookup
        old_section_map = {s.header: s for s in old_sections}
        new_section_map = {s.header: s for s in new_sections}
        
        # Track processed sections
        processed_new_sections = set()
        
        # Check each old section
        for old_section in old_sections:
            if old_section.header in new_section_map:
                # Section exists in both - check for modifications
                new_section = new_section_map[old_section.header]
                processed_new_sections.add(old_section.header)
                
                paragraph_changes = self._compare_paragraphs(
                    old_section.paragraphs, 
                    new_section.paragraphs,
                    old_section.header,
                    new_section.header
                )
                
                if paragraph_changes:
                    section_changes.append(SectionChange(
                        change_type=ChangeType.MODIFIED,
                        old_section=old_section,
                        new_section=new_section,
                        paragraph_changes=paragraph_changes
                    ))
            else:
                # Section removed
                section_changes.append(SectionChange(
                    change_type=ChangeType.REMOVED,
                    old_section=old_section,
                    new_section=None
                ))
        
        # Check for new sections
        for header, new_section in new_section_map.items():
            if header not in processed_new_sections:
                section_changes.append(SectionChange(
                    change_type=ChangeType.ADDED,
                    old_section=None,
                    new_section=new_section
                ))
        
        return section_changes
    
    def _compare_paragraphs(self, old_paragraphs: List[Paragraph], 
                           new_paragraphs: List[Paragraph],
                           old_section: str, new_section: str) -> List[ParagraphChange]:
        """Compare paragraphs within sections."""
        changes = []
        
        # Create hash maps for exact matches
        old_hash_map = {p.hash: p for p in old_paragraphs}
        new_hash_map = {p.hash: p for p in new_paragraphs}
        
        # Track processed paragraphs
        processed_new = set()
        
        # First pass: Find exact matches and removals
        for old_para in old_paragraphs:
            if old_para.hash in new_hash_map:
                # Exact match - no change needed unless position changed
                processed_new.add(old_para.hash)
            else:
                # Not an exact match - check for modifications
                best_match = self._find_best_match(old_para, new_paragraphs, processed_new)
                
                if best_match and best_match[1] >= self.similarity_threshold:
                    # Modified paragraph
                    new_para = best_match[0]
                    processed_new.add(new_para.hash)
                    changes.append(ParagraphChange(
                        change_type=ChangeType.MODIFIED,
                        old_paragraph=old_para,
                        new_paragraph=new_para,
                        old_section=old_section,
                        new_section=new_section,
                        similarity_score=best_match[1]
                    ))
                else:
                    # Removed paragraph
                    changes.append(ParagraphChange(
                        change_type=ChangeType.REMOVED,
                        old_paragraph=old_para,
                        new_paragraph=None,
                        old_section=old_section,
                        new_section=new_section
                    ))
        
        # Second pass: Find additions
        for new_para in new_paragraphs:
            if new_para.hash not in processed_new:
                changes.append(ParagraphChange(
                    change_type=ChangeType.ADDED,
                    old_paragraph=None,
                    new_paragraph=new_para,
                    old_section=old_section,
                    new_section=new_section
                ))
        
        return changes
    
    def _find_moved_paragraphs(self, old_sections: List[Section], 
                              new_sections: List[Section]) -> List[ParagraphChange]:
        """Find paragraphs that moved between sections."""
        moved = []
        
        # Build global paragraph maps
        old_para_to_section = {}
        new_para_to_section = {}
        
        for section in old_sections:
            for para in section.paragraphs:
                old_para_to_section[para.hash] = section.header
        
        for section in new_sections:
            for para in section.paragraphs:
                new_para_to_section[para.hash] = section.header
        
        # Find paragraphs that exist in both but different sections
        for para_hash, old_section_header in old_para_to_section.items():
            if para_hash in new_para_to_section:
                new_section_header = new_para_to_section[para_hash]
                if old_section_header != new_section_header:
                    # Find the actual paragraph objects
                    old_para = None
                    new_para = None
                    
                    for section in old_sections:
                        if section.header == old_section_header:
                            for para in section.paragraphs:
                                if para.hash == para_hash:
                                    old_para = para
                                    break
                    
                    for section in new_sections:
                        if section.header == new_section_header:
                            for para in section.paragraphs:
                                if para.hash == para_hash:
                                    new_para = para
                                    break
                    
                    if old_para and new_para:
                        moved.append(ParagraphChange(
                            change_type=ChangeType.MOVED,
                            old_paragraph=old_para,
                            new_paragraph=new_para,
                            old_section=old_section_header,
                            new_section=new_section_header,
                            similarity_score=1.0
                        ))
        
        return moved
    
    def _find_best_match(self, paragraph: Paragraph, 
                        candidates: List[Paragraph], 
                        exclude_hashes: Set[str]) -> Optional[Tuple[Paragraph, float]]:
        """Find the best matching paragraph from candidates."""
        best_match = None
        best_score = 0.0
        
        for candidate in candidates:
            if candidate.hash in exclude_hashes:
                continue
            
            # Calculate similarity
            score = self._calculate_similarity(paragraph.content, candidate.content)
            
            if score > best_score:
                best_score = score
                best_match = candidate
        
        if best_match and best_score >= self.similarity_threshold:
            return (best_match, best_score)
        
        return None
    
    def _calculate_similarity(self, text1: str, text2: str) -> float:
        """Calculate similarity between two texts."""
        if not text1 or not text2:
            return 0.0 if text1 != text2 else 1.0
        
        # Use SequenceMatcher for more accurate similarity
        return SequenceMatcher(None, text1.lower(), text2.lower()).ratio()
    
    def _generate_summary(self, section_changes: List[SectionChange], 
                         moved_paragraphs: List[ParagraphChange],
                         old_signature: ContentSignature,
                         new_signature: ContentSignature) -> DiffSummary:
        """Generate summary statistics for the diff."""
        summary = DiffSummary()
        
        # Count section changes
        for change in section_changes:
            if change.change_type == ChangeType.ADDED:
                summary.total_sections_added += 1
                # Count all paragraphs in new section as added
                if change.new_section:
                    summary.total_paragraphs_added += len(change.new_section.paragraphs)
                    summary.total_words_added += sum(p.word_count for p in change.new_section.paragraphs)
            elif change.change_type == ChangeType.REMOVED:
                summary.total_sections_removed += 1
                # Count all paragraphs in old section as removed
                if change.old_section:
                    summary.total_paragraphs_removed += len(change.old_section.paragraphs)
                    summary.total_words_removed += sum(p.word_count for p in change.old_section.paragraphs)
            elif change.change_type == ChangeType.MODIFIED:
                summary.total_sections_modified += 1
                # Count paragraph changes within section
                for para_change in change.paragraph_changes:
                    if para_change.change_type == ChangeType.ADDED:
                        summary.total_paragraphs_added += 1
                        if para_change.new_paragraph:
                            summary.total_words_added += para_change.new_paragraph.word_count
                    elif para_change.change_type == ChangeType.REMOVED:
                        summary.total_paragraphs_removed += 1
                        if para_change.old_paragraph:
                            summary.total_words_removed += para_change.old_paragraph.word_count
                    elif para_change.change_type == ChangeType.MODIFIED:
                        summary.total_paragraphs_modified += 1
                        if para_change.old_paragraph and para_change.new_paragraph:
                            word_diff = para_change.new_paragraph.word_count - para_change.old_paragraph.word_count
                            if word_diff > 0:
                                summary.total_words_added += word_diff
                            else:
                                summary.total_words_removed += abs(word_diff)
        
        # Count moved paragraphs
        summary.total_paragraphs_moved = len(moved_paragraphs)
        
        # Calculate overall similarity
        if old_signature.total_words > 0 or new_signature.total_words > 0:
            unchanged_words = max(0, min(old_signature.total_words, new_signature.total_words) - 
                                summary.total_words_removed - summary.total_words_added)
            total_words = max(old_signature.total_words, new_signature.total_words)
            summary.similarity_percentage = (unchanged_words / total_words * 100) if total_words > 0 else 0
        
        return summary
    
    def format_diff_summary(self, diff: MeetingDiff) -> str:
        """Format a diff summary for display."""
        summary = diff.summary
        lines = []
        
        lines.append("📊 Meeting Diff Summary")
        lines.append(f"   {diff.old_meeting_id} → {diff.new_meeting_id}")
        lines.append("")
        
        if summary.total_sections_added > 0:
            lines.append(f"   ✅ Sections added: {summary.total_sections_added}")
        if summary.total_sections_removed > 0:
            lines.append(f"   ❌ Sections removed: {summary.total_sections_removed}")
        if summary.total_sections_modified > 0:
            lines.append(f"   🔄 Sections modified: {summary.total_sections_modified}")
        
        lines.append("")
        
        if summary.total_paragraphs_added > 0:
            lines.append(f"   ✅ Paragraphs added: {summary.total_paragraphs_added} ({summary.total_words_added} words)")
        if summary.total_paragraphs_removed > 0:
            lines.append(f"   ❌ Paragraphs removed: {summary.total_paragraphs_removed} ({summary.total_words_removed} words)")
        if summary.total_paragraphs_modified > 0:
            lines.append(f"   🔄 Paragraphs modified: {summary.total_paragraphs_modified}")
        if summary.total_paragraphs_moved > 0:
            lines.append(f"   ↔️  Paragraphs moved: {summary.total_paragraphs_moved}")
        
        lines.append("")
        lines.append(f"   📈 Overall similarity: {summary.similarity_percentage:.1f}%")
        
        return '\n'.join(lines)
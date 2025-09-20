import difflib
import hashlib
import re
from typing import List, Dict, Tuple, Optional, Any
from dataclasses import dataclass
from datetime import datetime
import logging

logger = logging.getLogger(__name__)

@dataclass
class DiffResult:
    """Result of a diff comparison"""
    has_changes: bool
    similarity_ratio: float  # 0-1, how similar the texts are
    change_percentage: float  # 0-100, percentage of text changed
    word_count_delta: int
    line_count_delta: int

    # Diff details
    unified_diff: str
    context_diff: str
    summary: str

    # Semantic analysis
    sections_changed: List[str]
    significant_changes: List[str]
    minor_changes: List[str]

@dataclass
class BillSnapshot:
    """Snapshot of a bill at a specific point in time"""
    bill_id: int
    snapshot_time: datetime
    title: str
    summary: str
    full_text: str
    status: str
    sponsor: str
    committee: str
    checksum: str

class DiffEngine:
    """Advanced diff engine for bill text comparison"""

    def __init__(self):
        self.significant_keywords = [
            # Financial terms
            "reimbursement", "payment", "rate", "funding", "cost", "budget",
            "appropriation", "fee", "penalty", "fine", "tax", "credit",

            # Policy terms
            "requirement", "mandate", "prohibition", "restriction", "eligibility",
            "certification", "qualification", "standard", "criteria", "threshold",

            # Healthcare specific
            "medicare", "medicaid", "snf", "skilled nursing", "long-term care",
            "quality", "safety", "inspection", "survey", "compliance",

            # Legislative process
            "effective date", "implementation", "deadline", "timeline", "phase",
            "shall", "must", "required", "prohibited", "authorized"
        ]

        self.section_patterns = [
            r"SECTION\s+\d+",
            r"SEC\.\s+\d+",
            r"\(\w+\)\s*[A-Z][A-Z\s]+\.—",
            r"Title\s+[IVX]+",
            r"Chapter\s+\d+",
            r"Part\s+[A-Z]+",
            r"Subpart\s+[A-Z]+"
        ]

    def create_snapshot(self, bill_id: int, title: str, summary: str,
                       full_text: str, status: str, sponsor: str, committee: str) -> BillSnapshot:
        """Create a snapshot of the current bill state"""
        content = f"{title}\n{summary}\n{full_text}\n{status}\n{sponsor}\n{committee}"
        checksum = hashlib.md5(content.encode()).hexdigest()

        return BillSnapshot(
            bill_id=bill_id,
            snapshot_time=datetime.utcnow(),
            title=title or "",
            summary=summary or "",
            full_text=full_text or "",
            status=status or "",
            sponsor=sponsor or "",
            committee=committee or "",
            checksum=checksum
        )

    def compare_snapshots(self, old_snapshot: BillSnapshot,
                         new_snapshot: BillSnapshot) -> DiffResult:
        """Compare two bill snapshots and return detailed diff analysis"""

        if old_snapshot.checksum == new_snapshot.checksum:
            return DiffResult(
                has_changes=False,
                similarity_ratio=1.0,
                change_percentage=0.0,
                word_count_delta=0,
                line_count_delta=0,
                unified_diff="",
                context_diff="",
                summary="No changes detected",
                sections_changed=[],
                significant_changes=[],
                minor_changes=[]
            )

        # Combine all text fields for comprehensive comparison
        old_text = self._combine_bill_text(old_snapshot)
        new_text = self._combine_bill_text(new_snapshot)

        return self.compare_text(old_text, new_text)

    def compare_text(self, old_text: str, new_text: str) -> DiffResult:
        """Compare two text strings and return detailed analysis"""

        # Basic similarity metrics
        similarity_ratio = difflib.SequenceMatcher(None, old_text, new_text).ratio()
        change_percentage = (1 - similarity_ratio) * 100

        # Word and line counts
        old_words = len(old_text.split())
        new_words = len(new_text.split())
        word_count_delta = new_words - old_words

        old_lines = old_text.count('\n') + 1
        new_lines = new_text.count('\n') + 1
        line_count_delta = new_lines - old_lines

        # Generate diffs
        old_lines_list = old_text.splitlines(keepends=True)
        new_lines_list = new_text.splitlines(keepends=True)

        unified_diff = ''.join(difflib.unified_diff(
            old_lines_list, new_lines_list,
            fromfile='previous_version', tofile='current_version',
            lineterm='', n=3
        ))

        context_diff = ''.join(difflib.context_diff(
            old_lines_list, new_lines_list,
            fromfile='previous_version', tofile='current_version',
            lineterm='', n=3
        ))

        # Analyze changes
        sections_changed = self._identify_changed_sections(old_text, new_text)
        significant_changes = self._identify_significant_changes(old_text, new_text)
        minor_changes = self._identify_minor_changes(old_text, new_text)

        # Generate summary
        summary = self._generate_change_summary(
            similarity_ratio, sections_changed, significant_changes, minor_changes
        )

        return DiffResult(
            has_changes=True,
            similarity_ratio=similarity_ratio,
            change_percentage=change_percentage,
            word_count_delta=word_count_delta,
            line_count_delta=line_count_delta,
            unified_diff=unified_diff,
            context_diff=context_diff,
            summary=summary,
            sections_changed=sections_changed,
            significant_changes=significant_changes,
            minor_changes=minor_changes
        )

    def compare_field(self, old_value: str, new_value: str, field_name: str) -> Dict[str, Any]:
        """Compare a specific field between old and new versions"""
        if not old_value:
            old_value = ""
        if not new_value:
            new_value = ""

        if old_value == new_value:
            return {
                "changed": False,
                "field": field_name,
                "old_value": old_value,
                "new_value": new_value,
                "change_type": "none"
            }

        # Determine change type
        if not old_value and new_value:
            change_type = "addition"
        elif old_value and not new_value:
            change_type = "removal"
        else:
            change_type = "modification"

        # Calculate similarity for modifications
        similarity = 0.0
        if change_type == "modification":
            similarity = difflib.SequenceMatcher(None, old_value, new_value).ratio()

        return {
            "changed": True,
            "field": field_name,
            "old_value": old_value,
            "new_value": new_value,
            "change_type": change_type,
            "similarity": similarity,
            "diff": self._generate_inline_diff(old_value, new_value)
        }

    def _combine_bill_text(self, snapshot: BillSnapshot) -> str:
        """Combine all text fields of a bill snapshot"""
        return f"""TITLE: {snapshot.title}

SUMMARY: {snapshot.summary}

FULL TEXT:
{snapshot.full_text}

STATUS: {snapshot.status}
SPONSOR: {snapshot.sponsor}
COMMITTEE: {snapshot.committee}"""

    def _identify_changed_sections(self, old_text: str, new_text: str) -> List[str]:
        """Identify which sections of the bill have changed"""
        sections_changed = []

        for pattern in self.section_patterns:
            old_sections = re.findall(pattern, old_text, re.IGNORECASE)
            new_sections = re.findall(pattern, new_text, re.IGNORECASE)

            # Find sections that are different
            old_set = set(old_sections)
            new_set = set(new_sections)

            added_sections = new_set - old_set
            removed_sections = old_set - new_set

            for section in added_sections:
                sections_changed.append(f"Added: {section}")
            for section in removed_sections:
                sections_changed.append(f"Removed: {section}")

        return sections_changed

    def _identify_significant_changes(self, old_text: str, new_text: str) -> List[str]:
        """Identify significant changes using keyword analysis"""
        significant_changes = []

        # Look for changes involving significant keywords
        for keyword in self.significant_keywords:
            old_contexts = self._get_keyword_contexts(old_text, keyword)
            new_contexts = self._get_keyword_contexts(new_text, keyword)

            # Compare contexts
            if len(old_contexts) != len(new_contexts):
                if len(new_contexts) > len(old_contexts):
                    significant_changes.append(f"Added references to '{keyword}' ({len(new_contexts) - len(old_contexts)} new)")
                else:
                    significant_changes.append(f"Removed references to '{keyword}' ({len(old_contexts) - len(new_contexts)} removed)")

            # Check for changes in existing contexts
            for old_ctx, new_ctx in zip(old_contexts, new_contexts):
                if old_ctx != new_ctx:
                    significant_changes.append(f"Modified content around '{keyword}'")
                    break

        return list(set(significant_changes))  # Remove duplicates

    def _identify_minor_changes(self, old_text: str, new_text: str) -> List[str]:
        """Identify minor changes like typos, formatting, etc."""
        minor_changes = []

        # Check for typical minor changes
        old_lines = old_text.splitlines()
        new_lines = new_text.splitlines()

        diff = list(difflib.unified_diff(old_lines, new_lines, n=0))

        for line in diff:
            if line.startswith('-') or line.startswith('+'):
                # Skip diff metadata
                if line.startswith('---') or line.startswith('+++'):
                    continue

                change_text = line[1:].strip()

                # Check if it's likely a minor change
                if self._is_minor_change(change_text):
                    minor_changes.append(change_text[:100] + "..." if len(change_text) > 100 else change_text)

        return minor_changes[:10]  # Limit to avoid spam

    def _is_minor_change(self, text: str) -> bool:
        """Determine if a change is likely minor (typos, formatting, etc.)"""
        # Very short changes are likely minor
        if len(text.strip()) < 3:
            return True

        # Changes that are mostly punctuation or whitespace
        alpha_chars = sum(1 for c in text if c.isalpha())
        if alpha_chars < len(text) * 0.3:  # Less than 30% alphabetic
            return True

        # Single word changes might be typos
        words = text.split()
        if len(words) == 1 and len(words[0]) < 10:
            return True

        return False

    def _get_keyword_contexts(self, text: str, keyword: str, context_size: int = 50) -> List[str]:
        """Get contexts around keyword occurrences"""
        contexts = []
        text_lower = text.lower()
        keyword_lower = keyword.lower()

        start = 0
        while True:
            pos = text_lower.find(keyword_lower, start)
            if pos == -1:
                break

            context_start = max(0, pos - context_size)
            context_end = min(len(text), pos + len(keyword) + context_size)
            context = text[context_start:context_end].strip()
            contexts.append(context)

            start = pos + 1

        return contexts

    def _generate_inline_diff(self, old_text: str, new_text: str) -> str:
        """Generate inline diff representation"""
        if not old_text and new_text:
            return f"[ADDED: {new_text}]"
        elif old_text and not new_text:
            return f"[REMOVED: {old_text}]"
        elif old_text != new_text:
            return f"[CHANGED: {old_text} → {new_text}]"
        else:
            return "[NO CHANGE]"

    def _generate_change_summary(self, similarity_ratio: float, sections_changed: List[str],
                                significant_changes: List[str], minor_changes: List[str]) -> str:
        """Generate a human-readable summary of changes"""
        change_percentage = (1 - similarity_ratio) * 100

        summary_parts = [f"Overall similarity: {similarity_ratio:.1%} ({change_percentage:.1f}% changed)"]

        if sections_changed:
            summary_parts.append(f"Structural changes: {len(sections_changed)} sections affected")

        if significant_changes:
            summary_parts.append(f"Significant changes: {len(significant_changes)} policy-relevant modifications")

        if minor_changes:
            summary_parts.append(f"Minor changes: {len(minor_changes)} small text modifications")

        return ". ".join(summary_parts) + "."

    def calculate_change_significance(self, diff_result: DiffResult) -> str:
        """Calculate the overall significance of changes"""
        if not diff_result.has_changes:
            return "none"

        # Critical: Major structural or policy changes
        if (len(diff_result.significant_changes) > 5 or
            diff_result.change_percentage > 50 or
            len(diff_result.sections_changed) > 3):
            return "critical"

        # Significant: Notable policy changes
        if (len(diff_result.significant_changes) > 2 or
            diff_result.change_percentage > 25 or
            len(diff_result.sections_changed) > 1):
            return "significant"

        # Moderate: Some meaningful changes
        if (len(diff_result.significant_changes) > 0 or
            diff_result.change_percentage > 10 or
            abs(diff_result.word_count_delta) > 100):
            return "moderate"

        # Minor: Small changes
        return "minor"
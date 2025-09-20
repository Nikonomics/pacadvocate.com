import re
import logging
from typing import Dict, List, Tuple, Optional
from dataclasses import dataclass
from datetime import datetime
from models.change_detection import BillStage
import openai
import json
import os
from dotenv import load_dotenv

load_dotenv()
logger = logging.getLogger(__name__)

@dataclass
class StageTransitionResult:
    """Result of stage transition detection"""
    has_transition: bool
    from_stage: Optional[BillStage]
    to_stage: Optional[BillStage]
    confidence: float
    transition_date: Optional[datetime]
    committee_name: Optional[str]
    vote_details: Optional[str]
    notes: str
    passage_likelihood: float  # 0-1 probability estimate

class StageDetector:
    """Detects bill stage transitions and legislative progress"""

    def __init__(self):
        self.openai_client = openai.OpenAI(api_key=os.getenv('OPENAI_API_KEY'))

        # Status patterns for different stages
        self.stage_patterns = {
            BillStage.INTRODUCED: [
                r'introduced',
                r'referred to committee',
                r'read first time',
                r'presented',
                r'filed'
            ],

            BillStage.COMMITTEE_REVIEW: [
                r'in committee',
                r'committee review',
                r'referred to.*committee',
                r'under consideration',
                r'committee hearing'
            ],

            BillStage.COMMITTEE_MARKUP: [
                r'committee markup',
                r'markup scheduled',
                r'committee amendment',
                r'committee consideration'
            ],

            BillStage.COMMITTEE_REPORTED: [
                r'reported.*committee',
                r'committee reported',
                r'favorably reported',
                r'reported with amendment',
                r'committee passed'
            ],

            BillStage.FLOOR_CONSIDERATION: [
                r'floor consideration',
                r'scheduled for floor',
                r'second reading',
                r'floor debate',
                r'amendment process'
            ],

            BillStage.PASSED_CHAMBER: [
                r'passed.*house',
                r'passed.*senate',
                r'approved by',
                r'third reading passed',
                r'final passage'
            ],

            BillStage.SENT_TO_OTHER_CHAMBER: [
                r'sent to.*senate',
                r'sent to.*house',
                r'transmitted to',
                r'received from.*house',
                r'received from.*senate'
            ],

            BillStage.OTHER_CHAMBER_COMMITTEE: [
                r'referred to.*senate.*committee',
                r'referred to.*house.*committee',
                r'committee.*other chamber'
            ],

            BillStage.OTHER_CHAMBER_FLOOR: [
                r'senate floor',
                r'house floor',
                r'other chamber.*floor'
            ],

            BillStage.PASSED_BOTH_CHAMBERS: [
                r'passed both chambers',
                r'bicameral passage',
                r'cleared congress',
                r'final legislative approval'
            ],

            BillStage.SENT_TO_PRESIDENT: [
                r'sent to president',
                r'presented to president',
                r'awaiting presidential',
                r'presidential consideration'
            ],

            BillStage.SIGNED_INTO_LAW: [
                r'signed into law',
                r'became law',
                r'president signed',
                r'enacted',
                r'public law'
            ],

            BillStage.VETOED: [
                r'vetoed',
                r'presidential veto',
                r'veto message'
            ],

            BillStage.WITHDRAWN: [
                r'withdrawn',
                r'pulled back',
                r'sponsor withdrew'
            ],

            BillStage.DIED: [
                r'died in committee',
                r'failed to advance',
                r'session ended',
                r'expired',
                r'no action taken'
            ]
        }

        # Stage progression order (for validation)
        self.stage_order = [
            BillStage.INTRODUCED,
            BillStage.COMMITTEE_REVIEW,
            BillStage.COMMITTEE_MARKUP,
            BillStage.COMMITTEE_REPORTED,
            BillStage.FLOOR_CONSIDERATION,
            BillStage.PASSED_CHAMBER,
            BillStage.SENT_TO_OTHER_CHAMBER,
            BillStage.OTHER_CHAMBER_COMMITTEE,
            BillStage.OTHER_CHAMBER_FLOOR,
            BillStage.PASSED_BOTH_CHAMBERS,
            BillStage.SENT_TO_PRESIDENT,
            BillStage.SIGNED_INTO_LAW
        ]

        # Passage likelihood by stage
        self.passage_probabilities = {
            BillStage.INTRODUCED: 0.05,
            BillStage.COMMITTEE_REVIEW: 0.15,
            BillStage.COMMITTEE_MARKUP: 0.35,
            BillStage.COMMITTEE_REPORTED: 0.55,
            BillStage.FLOOR_CONSIDERATION: 0.75,
            BillStage.PASSED_CHAMBER: 0.85,
            BillStage.SENT_TO_OTHER_CHAMBER: 0.85,
            BillStage.OTHER_CHAMBER_COMMITTEE: 0.65,
            BillStage.OTHER_CHAMBER_FLOOR: 0.80,
            BillStage.PASSED_BOTH_CHAMBERS: 0.95,
            BillStage.SENT_TO_PRESIDENT: 0.98,
            BillStage.SIGNED_INTO_LAW: 1.0,
            BillStage.VETOED: 0.0,
            BillStage.WITHDRAWN: 0.0,
            BillStage.DIED: 0.0
        }

    def detect_stage_transition(self, old_status: str, new_status: str,
                              bill_context: Dict[str, str]) -> StageTransitionResult:
        """Detect if a bill has transitioned between legislative stages"""

        try:
            # Parse current and previous stages
            old_stage = self.parse_stage_from_status(old_status)
            new_stage = self.parse_stage_from_status(new_status)

            # Check if there's actually a transition
            if old_stage == new_stage:
                return StageTransitionResult(
                    has_transition=False,
                    from_stage=old_stage,
                    to_stage=new_stage,
                    confidence=0.9,
                    transition_date=None,
                    committee_name=None,
                    vote_details=None,
                    notes="No stage change detected",
                    passage_likelihood=self.passage_probabilities.get(new_stage, 0.1) if new_stage else 0.1
                )

            # Validate transition logic
            is_valid_transition = self._validate_transition(old_stage, new_stage)

            # Use AI to enhance detection and extract details
            ai_analysis = self._get_ai_stage_analysis(old_status, new_status, bill_context)

            # Extract additional details
            committee_name = self._extract_committee_name(new_status)
            vote_details = self._extract_vote_details(new_status)

            # Calculate confidence
            confidence = self._calculate_transition_confidence(
                old_stage, new_stage, is_valid_transition, ai_analysis.get('confidence', 0.7)
            )

            # Generate notes
            notes = ai_analysis.get('notes', f"Transitioned from {old_stage.value if old_stage else 'unknown'} to {new_stage.value if new_stage else 'unknown'}")

            # Get passage likelihood
            passage_likelihood = self.passage_probabilities.get(new_stage, 0.1) if new_stage else 0.1

            # Adjust likelihood based on bill context
            passage_likelihood = self._adjust_passage_likelihood(passage_likelihood, bill_context, ai_analysis)

            return StageTransitionResult(
                has_transition=True,
                from_stage=old_stage,
                to_stage=new_stage,
                confidence=confidence,
                transition_date=datetime.utcnow(),  # Could be enhanced to parse actual dates
                committee_name=committee_name,
                vote_details=vote_details,
                notes=notes,
                passage_likelihood=passage_likelihood
            )

        except Exception as e:
            logger.error(f"Error in stage transition detection: {e}")
            return StageTransitionResult(
                has_transition=False,
                from_stage=None,
                to_stage=None,
                confidence=0.0,
                transition_date=None,
                committee_name=None,
                vote_details=None,
                notes=f"Error in detection: {str(e)}",
                passage_likelihood=0.1
            )

    def parse_stage_from_status(self, status: str) -> Optional[BillStage]:
        """Parse the legislative stage from a status string"""
        if not status:
            return None

        status_lower = status.lower()

        # Check each stage pattern
        for stage, patterns in self.stage_patterns.items():
            for pattern in patterns:
                if re.search(pattern, status_lower):
                    return stage

        # Default fallback based on common keywords
        if 'committee' in status_lower:
            return BillStage.COMMITTEE_REVIEW
        elif 'passed' in status_lower:
            return BillStage.PASSED_CHAMBER
        elif 'introduced' in status_lower or 'referred' in status_lower:
            return BillStage.INTRODUCED

        return None

    def _validate_transition(self, from_stage: Optional[BillStage], to_stage: Optional[BillStage]) -> bool:
        """Validate that a stage transition makes logical sense"""
        if not from_stage or not to_stage:
            return True  # Can't validate without both stages

        # Terminal states can't transition
        if from_stage in [BillStage.SIGNED_INTO_LAW, BillStage.VETOED, BillStage.DIED]:
            return False

        # Some transitions are always valid (e.g., to terminal states)
        if to_stage in [BillStage.WITHDRAWN, BillStage.DIED, BillStage.VETOED]:
            return True

        # Check if transition follows logical order
        try:
            from_index = self.stage_order.index(from_stage)
            to_index = self.stage_order.index(to_stage)

            # Allow forward progression or reasonable backwards movement
            return to_index >= from_index or (from_index - to_index) <= 2

        except ValueError:
            # Stages not in main progression (e.g., withdrawn, died)
            return True

    def _get_ai_stage_analysis(self, old_status: str, new_status: str,
                              bill_context: Dict[str, str]) -> Dict[str, any]:
        """Use AI to analyze stage transition and extract details"""

        try:
            prompt = f"""Analyze this bill status change for legislative stage progression.

BILL CONTEXT:
- Bill: {bill_context.get('bill_number', 'Unknown')}
- Title: {bill_context.get('title', 'Unknown')[:100]}...

STATUS CHANGE:
- Previous: "{old_status}"
- Current: "{new_status}"

Provide JSON analysis with:
1. confidence: float 0-1 (how confident you are this is a real stage change)
2. committee: string (committee name if mentioned, null otherwise)
3. vote_info: string (voting details if mentioned, null otherwise)
4. timeline_estimate: string (estimated time to next major milestone)
5. notes: string (brief description of the transition)
6. significance: "minor", "moderate", "significant", or "major"
7. next_expected_action: string (what's likely to happen next)

Return only JSON, no other text."""

            response = self.openai_client.chat.completions.create(
                model="gpt-4o-mini",
                messages=[
                    {"role": "system", "content": "You are an expert in legislative processes and bill tracking. Provide accurate analysis of stage transitions."},
                    {"role": "user", "content": prompt}
                ],
                temperature=0.1,
                max_tokens=400
            )

            result_text = response.choices[0].message.content.strip()

            # Clean JSON if wrapped in markdown
            if result_text.startswith('```json'):
                result_text = result_text[7:-3].strip()
            elif result_text.startswith('```'):
                result_text = result_text[3:-3].strip()

            return json.loads(result_text)

        except Exception as e:
            logger.error(f"AI stage analysis failed: {e}")
            return {
                'confidence': 0.7,
                'notes': 'AI analysis unavailable',
                'significance': 'moderate'
            }

    def _extract_committee_name(self, status: str) -> Optional[str]:
        """Extract committee name from status string"""
        if not status:
            return None

        # Common committee name patterns
        committee_patterns = [
            r'committee on ([^,\n\.]+)',
            r'([^,\n\.]*committee[^,\n\.]*)',
            r'referred to ([^,\n\.]+)',
            r'([A-Z][a-z]+ (?:and [A-Z][a-z]+ )*Committee)'
        ]

        status_clean = re.sub(r'\s+', ' ', status).strip()

        for pattern in committee_patterns:
            match = re.search(pattern, status_clean, re.IGNORECASE)
            if match:
                committee_name = match.group(1).strip()
                # Clean up common artifacts
                committee_name = re.sub(r'^(the|on)\s+', '', committee_name, flags=re.IGNORECASE)
                if len(committee_name) > 5 and len(committee_name) < 100:  # Reasonable length
                    return committee_name

        return None

    def _extract_vote_details(self, status: str) -> Optional[str]:
        """Extract voting details from status string"""
        if not status:
            return None

        # Vote pattern matching
        vote_patterns = [
            r'(\d+-\d+)',  # e.g., "23-17"
            r'(voice vote)',
            r'(unanimous)',
            r'(passed by (?:a )?vote of \d+-\d+)',
            r'(\d+ yeas?,? \d+ nays?)',
            r'(\d+ in favor,? \d+ against)'
        ]

        for pattern in vote_patterns:
            match = re.search(pattern, status, re.IGNORECASE)
            if match:
                return match.group(1)

        return None

    def _calculate_transition_confidence(self, from_stage: Optional[BillStage],
                                       to_stage: Optional[BillStage],
                                       is_valid: bool, ai_confidence: float) -> float:
        """Calculate confidence score for the transition"""

        base_confidence = 0.7

        # Boost confidence for valid transitions
        if is_valid:
            base_confidence += 0.2

        # Incorporate AI confidence
        combined_confidence = (base_confidence + ai_confidence) / 2

        # Penalize unusual transitions
        if from_stage and to_stage:
            try:
                from_index = self.stage_order.index(from_stage)
                to_index = self.stage_order.index(to_stage)

                # Penalize backwards transitions
                if to_index < from_index:
                    combined_confidence *= 0.7

                # Penalize big jumps
                jump_size = abs(to_index - from_index)
                if jump_size > 3:
                    combined_confidence *= 0.8

            except ValueError:
                # Stage not in standard order
                combined_confidence *= 0.9

        return min(combined_confidence, 1.0)

    def _adjust_passage_likelihood(self, base_likelihood: float, bill_context: Dict[str, str],
                                 ai_analysis: Dict[str, any]) -> float:
        """Adjust passage likelihood based on context"""

        adjusted_likelihood = base_likelihood

        # Consider bill relevance/importance
        if 'relevance_score' in bill_context:
            try:
                relevance = float(bill_context['relevance_score'])
                # Higher relevance slightly increases passage likelihood
                relevance_boost = (relevance / 100.0) * 0.1
                adjusted_likelihood = min(adjusted_likelihood + relevance_boost, 1.0)
            except (ValueError, TypeError):
                pass

        # Consider AI assessment of significance
        significance = ai_analysis.get('significance', 'moderate')
        if significance == 'major':
            adjusted_likelihood = min(adjusted_likelihood * 1.1, 1.0)
        elif significance == 'minor':
            adjusted_likelihood *= 0.95

        return adjusted_likelihood

    def get_stage_timeline_estimate(self, current_stage: BillStage, bill_context: Dict[str, str]) -> str:
        """Estimate timeline for bill progression"""

        stage_timelines = {
            BillStage.INTRODUCED: "2-4 weeks to committee action",
            BillStage.COMMITTEE_REVIEW: "4-12 weeks for committee consideration",
            BillStage.COMMITTEE_MARKUP: "2-4 weeks to committee vote",
            BillStage.COMMITTEE_REPORTED: "2-8 weeks to floor scheduling",
            BillStage.FLOOR_CONSIDERATION: "1-3 weeks for floor vote",
            BillStage.PASSED_CHAMBER: "1-2 weeks to reach other chamber",
            BillStage.SENT_TO_OTHER_CHAMBER: "2-8 weeks for other chamber committee",
            BillStage.OTHER_CHAMBER_COMMITTEE: "4-12 weeks for committee action",
            BillStage.OTHER_CHAMBER_FLOOR: "1-4 weeks for floor consideration",
            BillStage.PASSED_BOTH_CHAMBERS: "5-10 days to reach president",
            BillStage.SENT_TO_PRESIDENT: "10 days for presidential decision",
            BillStage.SIGNED_INTO_LAW: "Law is effective per bill provisions",
            BillStage.VETOED: "Override attempts possible within session",
            BillStage.DIED: "Bill is inactive",
            BillStage.WITHDRAWN: "Bill is inactive"
        }

        return stage_timelines.get(current_stage, "Timeline uncertain")

    def assess_passage_probability(self, current_stage: BillStage, bill_context: Dict[str, str],
                                 vote_details: Optional[str] = None) -> Tuple[float, str]:
        """Assess probability of final passage with reasoning"""

        base_probability = self.passage_probabilities.get(current_stage, 0.1)
        reasoning_parts = [f"Base probability for {current_stage.value}: {base_probability:.0%}"]

        adjusted_probability = base_probability

        # Adjust based on vote margins (if available)
        if vote_details and current_stage in [BillStage.COMMITTEE_REPORTED, BillStage.PASSED_CHAMBER]:
            if 'unanimous' in vote_details.lower():
                adjusted_probability = min(adjusted_probability * 1.2, 1.0)
                reasoning_parts.append("Unanimous vote increases likelihood")
            elif re.search(r'(\d+)-(\d+)', vote_details):
                # Parse vote margin
                match = re.search(r'(\d+)-(\d+)', vote_details)
                if match:
                    yes_votes = int(match.group(1))
                    no_votes = int(match.group(2))
                    total_votes = yes_votes + no_votes
                    margin = (yes_votes - no_votes) / total_votes

                    if margin > 0.6:  # Strong majority
                        adjusted_probability = min(adjusted_probability * 1.15, 1.0)
                        reasoning_parts.append("Strong majority vote increases likelihood")
                    elif margin < 0.2:  # Close vote
                        adjusted_probability *= 0.9
                        reasoning_parts.append("Close vote margin decreases likelihood")

        # Adjust based on bill relevance
        if 'relevance_score' in bill_context:
            try:
                relevance = float(bill_context['relevance_score'])
                if relevance >= 70:
                    adjusted_probability = min(adjusted_probability * 1.05, 1.0)
                    reasoning_parts.append("High relevance score")
            except (ValueError, TypeError):
                pass

        reasoning = ". ".join(reasoning_parts) + "."

        return adjusted_probability, reasoning
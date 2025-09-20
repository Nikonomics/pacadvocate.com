from sqlalchemy.orm import Session
from models.legislation import Bill, Keyword, BillKeywordMatch
from typing import List, Dict, Tuple
import re
import json
from sentence_transformers import SentenceTransformer
import numpy as np

class KeywordMatcher:
    def __init__(self, db: Session):
        self.db = db
        self.model = None  # Will be loaded lazily

    def get_embedding_model(self):
        """Lazy load the sentence transformer model"""
        if self.model is None:
            try:
                self.model = SentenceTransformer('all-MiniLM-L6-v2')
            except Exception as e:
                print(f"Warning: Could not load sentence transformer model: {e}")
                self.model = False  # Mark as unavailable
        return self.model

    def extract_keywords_from_bill(self, bill: Bill) -> List[Dict]:
        """Extract and match keywords from a bill"""
        active_keywords = self.db.query(Keyword).filter(
            Keyword.is_active == True
        ).all()

        text_content = self._get_searchable_text(bill)
        matches = []

        for keyword in active_keywords:
            match_result = self._find_keyword_matches(keyword, text_content)
            if match_result['match_count'] > 0:
                matches.append({
                    'keyword_id': keyword.id,
                    'keyword_term': keyword.term,
                    'category': keyword.category,
                    **match_result
                })

        return matches

    def _get_searchable_text(self, bill: Bill) -> str:
        """Get all searchable text from a bill"""
        text_parts = []

        if bill.title:
            text_parts.append(bill.title)
        if bill.summary:
            text_parts.append(bill.summary)
        if bill.full_text:
            text_parts.append(bill.full_text)

        return " ".join(text_parts).lower()

    def _find_keyword_matches(self, keyword: Keyword, text: str) -> Dict:
        """Find matches for a specific keyword in text"""
        matches = []
        match_locations = []

        # Primary term search
        primary_matches = list(re.finditer(
            rf'\b{re.escape(keyword.term.lower())}\b',
            text,
            re.IGNORECASE
        ))

        for match in primary_matches:
            matches.append({
                'term': keyword.term,
                'start': match.start(),
                'end': match.end(),
                'confidence': 1.0  # Exact match
            })
            match_locations.append({
                'position': match.start(),
                'term': keyword.term,
                'type': 'exact'
            })

        # Synonym search
        if keyword.synonyms:
            try:
                synonyms = json.loads(keyword.synonyms)
                for synonym in synonyms:
                    synonym_matches = list(re.finditer(
                        rf'\b{re.escape(synonym.lower())}\b',
                        text,
                        re.IGNORECASE
                    ))

                    for match in synonym_matches:
                        matches.append({
                            'term': synonym,
                            'start': match.start(),
                            'end': match.end(),
                            'confidence': 0.9  # Synonym match
                        })
                        match_locations.append({
                            'position': match.start(),
                            'term': synonym,
                            'type': 'synonym'
                        })
            except json.JSONDecodeError:
                pass  # Skip if synonyms JSON is malformed

        # Calculate overall confidence
        confidence_score = self._calculate_confidence(matches, keyword, text)

        # Get context snippets
        context_snippet = self._extract_context(matches, text)

        return {
            'match_count': len(matches),
            'match_locations': json.dumps(match_locations),
            'confidence_score': confidence_score,
            'context_snippet': context_snippet
        }

    def _calculate_confidence(self, matches: List[Dict], keyword: Keyword, text: str) -> float:
        """Calculate confidence score for keyword matches"""
        if not matches:
            return 0.0

        # Base confidence from match types
        confidence_sum = sum(match['confidence'] for match in matches)

        # Weight by importance
        weighted_confidence = confidence_sum * keyword.importance_weight

        # Normalize by text length (longer texts dilute confidence)
        text_length_factor = min(1.0, 1000.0 / max(len(text), 1000))

        # Final confidence (capped at 1.0)
        final_confidence = min(1.0, weighted_confidence * text_length_factor / 10)

        return round(final_confidence, 3)

    def _extract_context(self, matches: List[Dict], text: str, context_length: int = 100) -> str:
        """Extract context snippets around matches"""
        if not matches:
            return ""

        # Get the best match (highest confidence)
        best_match = max(matches, key=lambda x: x['confidence'])

        start = max(0, best_match['start'] - context_length)
        end = min(len(text), best_match['end'] + context_length)

        context = text[start:end].strip()

        # Add ellipsis if truncated
        if start > 0:
            context = "..." + context
        if end < len(text):
            context = context + "..."

        return context[:500]  # Limit context length

    def process_bill_keywords(self, bill_id: int) -> int:
        """Process keywords for a specific bill and store matches"""
        bill = self.db.query(Bill).filter(Bill.id == bill_id).first()
        if not bill:
            return 0

        # Clear existing matches
        self.db.query(BillKeywordMatch).filter(
            BillKeywordMatch.bill_id == bill_id
        ).delete()

        matches = self.extract_keywords_from_bill(bill)

        for match in matches:
            bill_keyword_match = BillKeywordMatch(
                bill_id=bill_id,
                keyword_id=match['keyword_id'],
                match_count=match['match_count'],
                match_locations=match['match_locations'],
                confidence_score=match['confidence_score'],
                context_snippet=match['context_snippet']
            )
            self.db.add(bill_keyword_match)

        self.db.commit()
        return len(matches)

    def get_bill_keyword_matches(self, bill_id: int, min_confidence: float = 0.0) -> List[BillKeywordMatch]:
        """Get keyword matches for a bill"""
        query = self.db.query(BillKeywordMatch).filter(
            BillKeywordMatch.bill_id == bill_id,
            BillKeywordMatch.confidence_score >= min_confidence
        )

        return query.order_by(BillKeywordMatch.confidence_score.desc()).all()

    def get_keyword_bill_matches(self, keyword_id: int, min_confidence: float = 0.0) -> List[BillKeywordMatch]:
        """Get bills that match a specific keyword"""
        query = self.db.query(BillKeywordMatch).filter(
            BillKeywordMatch.keyword_id == keyword_id,
            BillKeywordMatch.confidence_score >= min_confidence
        )

        return query.order_by(BillKeywordMatch.confidence_score.desc()).all()

    def find_similar_bills(self, bill_id: int, limit: int = 10) -> List[Tuple[Bill, float]]:
        """Find bills similar to the given bill based on keyword matches"""
        # Get keyword matches for the source bill
        source_matches = self.get_bill_keyword_matches(bill_id)
        if not source_matches:
            return []

        # Get keyword IDs and their confidence scores
        source_keywords = {
            match.keyword_id: match.confidence_score
            for match in source_matches
        }

        # Find other bills with overlapping keywords
        similar_bills = {}

        for keyword_id, confidence in source_keywords.items():
            other_matches = self.db.query(BillKeywordMatch).filter(
                BillKeywordMatch.keyword_id == keyword_id,
                BillKeywordMatch.bill_id != bill_id
            ).all()

            for match in other_matches:
                if match.bill_id not in similar_bills:
                    similar_bills[match.bill_id] = 0

                # Add weighted similarity score
                similar_bills[match.bill_id] += confidence * match.confidence_score

        # Get bills and sort by similarity
        results = []
        for bill_id, similarity_score in similar_bills.items():
            bill = self.db.query(Bill).filter(Bill.id == bill_id).first()
            if bill:
                results.append((bill, similarity_score))

        # Sort by similarity and return top results
        results.sort(key=lambda x: x[1], reverse=True)
        return results[:limit]
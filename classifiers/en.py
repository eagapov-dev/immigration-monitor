"""
English classifier: keyword pre-filter → AI for matches.
"""
import logging
from typing import Optional

from .base import BaseClassifier, ClassificationResult

logger = logging.getLogger(__name__)


class EnglishClassifier(BaseClassifier):
    """
    Hybrid classifier for English text.
    Stage 1: keyword pre-filter (fast, free).
    Stage 2: AI verification for keyword matches.
    """

    def __init__(self, config_en: dict, ai_api_key: Optional[str], model: str):
        super().__init__(ai_api_key, model)
        self.keywords = [self._clean_text(kw) for kw in config_en.get("keywords", [])]
        self.question_markers = [qm.lower() for qm in config_en.get("question_markers", [])]
        self.min_keyword_matches = config_en.get("min_keyword_matches", 1)

    def _classify_keywords(self, text: str) -> ClassificationResult:
        cleaned = self._clean_text(text)
        text_lower = text.lower()
        keyword_matches = sum(1 for kw in self.keywords if self._word_match(kw, cleaned))
        has_question = any(qm in text_lower for qm in self.question_markers)
        is_relevant = keyword_matches >= self.min_keyword_matches
        category = self._detect_category(cleaned)
        return ClassificationResult(
            is_relevant=is_relevant,
            is_question=has_question,
            category=category,
            urgency="medium",
            confidence=min(keyword_matches * 0.2, 1.0),
            method="keywords",
        )

    def classify(self, text: str, include_draft: bool = False) -> ClassificationResult:
        """Keyword pre-filter → AI for matches."""
        keyword_result = self._classify_keywords(text)

        if not keyword_result.is_relevant:
            return keyword_result

        # AI verification for keyword matches
        ai_result = self._call_ai(text, lang_hint="en", include_draft=include_draft)
        if ai_result is None:
            # Fallback to keywords on AI error
            return keyword_result

        ai_result.method = "hybrid"
        return ai_result

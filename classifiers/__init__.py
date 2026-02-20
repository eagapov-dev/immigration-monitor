"""
Modular classifier facade.

Routes to EnglishClassifier or CyrillicClassifier based on source_lang.

Usage:
    from classifiers import Classifier, ClassificationResult
    c = Classifier(config["classification"])
    result = c.classify(text, source_lang="ru")
"""
from .base import ClassificationResult
from .en import EnglishClassifier
from .ru import CyrillicClassifier

__all__ = ["Classifier", "ClassificationResult"]


class Classifier:
    def __init__(self, config: dict):
        ai_key = config.get("anthropic_api_key")
        model = config.get("model", "claude-haiku-4-5-20251001")
        self.en = EnglishClassifier(config.get("en", {}), ai_key, model)
        self.cyrillic = CyrillicClassifier(
            config.get("ru", {}), config.get("uk", {}), ai_key, model
        )

    def classify(
        self, text: str, source_lang: str = "en", include_draft: bool = False
    ) -> ClassificationResult:
        if source_lang in ("ru", "uk", "ru/uk", "uk/ru"):
            return self.cyrillic.classify(text, source_lang, include_draft)
        return self.en.classify(text, include_draft)

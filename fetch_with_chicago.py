#!/usr/bin/env python3
"""Fetch posts with Chicago localization filter."""
import logging
import asyncio
import yaml
from datetime import datetime, timezone
from sources.reddit import RedditSource
from classifier import Classifier
from database import Database

# Setup logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Chicago-related keywords
CHICAGO_KEYWORDS = [
    'chicago',
    'schaumburg',
    'illinois',
    ' il ',
    ' il,',
    ' il.',
    'chicagoland',
    'cook county',
    'naperville',
    'evanston',
    'aurora',
    'joliet',
]

def is_chicago_related(text):
    """Check if text mentions Chicago area."""
    text_lower = text.lower()
    return any(kw in text_lower for kw in CHICAGO_KEYWORDS)

def main():
    # Load config
    with open("config.yaml", "r", encoding="utf-8") as f:
        config = yaml.safe_load(f)

    # Create components
    reddit_config = config.get("reddit", {})
    monitor = RedditSource(reddit_config)
    classifier = Classifier(config.get("classification", {}))
    db = Database(config.get("database", {}).get("path", "data/processed.db"))

    # Fetch posts from last 72 hours
    logger.info("Fetching posts from last 72 hours...")
    items = asyncio.run(monitor.fetch(lookback_hours=72))

    logger.info(f"Total items fetched: {len(items)}")

    # Categorize
    all_new = []
    chicago_posts = []
    chicago_questions = []
    all_questions = []

    print(f"\n{'='*90}")
    print(f"🔍 Обработка {len(items)} постов с фильтром по Чикаго...")
    print(f"{'='*90}\n")

    for i, item in enumerate(items, 1):
        # Skip if already processed
        if db.is_processed(item.id):
            continue

        # Skip short texts
        min_length = config.get("notifications", {}).get("min_text_length", 30)
        if len(item.text) < min_length:
            import json
            db.mark_processed(
                item.id, item.source, item.channel, item.text, item.url,
                classification=json.dumps({"is_relevant": False, "reason": "too_short"})
            )
            continue

        # Check if Chicago-related
        is_chicago = is_chicago_related(item.text)

        # Classify
        result = classifier.classify(text=item.text, source_lang="en", include_draft=False)

        # Mark as processed
        import json
        classification_json = json.dumps({
            "is_relevant": result.is_relevant,
            "is_question": result.is_question,
            "category": result.category,
            "urgency": result.urgency,
            "is_chicago": is_chicago,  # Add Chicago flag
        })
        db.mark_processed(
            item.id, item.source, item.channel, item.text, item.url,
            classification=classification_json,
        )

        all_new.append(item)

        if result.is_relevant:
            if is_chicago:
                chicago_posts.append(item)

                if result.is_question:
                    chicago_questions.append(item)

                    # Show immediately
                    print(f"🏙️  ЧИКАГО ВОПРОС: [{result.category.upper()}] {item.channel}")
                    print(f"   {item.title[:80]}")
                    print(f"   🔗 {item.url}")

                    # Show where Chicago mentioned
                    text_lower = item.text.lower()
                    for kw in CHICAGO_KEYWORDS:
                        if kw in text_lower:
                            idx = text_lower.find(kw)
                            start = max(0, idx - 40)
                            end = min(len(item.text), idx + 60)
                            context = item.text[start:end].replace('\n', ' ')
                            print(f"   💬 ...{context}...")
                            break
                    print()

            if result.is_question:
                all_questions.append(item)

        # Progress
        if i % 50 == 0:
            print(f"⏳ Обработано {i}/{len(items)}...")

    db.close()

    # Final statistics
    print(f"\n{'='*90}")
    print(f"📊 ИТОГОВАЯ СТАТИСТИКА")
    print(f"{'='*90}\n")

    print(f"Всего постов обработано: {len(all_new)}")
    print(f"Всего релевантных вопросов: {len(all_questions)}")
    print(f"\n🏙️  ЧИКАГО:")
    print(f"  Постов упоминающих Чикаго: {len(chicago_posts)}")
    print(f"  Вопросов про Чикаго: {len(chicago_questions)}")
    print(f"\n📈 ПРОЦЕНТ:")
    if all_questions:
        chicago_percent = len(chicago_questions) * 100 / len(all_questions)
        print(f"  {chicago_percent:.1f}% вопросов упоминают Чикаго/Иллинойс")

    print(f"\n⏱️  ПРОГНОЗ:")
    print(f"  Чикаго вопросов в день: ~{len(chicago_questions)/3:.1f}")
    print(f"  Чикаго вопросов в месяц: ~{len(chicago_questions)/3*30:.0f}")
    print(f"\n  Всего вопросов в день: ~{len(all_questions)/3:.1f}")
    print(f"  Всего вопросов в месяц: ~{len(all_questions)/3*30:.0f}")

    # Breakdown by subreddit
    from collections import defaultdict
    chicago_by_sub = defaultdict(int)
    for item in chicago_questions:
        chicago_by_sub[item.channel] += 1

    if chicago_by_sub:
        print(f"\n📍 ЧИКАГО ВОПРОСЫ ПО SUBREDDIT:")
        for sub, count in sorted(chicago_by_sub.items(), key=lambda x: x[1], reverse=True):
            print(f"  {sub}: {count} вопросов")

    print(f"\n{'='*90}\n")

    # Save Chicago questions to file
    with open("chicago_questions.txt", "w", encoding="utf-8") as f:
        f.write(f"ВОПРОСЫ ПРО ЧИКАГО/ИЛЛИНОЙС\n")
        f.write(f"{'='*90}\n\n")
        f.write(f"Найдено: {len(chicago_questions)} вопросов за 72 часа\n\n")

        for i, item in enumerate(chicago_questions, 1):
            f.write(f"{i}. {item.channel}\n")
            f.write(f"   {item.title}\n")
            f.write(f"   {item.url}\n\n")

    print(f"✅ Чикаго вопросы сохранены в: chicago_questions.txt\n")

if __name__ == "__main__":
    main()

#!/usr/bin/env python3
"""Fetch more posts from Reddit with longer lookback period."""
import logging
import yaml
from datetime import datetime, timezone
import asyncio
from sources.reddit import RedditSource
from classifier import Classifier
from database import Database

# Setup logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

def main():
    # Load config
    with open("config.yaml", "r", encoding="utf-8") as f:
        config = yaml.safe_load(f)

    # Create components
    reddit_config = config.get("reddit", {})
    monitor = RedditSource(reddit_config)
    classifier = Classifier(config.get("classification", {}))
    db = Database(config.get("database", {}).get("path", "data/processed.db"))

    # Fetch posts from last 72 hours (3 days)
    logger.info("Fetching posts from last 72 hours...")
    items = asyncio.run(monitor.fetch(lookback_hours=72))

    logger.info(f"Total items fetched: {len(items)}")

    new_count = 0
    relevant_count = 0

    print(f"\n{'='*80}")
    print(f"🔍 Обработка {len(items)} постов...")
    print(f"{'='*80}\n")

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

        # Classify
        result = classifier.classify(text=item.text, source_lang="en", include_draft=False)

        # Mark as processed
        import json
        classification_json = json.dumps({
            "is_relevant": result.is_relevant,
            "is_question": result.is_question,
            "category": result.category,
            "urgency": result.urgency,
        })
        db.mark_processed(
            item.id, item.source, item.channel, item.text, item.url,
            classification=classification_json,
        )
        new_count += 1

        if result.is_relevant:
            relevant_count += 1

            # Calculate time ago
            now = datetime.now(timezone.utc)
            time_diff = now - item.created_at
            hours_ago = time_diff.total_seconds() / 3600

            if hours_ago < 1:
                time_ago = f"{int(time_diff.total_seconds() / 60)} минут назад"
            elif hours_ago < 24:
                time_ago = f"{int(hours_ago)} часов назад"
            else:
                days = int(hours_ago / 24)
                time_ago = f"{days} дней назад"

            question_mark = "❓" if result.is_question else "📄"

            print(f"{question_mark} [{result.category.upper()}] {item.channel} - {time_ago}")
            print(f"   {item.title[:80]}")
            print(f"   🔗 {item.url}")
            print()

        # Progress indicator
        if i % 20 == 0:
            print(f"⏳ Обработано {i}/{len(items)}...")

    db.close()

    print(f"\n{'='*80}")
    print(f"✅ Готово!")
    print(f"📊 Обработано новых: {new_count}")
    print(f"🎯 Релевантных: {relevant_count}")
    print(f"{'='*80}\n")

if __name__ == "__main__":
    main()

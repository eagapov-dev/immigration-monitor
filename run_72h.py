#!/usr/bin/env python3
"""Run full monitoring cycle with 72h lookback."""
import asyncio
import yaml
import logging
import json
import sqlite3
from collections import Counter

from main import ImmigrationMonitor, setup_logging
from sources.reddit import RedditSource


async def main():
    with open("config.yaml", "r", encoding="utf-8") as f:
        config = yaml.safe_load(f)

    setup_logging(config)

    monitor = ImmigrationMonitor(config)

    print("\n🔍 Запуск парсинга за 72 часа...\n")

    # Find the Reddit source and run it with 72h lookback
    for source in monitor.sources:
        if isinstance(source, RedditSource):
            await monitor.process_source(source, lookback_hours=72)

    await monitor.cleanup()

    # Show location stats
    conn = sqlite3.connect("data/processed.db")
    cursor = conn.cursor()
    cursor.execute("SELECT group_name, classification FROM processed_items WHERE classification IS NOT NULL")

    location_counts = Counter()
    chicago_questions = []
    all_questions = 0

    for group, clf_json in cursor.fetchall():
        clf = json.loads(clf_json)
        if not clf.get("is_relevant") or not clf.get("is_question"):
            continue
        all_questions += 1
        loc = clf.get("location", "")
        if loc:
            location_counts[loc] += 1
        if loc == "Chicago, IL":
            chicago_questions.append(group)

    conn.close()

    print(f"\n{'='*70}")
    print(f"📊 ЛОКАЛИЗАЦИЯ (все вопросы в БД)")
    print(f"{'='*70}")
    print(f"Всего вопросов: {all_questions}")
    print(f"С определенной локацией: {sum(location_counts.values())}")
    print(f"\n📍 Распределение по локациям:")
    for loc, count in location_counts.most_common():
        chicago_mark = " ⭐" if loc == "Chicago, IL" else ""
        print(f"  {loc}{chicago_mark}: {count}")


if __name__ == "__main__":
    asyncio.run(main())

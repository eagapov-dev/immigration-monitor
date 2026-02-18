#!/usr/bin/env python3
"""Show posts that matched keyword criteria."""
import sqlite3
import json
from datetime import datetime

def main():
    # Connect to database
    conn = sqlite3.connect("data/processed.db")
    cursor = conn.cursor()

    # Get all processed items with classification
    cursor.execute("""
        SELECT id, source, group_name, text_preview, url, classification, processed_at, notified
        FROM processed_items
        ORDER BY processed_at DESC
        LIMIT 50
    """)

    items = cursor.fetchall()

    print(f"\n{'='*80}")
    print(f"Найдено {len(items)} обработанных постов")
    print(f"{'='*80}\n")

    relevant_count = 0
    question_count = 0

    for item in items:
        item_id, source, group_name, text_preview, url, classification_json, processed_at, notified = item

        # Parse classification
        if classification_json:
            classification = json.loads(classification_json)
            is_relevant = classification.get('is_relevant', False)
            is_question = classification.get('is_question', False)
            category = classification.get('category', 'unknown')
            urgency = classification.get('urgency', 'unknown')

            # Only show relevant posts
            if is_relevant:
                relevant_count += 1
                if is_question:
                    question_count += 1

                print(f"\n{'─'*80}")
                print(f"🎯 Релевантный пост #{relevant_count}")
                print(f"{'─'*80}")
                print(f"Источник: {group_name} ({source})")
                print(f"Категория: {category.upper()}")
                print(f"Срочность: {urgency}")
                print(f"Это вопрос: {'✅ ДА' if is_question else '❌ НЕТ'}")
                print(f"Уведомление отправлено: {'✅ ДА' if notified else '❌ НЕТ'}")
                print(f"Обработан: {processed_at}")
                print(f"\n📝 Текст (первые 400 символов):")
                print(f"{text_preview[:400]}...")
                print(f"\n🔗 URL: {url}")

    conn.close()

    print(f"\n{'='*80}")
    print(f"📊 Статистика:")
    print(f"  Всего обработано: {len(items)}")
    print(f"  Релевантных: {relevant_count}")
    print(f"  Из них вопросов: {question_count}")
    print(f"{'='*80}\n")

if __name__ == "__main__":
    main()

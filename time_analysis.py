#!/usr/bin/env python3
"""Analyze time distribution of questions."""
import sqlite3
import json
from datetime import datetime, timezone
from collections import defaultdict

def main():
    conn = sqlite3.connect("data/processed.db")
    cursor = conn.cursor()

    # Get all relevant questions with timestamps
    cursor.execute("""
        SELECT id, source, group_name, text_preview, url, classification, processed_at
        FROM processed_items
        WHERE classification IS NOT NULL
        ORDER BY processed_at DESC
    """)

    items = cursor.fetchall()
    conn.close()

    questions_only = []

    for item in items:
        item_id, source, group_name, text_preview, url, classification_json, processed_at = item

        if not classification_json:
            continue

        classification = json.loads(classification_json)
        is_relevant = classification.get('is_relevant', False)
        is_question = classification.get('is_question', False)

        if is_relevant and is_question:
            questions_only.append({
                'id': item_id,
                'group': group_name,
                'text': text_preview,
                'url': url,
                'processed_at': processed_at,
                'category': classification.get('category', 'other')
            })

    if not questions_only:
        print("No questions found!")
        return

    # Parse timestamps (they're in format "2026-02-16 14:36:10")
    now = datetime.now(timezone.utc)

    # We need to extract creation time from URL or text
    # For now, let's show when they were processed

    print(f"\n{'='*90}")
    print(f"⏰ ВРЕМЕННОЙ АНАЛИЗ ВОПРОСОВ")
    print(f"{'='*90}\n")

    print(f"Всего вопросов: {len(questions_only)}")

    # Get first and last
    timestamps = [q['processed_at'] for q in questions_only]
    first_time = min(timestamps)
    last_time = max(timestamps)

    print(f"Первый вопрос обработан: {first_time}")
    print(f"Последний вопрос обработан: {last_time}")

    # Parse to calculate difference
    first_dt = datetime.strptime(first_time, "%Y-%m-%d %H:%M:%S")
    last_dt = datetime.strptime(last_time, "%Y-%m-%d %H:%M:%S")
    time_diff = last_dt - first_dt

    hours_span = time_diff.total_seconds() / 3600

    print(f"\n⏱️  Временной диапазон: {time_diff}")
    print(f"⏱️  Это примерно: {hours_span:.1f} часов ({hours_span/24:.1f} дней)")

    # Since we fetched with lookback_hours=72, posts are from last 72 hours
    print(f"\n📅 ВАЖНО: Мы запрашивали посты за последние 72 часа (3 дня)")
    print(f"   Значит эти 92 вопроса были опубликованы за последние 72 часа")

    # Calculate rate
    questions_per_hour = len(questions_only) / 72
    questions_per_day = questions_per_hour * 24

    print(f"\n📊 СТАТИСТИКА:")
    print(f"   92 вопроса за 72 часа (3 дня)")
    print(f"   ≈ {questions_per_hour:.1f} вопросов в час")
    print(f"   ≈ {questions_per_day:.1f} вопросов в день")
    print(f"   ≈ {questions_per_day * 7:.0f} вопросов в неделю")
    print(f"   ≈ {questions_per_day * 30:.0f} вопросов в месяц")

    # Breakdown by subreddit
    by_subreddit = defaultdict(int)
    for q in questions_only:
        by_subreddit[q['group']] += 1

    print(f"\n📍 РАСПРЕДЕЛЕНИЕ ПО SUBREDDIT:")
    for sub, count in sorted(by_subreddit.items(), key=lambda x: x[1], reverse=True):
        per_day = (count / 72) * 24
        print(f"   r/{sub}: {count} вопросов ({per_day:.1f}/день)")

    # Calculate for Liberum Law (assuming 68% are good fit)
    liberum_questions = len(questions_only) * 0.68
    liberum_per_day = liberum_questions / 3
    liberum_per_week = liberum_per_day * 7
    liberum_per_month = liberum_per_day * 30

    print(f"\n{'='*90}")
    print(f"💼 ДЛЯ LIBERUM LAW (68% подходят):")
    print(f"{'='*90}")
    print(f"   Релевантных вопросов за 3 дня: {int(liberum_questions)}")
    print(f"   ≈ {liberum_per_day:.1f} лидов в день")
    print(f"   ≈ {liberum_per_week:.0f} лидов в неделю")
    print(f"   ≈ {liberum_per_month:.0f} лидов в месяц")

    # If conversion rate is 5-10%
    print(f"\n💰 При конверсии 5-10% в платных клиентов:")
    print(f"   5%:  {liberum_per_month * 0.05:.0f} новых клиентов в месяц")
    print(f"   10%: {liberum_per_month * 0.10:.0f} новых клиентов в месяц")

    print(f"\n{'='*90}\n")

if __name__ == "__main__":
    main()

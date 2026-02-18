#!/usr/bin/env python3
"""Add Chicago localization filter and re-analyze."""
import sqlite3
import json
import re

def main():
    conn = sqlite3.connect("data/processed.db")
    cursor = conn.cursor()

    # Get all relevant questions
    cursor.execute("""
        SELECT id, source, group_name, text_preview, url, classification
        FROM processed_items
        WHERE classification IS NOT NULL
        ORDER BY processed_at DESC
    """)

    items = cursor.fetchall()

    # Chicago-related keywords
    chicago_keywords = [
        'chicago',
        'schaumburg',  # Liberum Law location
        'illinois',
        'il ',
        ' il,',
        'chicagoland',
        'cook county',
        'naperville',
        'aurora',
        'joliet',
        'rockford',
        'evanston',
        'arlington heights',
    ]

    all_questions = []
    chicago_questions = []
    non_chicago_immigration_questions = []

    for item in items:
        item_id, source, group_name, text_preview, url, classification_json = item

        if not classification_json:
            continue

        classification = json.loads(classification_json)
        is_relevant = classification.get('is_relevant', False)
        is_question = classification.get('is_question', False)

        if not (is_relevant and is_question):
            continue

        text_lower = text_preview.lower()
        title = text_preview.split('\n')[0]

        # Check if Chicago-related
        is_chicago = any(kw in text_lower for kw in chicago_keywords)

        # Skip false positives from r/chicago that are not immigration-related
        if group_name == 'chicago':
            # Must have strong immigration keywords
            immigration_keywords = [
                'visa', 'green card', 'greencard', 'h1b', 'h-1b',
                'immigration', 'uscis', 'citizenship', 'asylum',
                'deportation', 'i-485', 'i-130', 'naturalization'
            ]
            has_immigration = any(kw in text_lower for kw in immigration_keywords)

            if not has_immigration:
                continue  # Skip non-immigration posts from r/chicago

        post_data = {
            'id': item_id,
            'title': title[:150],
            'group': group_name,
            'url': url,
            'text': text_preview,
            'category': classification.get('category', 'other'),
            'is_chicago': is_chicago
        }

        all_questions.append(post_data)

        if is_chicago:
            chicago_questions.append(post_data)
        elif group_name != 'chicago':  # Immigration question but not Chicago-related
            non_chicago_immigration_questions.append(post_data)

    conn.close()

    # Print results
    print(f"\n{'='*90}")
    print(f"📍 АНАЛИЗ С ЛОКАЛИЗАЦИЕЙ ПО ЧИКАГО")
    print(f"{'='*90}\n")

    print(f"Всего релевантных вопросов: {len(all_questions)}")
    print(f"🏙️  Упоминают Чикаго/Иллинойс: {len(chicago_questions)} ({len(chicago_questions)*100//len(all_questions) if all_questions else 0}%)")
    print(f"🌎 Другие локации/не указано: {len(non_chicago_immigration_questions)}\n")

    # Show Chicago questions
    if chicago_questions:
        print(f"{'='*90}")
        print(f"🏙️  ВОПРОСЫ ПРО ЧИКАГО/ИЛЛИНОЙС ({len(chicago_questions)} шт.)")
        print(f"{'='*90}\n")

        for i, q in enumerate(chicago_questions, 1):
            print(f"{i}. [{q['category'].upper()}] r/{q['group']}")
            print(f"   {q['title']}")
            print(f"   🔗 {q['url']}")

            # Show where Chicago was mentioned
            text_lower = q['text'].lower()
            for kw in chicago_keywords:
                if kw in text_lower:
                    # Find context
                    idx = text_lower.find(kw)
                    start = max(0, idx - 50)
                    end = min(len(text_lower), idx + 50)
                    context = q['text'][start:end].replace('\n', ' ')
                    print(f"   💬 ...{context}...")
                    break
            print()

    # Statistics for Liberum Law
    print(f"\n{'='*90}")
    print(f"💼 ДЛЯ LIBERUM LAW (офис в Schaumburg, IL)")
    print(f"{'='*90}\n")

    # Liberum can work with all US clients (remotely) but Chicago is priority
    liberum_fit_chicago = len(chicago_questions) * 0.68  # 68% fit rate
    liberum_fit_total = len(all_questions) * 0.68

    print(f"Стратегия 1: ТОЛЬКО локальные (Чикаго) клиенты")
    print(f"  Вопросов из Чикаго за 3 дня: {len(chicago_questions)}")
    print(f"  Подходят для Liberum: ~{int(liberum_fit_chicago)}")
    print(f"  В день: ~{liberum_fit_chicago/3:.1f} лидов")
    print(f"  В месяц: ~{liberum_fit_chicago/3*30:.0f} лидов\n")

    print(f"Стратегия 2: ВСЕ США (удаленно)")
    print(f"  Всего вопросов за 3 дня: {len(all_questions)}")
    print(f"  Подходят для Liberum: ~{int(liberum_fit_total)}")
    print(f"  В день: ~{liberum_fit_total/3:.1f} лидов")
    print(f"  В месяц: ~{liberum_fit_total/3*30:.0f} лидов\n")

    print(f"Стратегия 3: ПРИОРИТЕТ Чикаго + остальные США")
    print(f"  Чикаго (приоритет 1): ~{liberum_fit_chicago/3:.1f} лидов/день")
    print(f"  Остальные США (приоритет 2): ~{(liberum_fit_total-liberum_fit_chicago)/3:.1f} лидов/день")
    print(f"  ИТОГО: ~{liberum_fit_total/3:.1f} лидов/день\n")

    # Save to file
    with open("chicago_analysis.txt", "w", encoding="utf-8") as f:
        f.write(f"АНАЛИЗ С ЛОКАЛИЗАЦИЕЙ ПО ЧИКАГО\n")
        f.write(f"{'='*90}\n\n")

        f.write(f"Всего вопросов: {len(all_questions)}\n")
        f.write(f"Упоминают Чикаго: {len(chicago_questions)}\n\n")

        f.write(f"ВОПРОСЫ ПРО ЧИКАГО:\n")
        f.write(f"{'='*90}\n\n")

        for i, q in enumerate(chicago_questions, 1):
            f.write(f"{i}. [{q['category'].upper()}] r/{q['group']}\n")
            f.write(f"   {q['title']}\n")
            f.write(f"   {q['url']}\n\n")

    print(f"✅ Анализ сохранен в: chicago_analysis.txt\n")

if __name__ == "__main__":
    main()

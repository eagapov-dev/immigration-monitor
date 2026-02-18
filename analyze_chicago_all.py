#!/usr/bin/env python3
"""Analyze ALL database for Chicago mentions."""
import sqlite3
import json

# Chicago keywords
CHICAGO_KW = ['chicago', 'schaumburg', 'illinois', ' il ', ' il,', 'chicagoland', 'cook county', 'naperville', 'evanston']

conn = sqlite3.connect('data/processed.db')
cursor = conn.cursor()

# Get ALL items
cursor.execute('SELECT id, source, group_name, text_preview, url, classification FROM processed_items')
items = cursor.fetchall()
conn.close()

chicago_questions = []
all_questions = []

for item in items:
    item_id, source, group_name, text_preview, url, classification_json = item

    if not classification_json:
        continue

    classification = json.loads(classification_json)
    is_relevant = classification.get('is_relevant', False)
    is_question = classification.get('is_question', False)

    if not (is_relevant and is_question):
        continue

    all_questions.append(item)

    # Check Chicago
    text_lower = text_preview.lower()
    if any(kw in text_lower for kw in CHICAGO_KW):
        chicago_questions.append({
            'group': group_name,
            'title': text_preview.split('\n')[0][:120],
            'url': url,
            'text': text_preview,
            'category': classification.get('category', 'other')
        })

print(f"\n{'='*90}")
print(f"📊 АНАЛИЗ ВСЕЙ БАЗЫ ДАННЫХ")
print(f"{'='*90}\n")
print(f"Всего релевантных вопросов: {len(all_questions)}")
print(f"🏙️  Упоминают Чикаго/Иллинойс: {len(chicago_questions)}")
if all_questions:
    percent = len(chicago_questions)*100//len(all_questions)
    print(f"📈 Процент: {percent}%\n")

if chicago_questions:
    print(f"{'='*90}")
    print(f"🏙️  ВОПРОСЫ ПРО ЧИКАГО ({len(chicago_questions)} шт.)")
    print(f"{'='*90}\n")

    for i, q in enumerate(chicago_questions, 1):
        print(f"{i}. [{q['category'].upper()}] r/{q['group']}")
        print(f"   {q['title']}")
        print(f"   🔗 {q['url']}")

        # Show context
        text_lower = q['text'].lower()
        for kw in CHICAGO_KW:
            if kw in text_lower:
                idx = text_lower.find(kw)
                start = max(0, idx - 50)
                end = min(len(q['text']), idx + 70)
                context = q['text'][start:end].replace('\n', ' ')
                print(f"   💬 ...{context}...")
                break
        print()

print(f"\n⏱️  ЗА 3 ДНЯ (прогноз):")
print(f"  Чикаго вопросов в день: ~{len(chicago_questions)/3:.1f}")
print(f"  Чикаго вопросов в месяц: ~{len(chicago_questions)/3*30:.0f}")
print(f"  Всего вопросов в день: ~{len(all_questions)/3:.1f}")
print(f"  Всего вопросов в месяц: ~{len(all_questions)/3*30:.0f}\n")

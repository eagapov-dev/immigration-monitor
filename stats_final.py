#!/usr/bin/env python3
import sqlite3, json
from collections import Counter

conn = sqlite3.connect('data/processed.db')
cursor = conn.cursor()
cursor.execute('SELECT group_name, text_preview, url, classification FROM processed_items WHERE classification IS NOT NULL')

total = 0
questions = []
by_subreddit = Counter()
by_category = Counter()
chicago_q = []
located_q = []

for group, text, url, clf_json in cursor.fetchall():
    total += 1
    clf = json.loads(clf_json)
    if not clf.get('is_relevant') or not clf.get('is_question'):
        continue
    loc = clf.get('location', '')
    cat = clf.get('category', 'other')
    title = text.split('\n')[0][:90]
    questions.append((group, title, url, cat, loc))
    by_subreddit[group] += 1
    by_category[cat] += 1
    if loc:
        located_q.append((group, title, url, cat, loc))
    if loc == 'Chicago, IL':
        chicago_q.append((group, title, url, cat))

conn.close()

q = len(questions)
sep = '='*70

print(f"\n{sep}")
print(f"ИТОГО ЗА 72 ЧАСА (3 ДНЯ)")
print(f"{sep}")
print(f"Постов обработано:     {total}")
print(f"Релевантных вопросов:  {q}")
print(f"  В день:              ~{q//3}")
print(f"  В месяц:             ~{q//3*30}")
print()
print(f"С локацией:            {len(located_q)} ({len(located_q)*100//q}%)")
print(f"Без локации:           {q - len(located_q)} ({(q-len(located_q))*100//q}%)")
print()
print(f"📍 CHICAGO:            {len(chicago_q)} за 3 дня (~{len(chicago_q)/3:.1f}/день, ~{len(chicago_q)/3*30:.0f}/месяц)")

print(f"\nПО SUBREDDIT:")
for sub, cnt in by_subreddit.most_common():
    print(f"  r/{sub}: {cnt} ({cnt/3:.1f}/день)")

print(f"\nПО КАТЕГОРИИ:")
for cat, cnt in by_category.most_common():
    print(f"  {cat}: {cnt}")

print(f"\n{'='*70}")
print(f"🏙️  CHICAGO ВОПРОСЫ ({len(chicago_q)} шт.):")
print(f"{'='*70}")
for group, title, url, cat in chicago_q:
    print(f"  [{cat.upper()}] r/{group}")
    print(f"  {title}")
    print(f"  {url}")
    print()

print(f"{'='*70}")
print(f"📍 ВСЕ ВОПРОСЫ С ЛОКАЦИЕЙ ({len(located_q)} шт.):")
print(f"{'='*70}")
for group, title, url, cat, loc in located_q:
    star = ' ⭐' if loc == 'Chicago, IL' else ''
    print(f"  [{cat.upper()}] 📍 {loc}{star} | r/{group}")
    print(f"  {title}")
    print()

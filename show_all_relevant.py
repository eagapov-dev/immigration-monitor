#!/usr/bin/env python3
"""Show all relevant posts with timestamps and links."""
import sqlite3
import json
from datetime import datetime, timezone

def main():
    # Connect to database
    conn = sqlite3.connect("data/processed.db")
    cursor = conn.cursor()

    # Get all relevant posts
    cursor.execute("""
        SELECT id, source, group_name, text_preview, url, classification, processed_at
        FROM processed_items
        WHERE classification IS NOT NULL
        ORDER BY processed_at DESC
    """)

    items = cursor.fetchall()

    relevant_posts = []
    questions = []

    for item in items:
        item_id, source, group_name, text_preview, url, classification_json, processed_at = item

        if classification_json:
            classification = json.loads(classification_json)
            is_relevant = classification.get('is_relevant', False)

            if is_relevant:
                is_question = classification.get('is_question', False)
                category = classification.get('category', 'other')
                urgency = classification.get('urgency', 'medium')

                post_data = {
                    'id': item_id,
                    'source': source,
                    'group': group_name,
                    'text': text_preview,
                    'url': url,
                    'category': category,
                    'urgency': urgency,
                    'is_question': is_question,
                    'processed_at': processed_at
                }

                relevant_posts.append(post_data)
                if is_question:
                    questions.append(post_data)

    conn.close()

    # Print summary
    print(f"\n{'='*90}")
    print(f"📊 СТАТИСТИКА")
    print(f"{'='*90}")
    print(f"Всего релевантных постов: {len(relevant_posts)}")
    print(f"Из них вопросов: {len(questions)}")
    print(f"{'='*90}\n")

    # Print questions first
    if questions:
        print(f"\n{'🔥'*30}")
        print(f"❓ ВОПРОСЫ (ГОРЯЧИЕ ЛИДЫ) - {len(questions)} шт.")
        print(f"{'🔥'*30}\n")

        for i, post in enumerate(questions, 1):
            # Parse title from text
            title = post['text'].split('\n')[0][:100]

            print(f"{i}. [{post['category'].upper()}] 🔥 r/{post['group']}")
            print(f"   {title}")
            print(f"   🔗 {post['url']}")
            print()

    # Print other relevant posts
    other_posts = [p for p in relevant_posts if not p['is_question']]
    if other_posts:
        print(f"\n{'─'*90}")
        print(f"📄 ДРУГИЕ РЕЛЕВАНТНЫЕ ПОСТЫ - {len(other_posts)} шт.")
        print(f"{'─'*90}\n")

        for i, post in enumerate(other_posts, 1):
            title = post['text'].split('\n')[0][:100]

            print(f"{i}. [{post['category'].upper()}] r/{post['group']}")
            print(f"   {title}")
            print(f"   🔗 {post['url']}")
            print()

    # Export to file
    with open("relevant_posts.txt", "w", encoding="utf-8") as f:
        f.write(f"РЕЛЕВАНТНЫЕ ПОСТЫ ПО ИММИГРАЦИИ\n")
        f.write(f"Дата: {datetime.now().strftime('%Y-%m-%d %H:%M')}\n")
        f.write(f"{'='*90}\n\n")

        f.write(f"СТАТИСТИКА:\n")
        f.write(f"  Всего релевантных: {len(relevant_posts)}\n")
        f.write(f"  Вопросов: {len(questions)}\n")
        f.write(f"  Других: {len(other_posts)}\n\n")

        f.write(f"{'='*90}\n")
        f.write(f"ВОПРОСЫ (ГОРЯЧИЕ ЛИДЫ)\n")
        f.write(f"{'='*90}\n\n")

        for i, post in enumerate(questions, 1):
            title = post['text'].split('\n')[0][:100]
            f.write(f"{i}. [{post['category'].upper()}] r/{post['group']}\n")
            f.write(f"   {title}\n")
            f.write(f"   {post['url']}\n\n")

        f.write(f"\n{'='*90}\n")
        f.write(f"ДРУГИЕ РЕЛЕВАНТНЫЕ ПОСТЫ\n")
        f.write(f"{'='*90}\n\n")

        for i, post in enumerate(other_posts, 1):
            title = post['text'].split('\n')[0][:100]
            f.write(f"{i}. [{post['category'].upper()}] r/{post['group']}\n")
            f.write(f"   {title}\n")
            f.write(f"   {post['url']}\n\n")

    print(f"✅ Список сохранен в файл: relevant_posts.txt\n")

if __name__ == "__main__":
    main()

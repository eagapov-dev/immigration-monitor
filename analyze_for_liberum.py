#!/usr/bin/env python3
"""Analyze which questions are good fit for Liberum Law."""
import sqlite3
import json

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

    # Liberum Law practice areas
    liberum_areas = {
        "citizenship": ["citizenship", "naturalization", "n-400", "n400"],
        "green_card": ["green card", "greencard", "i-485", "i485", "permanent resident", "adjustment of status"],
        "work_visa": ["h1b", "h-1b", "h4", "h-4", "o-1", "o1", "eb-1", "eb1", "eb-2", "eb2", "eb-3", "eb3", "work permit", "ead", "i-140", "i140"],
        "business_visa": ["entrepreneur", "business", "e-2", "e2", "l-1", "l1"],
        "asylum": ["asylum", "refugee", "persecution", "tps", "temporary protected status"],
        "parole": ["parole", "u4u", "uniting for ukraine"],
        "family": ["i-130", "i130", "k-1", "k1", "spouse", "marriage", "family"],
        "deportation": ["deportation", "removal", "ice", "detained", "undocumented", "overstay", "out of status"],
        "general": ["lawyer", "attorney", "help", "advice", "confused", "need guidance"]
    }

    # Categories Liberum can handle well
    can_handle = []
    perfect_fit = []
    maybe_fit = []
    not_fit = []

    questions_only = []

    for item in items:
        item_id, source, group_name, text_preview, url, classification_json = item

        if not classification_json:
            continue

        classification = json.loads(classification_json)
        is_relevant = classification.get('is_relevant', False)
        is_question = classification.get('is_question', False)

        if not (is_relevant and is_question):
            continue

        questions_only.append(item)

        text_lower = text_preview.lower()

        # Check which areas match
        matching_areas = []
        for area, keywords in liberum_areas.items():
            if any(kw in text_lower for kw in keywords):
                matching_areas.append(area)

        # Title
        title = text_preview.split('\n')[0][:100]

        post_data = {
            'title': title,
            'url': url,
            'group': group_name,
            'text': text_preview,
            'areas': matching_areas
        }

        # Categorize by fit
        if "deportation" in matching_areas or "removal" in text_lower or "ice" in text_lower or "detained" in text_lower:
            # Deportation defense - they can handle but it's urgent/complex
            if any(area in matching_areas for area in ["asylum", "green_card", "citizenship", "work_visa"]):
                # Deportation + other path = perfect fit (complex case)
                perfect_fit.append(post_data)
            else:
                # Pure deportation defense - maybe (depends on case)
                maybe_fit.append(post_data)
        elif any(area in matching_areas for area in ["green_card", "citizenship", "work_visa", "asylum", "family", "parole"]):
            # Core immigration services - perfect fit
            perfect_fit.append(post_data)
        elif "general" in matching_areas and not matching_areas == ["general"]:
            # General question with specific area
            can_handle.append(post_data)
        elif "general" in matching_areas:
            # Only general "need lawyer" - can handle
            can_handle.append(post_data)
        else:
            # Unclear or edge case
            maybe_fit.append(post_data)

    conn.close()

    # Print results
    total_questions = len(questions_only)

    print(f"\n{'='*90}")
    print(f"АНАЛИЗ ДЛЯ LIBERUM LAW")
    print(f"{'='*90}\n")

    print(f"Всего вопросов: {total_questions}")
    print(f"✅ Идеально подходят: {len(perfect_fit)} ({len(perfect_fit)*100//total_questions}%)")
    print(f"✓  Могут взять: {len(can_handle)} ({len(can_handle)*100//total_questions}%)")
    print(f"❓ Возможно подходят: {len(maybe_fit)} ({len(maybe_fit)*100//total_questions}%)")

    total_potential = len(perfect_fit) + len(can_handle)
    print(f"\n🎯 ИТОГО ПОТЕНЦИАЛЬНЫХ КЛИЕНТОВ: {total_potential} ({total_potential*100//total_questions}%)")

    print(f"\n{'='*90}")
    print(f"✅ ИДЕАЛЬНО ПОДХОДЯТ ({len(perfect_fit)} вопросов)")
    print(f"{'='*90}\n")

    for i, post in enumerate(perfect_fit[:20], 1):  # Show first 20
        areas_str = ", ".join(post['areas']).upper()
        print(f"{i}. [{areas_str}]")
        print(f"   {post['title']}")
        print(f"   r/{post['group']}")
        print(f"   🔗 {post['url']}\n")

    if len(perfect_fit) > 20:
        print(f"   ... и еще {len(perfect_fit) - 20} вопросов\n")

    print(f"\n{'='*90}")
    print(f"✓  МОГУТ ВЗЯТЬ ({len(can_handle)} вопросов)")
    print(f"{'='*90}\n")

    for i, post in enumerate(can_handle[:10], 1):  # Show first 10
        areas_str = ", ".join(post['areas']).upper() if post['areas'] else "GENERAL"
        print(f"{i}. [{areas_str}]")
        print(f"   {post['title']}")
        print(f"   r/{post['group']}")
        print(f"   🔗 {post['url']}\n")

    if len(can_handle) > 10:
        print(f"   ... и еще {len(can_handle) - 10} вопросов\n")

    # Export to file
    with open("liberum_analysis.txt", "w", encoding="utf-8") as f:
        f.write(f"АНАЛИЗ ДЛЯ LIBERUM LAW\n")
        f.write(f"{'='*90}\n\n")
        f.write(f"Всего вопросов: {total_questions}\n")
        f.write(f"Идеально подходят: {len(perfect_fit)} ({len(perfect_fit)*100//total_questions}%)\n")
        f.write(f"Могут взять: {len(can_handle)} ({len(can_handle)*100//total_questions}%)\n")
        f.write(f"Возможно подходят: {len(maybe_fit)} ({len(maybe_fit)*100//total_questions}%)\n\n")
        f.write(f"ИТОГО ПОТЕНЦИАЛЬНЫХ КЛИЕНТОВ: {total_potential} ({total_potential*100//total_questions}%)\n\n")

        f.write(f"{'='*90}\n")
        f.write(f"ИДЕАЛЬНО ПОДХОДЯТ\n")
        f.write(f"{'='*90}\n\n")

        for i, post in enumerate(perfect_fit, 1):
            areas_str = ", ".join(post['areas']).upper()
            f.write(f"{i}. [{areas_str}]\n")
            f.write(f"   {post['title']}\n")
            f.write(f"   r/{post['group']}\n")
            f.write(f"   {post['url']}\n\n")

    print(f"\n✅ Анализ сохранен в: liberum_analysis.txt\n")

if __name__ == "__main__":
    main()

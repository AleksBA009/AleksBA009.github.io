import os
import requests
from groq import Groq
from github import Github
from datetime import datetime
import json
import re

# --- Конфигурация (из Secrets) ---
GROQ_KEY = os.environ['GROQ_API_KEY']
GH_TOKEN = os.environ['GH_TOKEN']
REPO_NAME = "AleksBA009.github.io"
SITE_URL = "https://aleksba009.github.io"
PINTEREST_TOKEN = os.environ.get('PINTEREST_TOKEN', None)

# Настройка Groq
client = Groq(api_key=GROQ_KEY)

# Партнёрские ссылки (замените на свои)
AFFILIATE_LINKS = {
    "курс бариста онлайн": "https://digistore24.com/example-barista-course",
    "лучшая бюджетная кофемашина": "https://admitad.com/example-coffeemachine",
    "свежие кофейные зерна": "https://travelpayouts.com/example-coffee-beans"
}

def get_next_topic():
    with open("topics.txt", "r", encoding="utf-8") as f:
        lines = f.readlines()
    for i, line in enumerate(lines):
        if "::pending" in line:
            topic = line.split("::")[0].strip()
            lines[i] = line.replace("::pending", "::done")
            with open("topics.txt", "w", encoding="utf-8") as f:
                f.writelines(lines)
            return topic
    raise Exception("Все темы использованы. Добавьте новые в topics.txt.")

def generate_article(topic):
    if "кофемашин" in topic or "бюджет" in topic:
        aff_text = "бюджетной кофемашины"
        aff_url = AFFILIATE_LINKS["лучшая бюджетная кофемашина"]
    elif "курс" in topic or "бариста" in topic or "открыть" in topic:
        aff_text = "курса бариста онлайн"
        aff_url = AFFILIATE_LINKS["курс бариста онлайн"]
    else:
        aff_text = "свежих кофейных зерен"
        aff_url = AFFILIATE_LINKS["свежие кофейные зерна"]

    prompt = f"""Ты — эксперт по кофе и SEO-копирайтер. Напиши статью на тему "{topic}" длиной 1000-1500 слов на русском языке.
Структура: 
- Привлекающий внимание заголовок (H1).
- Введение, где ты описываешь проблему или желание читателя.
- 5-7 подзаголовков H2 с практическими советами, рецептами, сравнениями.
- Вопросы и ответы (FAQ) по теме.
- Заключение с рекомендацией.

В текст естественно вставь 2 раза ссылку: <a href="{aff_url}" target="_blank">{aff_text}</a>. 
Также добавь одну внутреннюю ссылку на ранее опубликованную статью с сайта {SITE_URL} (придумай правдоподобный URL, например /kak-vybrat-zerna-espresso/).
Ответ верни ТОЛЬКО в формате JSON: {{"title": "...", "excerpt": "...", "content_markdown": "...", "tags": "кофе, ..."}}. 
В "content_markdown" используй Markdown с подзаголовками ##, списками, абзацами. Без дополнительных пояснений."""
    
    response = client.chat.completions.create(
        model="llama-3.3-70b-versatile",   # ← актуальная рабочая модель
        messages=[{"role": "user", "content": prompt}],
        temperature=0.7,
        max_tokens=2048,
    )
    raw = response.choices[0].message.content
    json_match = re.search(r'{.*}', raw, re.DOTALL)
    if json_match:
        data = json.loads(json_match.group())
    else:
        raise ValueError(f"Не удалось извлечь JSON из ответа: {raw[:200]}")
    return data

def commit_post(data, img_path=None):
    slug = re.sub(r'[^a-zA-Zа-яА-Я0-9]+', '-', data['title'].lower()).strip('-')
    date_str = datetime.now().strftime("%Y-%m-%d")
    filename = f"_posts/{date_str}-{slug}.md"
    
    frontmatter = f"""---
layout: post
title: "{data['title']}"
date: {datetime.now().strftime("%Y-%m-%d %H:%M:%S +0000")}
excerpt: "{data['excerpt']}"
tags: {data.get('tags', 'кофе')}
---
"""
    content = frontmatter + "\n" + data['content_markdown']
    if img_path:
        content += f"\n\n![{data['title']}]({img_path})"
    
    g = Github(GH_TOKEN)
    repo = g.get_repo(f"AleksBA009/{REPO_NAME}")
    try:
        contents = repo.get_contents(filename)
        repo.update_file(filename, f"Новый пост: {data['title']}", content, contents.sha)
    except:
        repo.create_file(filename, f"Новый пост: {data['title']}", content)
    print(f"Статья {filename} закоммичена.")
    return slug

def notify_indexing(slug):
    url = f"{SITE_URL}/{slug}/"
    print(f"URL для индексации: {url}")

def post_to_pinterest(slug, data, img_path):
    if PINTEREST_TOKEN and img_path:
        board_id = "ваш_board_id"
        headers = {"Authorization": f"Bearer {PINTEREST_TOKEN}"}
        pin_data = {
            "board_id": board_id,
            "title": data['title'],
            "description": data['excerpt'],
            "link": f"{SITE_URL}/{slug}/",
            "media_source": {"source_type": "image_url", "url": f"{SITE_URL}/{img_path}"}
        }
        print("Пин отправлен (закомментировано).")

# --- Основной рабочий процесс ---
if __name__ == "__main__":
    topic = get_next_topic()
    print(f"Генерируем тему: {topic}")
    article = generate_article(topic)
    # Картинку временно отключаем, чтобы избежать ошибок
    # img_path = create_image(topic)
    slug = commit_post(article, None)   # None вместо картинки
    notify_indexing(slug)
    post_to_pinterest(slug, article, None)
    print("Готово!")

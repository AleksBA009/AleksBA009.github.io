import os
import requests
from groq import Groq
from github import Github
from datetime import datetime
import json
import re

# --- Конфигурация ---
GROQ_KEY = os.environ['GROQ_API_KEY']
GH_TOKEN = os.environ['GH_TOKEN']
REPO_NAME = "AleksBA009.github.io"
SITE_URL = "https://aleksba009.github.io"
PINTEREST_TOKEN = os.environ.get('PINTEREST_TOKEN', None)

client = Groq(api_key=GROQ_KEY)

AFFILIATE_LINKS = {
    "курс бариста онлайн": "https://getsale.ru/ваша_ссылка",
    "лучшая бюджетная кофемашина": "https://ad.admitad.com/g/ваша_ссылка",
    "свежие кофейные зерна": "https://ad.admitad.com/g/ваша_ссылка"
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

    prompt = f"""Ты — профессиональный кофейный эксперт и автор глубоких статей для издания вроде «Вокруг кофе» или «Кофейный журнал». 
Тема статьи: «{topic}».

Напиши развёрнутую, полезную статью на русском языке длиной не менее 1200 слов. 
Твой текст должен читаться как материал настоящего знатока, а не поверхностная компиляция из интернета.

Стиль:
- Умный, но не заумный; доверительный, как разговор с опытным бариста.
- Избегай общих фраз («кофе — это прекрасный напиток»). Сразу к делу.
- Используй конкретные цифры, факты, сравнения (например, «давление в 9 бар против 15 бар», «зёрна 100% арабика из Эфиопии Иргачеффе»).
- Расскажи о типичных ошибках, которые совершают новички, и как их избежать.
- Включи небольшой исторический или технологический экскурс, если это уместно.

Структура статьи (обязательно используй заголовки H2):
1. Введение, которое сразу захватывает внимание — начни с проблемы или любопытного факта.
2. Основная часть из 5-7 подзаголовков, раскрывающих тему с разных сторон.
3. Блок FAQ: 3-4 вопроса и развёрнутых ответа по теме.
4. Заключение с главным выводом и рекомендацией.

В тексте дважды естественно вставь партнёрскую ссылку с анкором «{aff_text}»: <a href="{aff_url}" target="_blank">{aff_text}</a>.
Также добавь одну внутреннюю ссылку на другую статью сайта {SITE_URL} (придумай логичный URL, например /kak-vybrat-zerna-espresso/).

ВАЖНО: ответ пришли ТОЛЬКО в формате JSON, без дополнительного текста.
JSON-объект должен содержать поля:
{{"title": "...", "excerpt": "...", "content_markdown": "...", "tags": "кофе, ..."}}
В поле "content_markdown" должен быть полностью Markdown статьи (с подзаголовками ##, списками и т.д.).
Экранируй все двойные кавычки внутри значений как \\\", а переводы строк как \\n."""

    response = client.chat.completions.create(
        model="mixtral-8x7b-32768",   # ← более креативная модель
        messages=[{"role": "user", "content": prompt}],
        temperature=0.85,              # больше вариативности
        max_tokens=3072,               # даём простор для мысли
    )
    raw = response.choices[0].message.content

    json_match = re.search(r'{.*}', raw, re.DOTALL)
    if json_match:
        raw_json = json_match.group()
    else:
        raw_json = raw

    def clean_json(s):
        return re.sub(r'[\x00-\x08\x0b\x0c\x0e-\x1f]', '', s)

    try:
        data = json.loads(raw_json)
    except json.JSONDecodeError:
        try:
            cleaned = clean_json(raw_json)
            data = json.loads(cleaned)
        except json.JSONDecodeError as e:
            raise ValueError(f"Ошибка парсинга JSON: {e}\nСырой ответ:\n{raw[:500]}")
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

if __name__ == "__main__":
    topic = get_next_topic()
    print(f"Генерируем тему: {topic}")
    article = generate_article(topic)
    slug = commit_post(article, None)
    notify_indexing(slug)
    print("Готово!")
    
        
import os
import requests
from groq import Groq
from github import Github
from datetime import datetime
import json
import re

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

    prompt = f"""Ты — редактор кофейного журнала с 20-летним стажем. Напиши экспертную статью на тему «{topic}». 
Статья должна быть на русском языке, МИНИМУМ 1200 слов (я проверю, меньше — не принимаю).

СТРОГИЕ ПРАВИЛА:
1. Никаких общих фраз вроде «кофе — это искусство», «выбор сложен», «надеемся, что помогли». Сразу к делу.
2. Каждый подзаголовок H2 должен содержать от 100 до 200 слов с конкретной, измеримой информацией.
3. ОБЯЗАТЕЛЬНО используй:
   - Реальные названия моделей, брендов, сортов (DeLonghi Magnifica S, Philips 2200, Ethiopia Yirgacheffe).
   - Цифры: давление в барах, мощность в Вт, объём в мл, цена в рублях, время в секундах.
   - Сравнения в формате «модель А vs модель Б» с таблицей или списком.
   - Типичные ошибки новичков и чёткие инструкции, как их избежать.
   - Хотя бы один исторический или технологический факт (например, «первый патент на эспрессо-машину был выдан в 1884 году Анджело Мориондо»).
4. FAQ-блок должен содержать 3-4 вопроса с развёрнутыми ответами (не менее 3 предложений каждый).

СТРУКТУРА:
- Введение: начни с парадокса, малоизвестного факта или сильного утверждения, которое зацепит читателя (3-5 предложений).
- 5-7 подзаголовков H2, раскрывающих тему.
- Блок «Часто задаваемые вопросы» (H2).
- Заключение с главным выводом и практической рекомендацией.

Дважды в тексте вставь партнёрскую ссылку: <a href="{aff_url}" target="_blank">{aff_text}</a> — органично, там, где это действительно нужно.
Добавь ОДНУ внутреннюю ссылку на другую статью сайта: [{SITE_URL}/...]({SITE_URL}/...) — с логичным URL, например /kak-vybrat-zerna-espresso.

ФОРМАТ ОТВЕТА (строго JSON):
{{"title": "...", "excerpt": "...", "content_markdown": "...", "tags": "кофе, ..."}}

В "content_markdown" — полный Markdown статьи. Заголовки H2 обозначай ## .
Статья должна быть НЕ МЕНЕЕ 1200 СЛОВ."""

    response = client.chat.completions.create(
        model="llama-3.3-70b-versatile",
        messages=[{"role": "user", "content": prompt}],
        temperature=0.85,
        max_tokens=4096,  # увеличен для длинных статей
    )
    raw = response.choices[0].message.content
    return parse_article_response(raw)

def parse_article_response(raw):
    try:
        data = json.loads(raw)
        if all(k in data for k in ("title", "excerpt", "content_markdown")):
            return data
    except:
        pass
    json_match = re.search(r'```json\s*(.*?)\s*```', raw, re.DOTALL)
    if json_match:
        try:
            data = json.loads(json_match.group(1))
            if all(k in data for k in ("title", "excerpt", "content_markdown")):
                return data
        except:
            pass
    title = extract_field(raw, "title")
    excerpt = extract_field(raw, "excerpt")
    content = extract_field(raw, "content_markdown")
    tags = extract_field(raw, "tags")
    if title and excerpt and content:
        return {"title": title, "excerpt": excerpt, "content_markdown": content, "tags": tags or "кофе"}
    else:
        raise ValueError(f"Не удалось извлечь статью:\n{raw[:500]}")

def extract_field(text, field_name):
    pattern = r'"' + re.escape(field_name) + r'"\s*:\s*"(.*?)"\s*[,}]'
    match = re.search(pattern, text, re.DOTALL)
    if match:
        value = match.group(1)
        value = value.replace('\\"', '"').replace('\\n', '\n')
        return value.strip()
    return None

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
    print(f"URL для индексации: {SITE_URL}/{slug}/")

def post_to_pinterest(slug, data, img_path):
    if PINTEREST_TOKEN and img_path:
        print("Пин отправлен (закомментировано).")

if __name__ == "__main__":
    topic = get_next_topic()
    print(f"Генерируем тему: {topic}")
    article = generate_article(topic)
    slug = commit_post(article, None)
    notify_indexing(slug)
    post_to_pinterest(slug, article, None)
    print("Готово!")
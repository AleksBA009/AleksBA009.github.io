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

    prompt = f"""Ты — редактор кофейного журнала с 20-летним стажем. Напиши экспертную статью на русском языке. Тема: «{topic}». МИНИМУМ 1200 слов.

ЖЁСТКИЕ ПРАВИЛА:
1. Никаких штампов: «кофе — это искусство», «выбор сложен», «надеемся, что помогли». Сразу к делу.
2. Каждый подзаголовок H2 — от 100 до 250 слов с КОНКРЕТНОЙ информацией.
3. ОБЯЗАТЕЛЬНО используй:
   - Научные данные: упомяни хотя бы одно исследование (университет, год, суть) или конкретные цифры (например, «3-6 мг кофеина на кг веса», «за 30-60 мин до тренировки»).
   - Реальные бренды и модели: для турки — медная турка «Станица», TimA, Гурман. Для кофемашин — DeLonghi, Philips, Krups.
   - Цифры: объём в мл, цена в рублях, время в минутах, температура в °C.
   - Сравнительную таблицу или маркированный список сравнения.
   - Типичные ошибки (минимум 3) и способы их избежать.
   - Исторический факт или технологическую справку.
4. ТЕМАТИЧЕСКАЯ ТОЧНОСТЬ: если тема про турку — пиши про турку. Не путай с кофемашиной. Для турки: помол «в пыль», пенка, прогрев в песке.
5. FAQ-блок: 3-4 вопроса с развёрнутыми ответами (каждый ответ — минимум 4 предложения).
6. Заключение: один ГЛАВНЫЙ ВЫВОД жирным шрифтом и практическая рекомендация.
7. ЗАПРЕЩЕНЫ англицизмы в русском тексте (вместо «neutralize» — «нейтрализуют», вместо «consume» — «потреблять»).
8. Каждый раздел должен быть полным. НЕ ДОПУСКАЮТСЯ разделы из одного-двух предложений.

СТРУКТУРА:
- Введение: сильное утверждение, парадокс или мощный факт (3-5 предложений).
- 5-7 подзаголовков H2.
- Блок FAQ (H2).
- Заключение.

Дважды органично вставь партнёрскую ссылку: <a href="{aff_url}" target="_blank">{aff_text}</a>.
Добавь ОДНУ внутреннюю ссылку на другую статью сайта [{SITE_URL}/...]({SITE_URL}/...).

ФОРМАТ ОТВЕТА (строго JSON):
{{"title": "...", "excerpt": "...", "content_markdown": "...", "tags": "кофе, ..."}}

В "content_markdown" — полный Markdown статьи. Заголовки H2 обозначай ## .
СТАТЬЯ ДОЛЖНА БЫТЬ НЕ МЕНЕЕ 1200 СЛОВ. Я проверю объём."""

    response = client.chat.completions.create(
        model="gemma2-9b-it",  # ← более объёмная и разговорчивая
        messages=[{"role": "user", "content": prompt}],
        temperature=0.9,
        max_tokens=4096,
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
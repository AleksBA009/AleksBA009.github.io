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

# Партнёрские ссылки (замените на свои)
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

Ответ пришли в формате JSON с полями:
- "title": заголовок статьи,
- "excerpt": краткое описание (1-2 предложения),
- "content_markdown": полный текст статьи в Markdown,
- "tags": строка с тегами через запятую.

Важно: JSON должен быть валидным, без разрывов строк внутри строковых значений. Используй \\n для переносов строк."""

    response = client.chat.completions.create(
        model="llama-3.3-70b-versatile",
        messages=[{"role": "user", "content": prompt}],
        temperature=0.85,
        max_tokens=3072,
    )
    raw = response.choices[0].message.content
    return parse_article_response(raw)

def parse_article_response(raw):
    """Извлекает поля статьи из текстового ответа, даже если JSON сломан."""
    # Попытка 1: парсим как обычный JSON
    try:
        data = json.loads(raw)
        if all(k in data for k in ("title", "excerpt", "content_markdown")):
            return data
    except:
        pass

    # Попытка 2: ищем JSON-блок внутри текста (может быть в ```json ... ```)
    json_match = re.search(r'```json\s*(.*?)\s*```', raw, re.DOTALL)
    if json_match:
        try:
            data = json.loads(json_match.group(1))
            if all(k in data for k in ("title", "excerpt", "content_markdown")):
                return data
        except:
            pass

    # Попытка 3: извлекаем поля регулярками, даже если есть переносы строк в значениях
    title = extract_field(raw, "title")
    excerpt = extract_field(raw, "excerpt")
    content = extract_field(raw, "content_markdown")
    tags = extract_field(raw, "tags")

    if title and excerpt and content:
        return {
            "title": title,
            "excerpt": excerpt,
            "content_markdown": content,
            "tags": tags or "кофе"
        }
    else:
        raise ValueError(f"Не удалось извлечь статью из ответа:\n{raw[:500]}")

def extract_field(text, field_name):
    """Ищет значение поля вида "field_name": "значение" с учётом многострочности."""
    # Сначала ищем "field_name": "..." где значение может содержать экранированные кавычки
    pattern = rf'"{field_name}"\s*:\s*"(.*?)"\s*[,}}]'
    match = re.search(pattern, text, re.DOTALL)
    if match:
        value = match.group(1)
        # Убираем экранирование кавычек и переносов строк (если они есть)
        value = value.replace('\\"', '"').replace('\\n', '\n')
        return value.strip()
    # Если не нашли, возможно значение в одинарных кавычках
    pattern2 = rf'"{field_name}"\s*:\s*'(.*?)'\s*[,}}]'
    match2 = re.search(pattern2, text, re.DOTALL)
    if match2:
        return match2.group(1).strip()
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

if __name__ == "__main__":
    topic = get_next_topic()
    print(f"Генерируем тему: {topic}")
    article = generate_article(topic)
    slug = commit_post(article, None)
    notify_indexing(slug)
    post_to_pinterest(slug, article, None)
    print("Готово!")




    
        
import os, requests, json, re
from groq import Groq
from github import Github
from datetime import datetime

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
    aff_text = "свежих кофейных зерен"
    aff_url = AFFILIATE_LINKS["свежие кофейные зерна"]
    if "кофемашин" in topic or "бюджет" in topic:
        aff_text = "бюджетной кофемашины"
        aff_url = AFFILIATE_LINKS["лучшая бюджетная кофемашина"]
    elif "курс" in topic or "бариста" in topic or "открыть" in topic:
        aff_text = "курса бариста онлайн"
        aff_url = AFFILIATE_LINKS["курс бариста онлайн"]

    # Шаг 1: запрос плана
    plan_prompt = f"""Ты — эксперт по кофе. Составь подробный план статьи на тему: «{topic}».
План должен содержать:
- Мощное введение (факт, парадокс, цифра).
- 5-7 подзаголовков H2, каждый с тезисным описанием (1 предложение, что будет раскрыто).
- Блок FAQ: 4 вопроса (без ответов).
- Заключение с главным выводом.
Ответь кратко."""

    plan_response = client.chat.completions.create(
        model="llama-3.3-70b-versatile",
        messages=[{"role": "user", "content": plan_prompt}],
        temperature=0.7,
        max_tokens=500,
    )
    plan = plan_response.choices[0].message.content
    print("План составлен.")

    # Шаг 2: написание полного текста по плану
    full_prompt = f"""Ты — главный редактор кофейного журнала. Используя приложенный план, напиши готовую статью на тему «{topic}» (русский, 1200+ слов).

План:
{plan}

Требования:
- Избегай штампов («кофе — это искусство»).
- Приведи реальные модели (DeLonghi, Philips, Krups, турка «Станица»), цифры, факты, сравнительную таблицу.
- FAQ с развёрнутыми ответами (не менее 3 предложений каждый).
- Введи дважды партнёрскую ссылку: <a href="{aff_url}">{aff_text}</a>.
- Добавь одну внутреннюю ссылку: [{SITE_URL}/...]({SITE_URL}/...).
- Заключение начни со слов «Главный вывод:».
- Ответ строго в JSON: {{"title":"...","excerpt":"...","content_markdown":"...","tags":"кофе, ..."}}.
- В content_markdown — Markdown-разметка. H2 — через ##."""

    full_response = client.chat.completions.create(
        model="llama-3.3-70b-versatile",
        messages=[{"role": "user", "content": full_prompt}],
        temperature=0.9,
        max_tokens=4096,
    )
    raw = full_response.choices[0].message.content
    return parse_response(raw)

def parse_response(raw):
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
    title = re.search(r'"title"\s*:\s*"(.*?)"', raw, re.DOTALL)
    excerpt = re.search(r'"excerpt"\s*:\s*"(.*?)"', raw, re.DOTALL)
    content = re.search(r'"content_markdown"\s*:\s*"(.*?)"', raw, re.DOTALL)
    tags = re.search(r'"tags"\s*:\s*"(.*?)"', raw, re.DOTALL)
    if title and excerpt and content:
        return {
            "title": title.group(1).replace('\\"','"').replace('\\n','\n'),
            "excerpt": excerpt.group(1).replace('\\"','"').replace('\\n','\n'),
            "content_markdown": content.group(1).replace('\\"','"').replace('\\n','\n'),
            "tags": tags.group(1) if tags else "кофе"
        }
    raise ValueError(f"Не удалось извлечь статью: {raw[:300]}")

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

if __name__ == "__main__":
    topic = get_next_topic()
    print(f"Генерируем тему: {topic}")
    article = generate_article(topic)
    slug = commit_post(article)
    notify_indexing(slug)
    print("Готово!")
---
layout: default
---

# Добро пожаловать в мир кофе!
Здесь вы найдете проверенные рецепты, подборки лучших кофемашин и секреты бариста.
{% for post in site.posts %}
- [{{ post.title }}]({{ post.url }}) — {{ post.date | date: "%d.%m.%Y" }}
{% endfor %}

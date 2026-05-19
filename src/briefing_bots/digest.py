from __future__ import annotations

from openai import AsyncOpenAI

from briefing_bots.collector import collect_articles
from briefing_bots.storage import latest_unnotified_articles_by_keyword, upsert_articles


async def build_channel_digest(
    database_path, channel: dict, max_items: int, max_chars: int, model: str
) -> tuple[str, list[str]]:
    keywords = channel.get("keywords", [])
    sources = channel.get("sources", [])
    name = channel.get("name", "")

    if not keywords:
        return f"[{name}] 収集キーワードが未設定", []

    collected = await collect_articles(sources, model, keywords, max_items)
    await upsert_articles(database_path, collected)

    grouped_articles = {
        keyword: await latest_unnotified_articles_by_keyword(database_path, keyword, max_items)
        for keyword in keywords
    }

    client = AsyncOpenAI()
    source_lines = _format_grouped_articles(grouped_articles)
    if not source_lines:
        return f"[{name}] 設定キーワードに一致する新着情報なし", []

    used_urls = [a.url for articles in grouped_articles.values() for a in articles]

    response = await client.responses.create(
        model=model,
        input=(
            "Discordに投稿する朝の情報ダイジェストを日本語で作成。"
            "キーワードごとに大きな見出しで分ける。各項目にURLを1つ含める。"
            f"全体を{max_chars}文字以内に収める。\n\n"
            f"見出し: {name}\n\n材料:\n{source_lines}"
        ),
        max_output_tokens=900,
    )
    return response.output_text.strip(), used_urls


def _format_grouped_articles(grouped_articles) -> str:
    sections: list[str] = []
    for keyword, articles in grouped_articles.items():
        if not articles:
            continue
        article_lines = "\n".join(
            f"- [{article.source}] {article.title}\n  {article.summary}\n  {article.url}"
            for article in articles
        )
        sections.append(f"## {keyword}\n{article_lines}")
    return "\n\n".join(sections)

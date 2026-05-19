from __future__ import annotations

from email.utils import parsedate_to_datetime

import feedparser
import httpx
from bs4 import BeautifulSoup
from openai import AsyncOpenAI

from briefing_bots.storage import Article


async def collect_articles(sources: list[dict], model: str, keywords: list[str], max_items: int = 12) -> list[Article]:
    client = AsyncOpenAI()
    articles: list[Article] = []
    if not keywords:
        return articles

    async with httpx.AsyncClient(timeout=20.0, follow_redirects=True) as http:
        for source in sources:
            if source.get("kind") != "rss":
                continue
            articles.extend(
                await _collect_rss_source(http, client, source, model, keywords, max_items)
            )

    return articles[:max_items]


async def _collect_rss_source(
    http: httpx.AsyncClient,
    openai: AsyncOpenAI,
    source: dict,
    model: str,
    keywords: list[str],
    max_items: int,
) -> list[Article]:
    response = await http.get(source["url"])
    response.raise_for_status()
    feed = feedparser.parse(response.text)
    articles: list[Article] = []

    for entry in feed.entries[:max_items]:
        title = _text(entry.get("title", "Untitled"))
        url = entry.get("link")
        if not url:
            continue
        content = await _entry_content(http, entry, url)
        matched_keywords = _matched_keywords(keywords, title, content)
        if not matched_keywords:
            continue
        summary = await summarize_article(openai, model, title, content)
        articles.append(
            Article(
                source=source.get("name", "Unknown"),
                title=title,
                url=url,
                published_at=_published_at(entry),
                summary=summary,
                content=content,
                keywords=tuple(matched_keywords),
            )
        )
    return articles


async def _entry_content(http: httpx.AsyncClient, entry: dict, url: str) -> str:
    rss_text = _text(entry.get("summary", "") or entry.get("description", ""))
    try:
        page = await http.get(url)
        page.raise_for_status()
    except httpx.HTTPError:
        return rss_text[:6000]

    soup = BeautifulSoup(page.text, "html.parser")
    for node in soup(["script", "style", "nav", "footer", "header"]):
        node.decompose()
    page_text = " ".join(soup.get_text(" ").split())
    combined = f"{rss_text}\n\n{page_text}".strip()
    return combined[:12000]


async def summarize_article(openai: AsyncOpenAI, model: str, title: str, content: str) -> str:
    prompt = (
        "次の記事を日本語で2文以内に要約。事実だけを書き、推測は避ける。\n\n"
        f"タイトル: {title}\n本文:\n{content[:8000]}"
    )
    response = await openai.responses.create(
        model=model,
        input=prompt,
        max_output_tokens=220,
    )
    return response.output_text.strip()


def _published_at(entry: dict) -> str | None:
    raw = entry.get("published") or entry.get("updated")
    if not raw:
        return None
    try:
        return parsedate_to_datetime(raw).isoformat()
    except (TypeError, ValueError):
        return None


def _text(value: str) -> str:
    return BeautifulSoup(value or "", "html.parser").get_text(" ", strip=True)


def _matched_keywords(keywords: list[str], title: str, content: str) -> list[str]:
    haystack = f"{title}\n{content}".casefold()
    return [keyword for keyword in keywords if keyword.casefold() in haystack]

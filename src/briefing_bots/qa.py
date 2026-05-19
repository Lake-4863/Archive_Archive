from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path

from openai import AsyncOpenAI

from briefing_bots.storage import latest_articles, search_articles


async def answer_question(database_path: Path, question: str, model: str) -> str:
    fts_articles = await search_articles(database_path, question, limit=10)
    recent_articles = await latest_articles(database_path, limit=6)

    seen_urls: set[str] = set()
    candidates = []
    for article in fts_articles + recent_articles:
        if article.url not in seen_urls:
            seen_urls.add(article.url)
            candidates.append(article)

    if not candidates:
        return "関連する収集済み情報が見つかりませんでした"

    now = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")
    context = "\n\n".join(
        f"[{i + 1}] {a.source} | {a.published_at or '日付不明'}\n"
        f"タイトル: {a.title}\n"
        f"要約: {a.summary}\n"
        f"URL: {a.url}"
        for i, a in enumerate(candidates)
    )

    response = await AsyncOpenAI().responses.create(
        model=model,
        input=(
            f"現在時刻: {now}\n\n"
            "あなたは情報キュレーターです。以下の収集済み記事の中から、"
            "ユーザーの質問に関連する情報を注目度と新鮮度を考慮して選び、日本語で回答してください。\n\n"
            "ルール:\n"
            "- 質問に最も関連性が高く、かつ新しい情報を優先して紹介する\n"
            "- 記事の日付を参考に鮮度を判断する\n"
            "- 各情報には必ず記事番号とURLを添える\n"
            "- 収集済み記事に根拠がない情報は述べない\n"
            "- 関連情報が見つからない場合はその旨を伝える\n\n"
            f"質問: {question}\n\n"
            f"収集済み記事:\n{context}"
        ),
        max_output_tokens=1000,
    )
    return response.output_text.strip()

from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path

from openai import AsyncOpenAI

from briefing_bots.storage import latest_articles, search_articles

History = list[dict[str, str]]


async def answer_question(
    database_path: Path,
    question: str,
    model: str,
    history: History | None = None,
) -> tuple[str, History]:
    history = list(history or [])

    fts_articles = await search_articles(database_path, question, limit=10)
    recent_articles = await latest_articles(database_path, limit=6)

    seen_urls: set[str] = set()
    candidates = []
    for article in fts_articles + recent_articles:
        if article.url not in seen_urls:
            seen_urls.add(article.url)
            candidates.append(article)

    now = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")

    history_text = ""
    if history:
        lines = []
        for msg in history:
            role = "ユーザー" if msg["role"] == "user" else "アシスタント"
            lines.append(f"{role}: {msg['content']}")
        history_text = "【過去の会話】\n" + "\n".join(lines) + "\n\n"

    if candidates:
        context_text = "収集済み記事:\n" + "\n\n".join(
            f"[{i + 1}] {a.source} | {a.published_at or '日付不明'}\n"
            f"タイトル: {a.title}\n"
            f"要約: {a.summary}\n"
            f"URL: {a.url}"
            for i, a in enumerate(candidates)
        )
    else:
        context_text = "収集済み記事: なし"

    response = await AsyncOpenAI().responses.create(
        model=model,
        input=(
            f"現在時刻: {now}\n\n"
            "あなたはゲーム情報に詳しいアシスタントです。"
            "収集済み記事があればそれを優先して回答し、記事にない情報は自分の知識で補完して答えてください。"
            "過去の会話があれば文脈を踏まえて自然に回答してください。\n\n"
            "ルール:\n"
            "- 収集済み記事の情報は新鮮度と関連度を考慮して優先する\n"
            "- 記事を参照した場合は記事番号とURLを添える\n"
            "- 記事にない情報は自分の知識で補完してよい（その場合は「記事にはありませんが」と一言添える）\n"
            "- 会話の流れを踏まえて自然に答える\n\n"
            f"{history_text}"
            f"質問: {question}\n\n"
            f"{context_text}"
        ),
        max_output_tokens=1000,
    )
    answer = response.output_text.strip()

    history.append({"role": "user", "content": question})
    history.append({"role": "assistant", "content": answer})
    if len(history) > 20:
        history = history[-20:]

    return answer, history

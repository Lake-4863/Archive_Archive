from __future__ import annotations

import argparse
import asyncio

import httpx

from briefing_bots.digest import build_channel_digest
from briefing_bots.settings import load_config, load_digest_settings
from briefing_bots.storage import init_db, mark_articles_notified, sync_keywords


DISCORD_API_BASE = "https://discord.com/api/v10"
DISCORD_MESSAGE_LIMIT = 2000
SAFE_MESSAGE_LIMIT = 1900


async def main() -> None:
    parser = argparse.ArgumentParser(description="Post one digest run to Discord.")
    parser.add_argument("--dry-run", action="store_true", help="Print digests without posting.")
    args = parser.parse_args()

    settings = load_digest_settings()
    config = load_config(settings.config_path)
    await init_db(settings.database_path)

    channels = config.get("channels", [])
    max_items = int(config.get("digest", {}).get("max_items", 12))
    max_chars = int(config.get("digest", {}).get("max_message_chars", 1800))

    all_keywords = [kw for channel in channels for kw in channel.get("keywords", [])]
    await sync_keywords(settings.database_path, all_keywords)

    async with httpx.AsyncClient(timeout=20.0) as http:
        for channel_config in channels:
            channel_id = channel_config.get("channel_id")
            if not channel_id:
                continue

            digest, used_urls = await build_channel_digest(
                settings.database_path,
                channel_config,
                max_items,
                max_chars,
                settings.openai_model,
            )
            if args.dry_run:
                print(f"\n=== {channel_config.get('name', channel_id)} ===")
                print(digest)
                continue

            await post_discord_message(http, settings.digest_discord_token, int(channel_id), digest)
            await mark_articles_notified(settings.database_path, used_urls)


async def post_discord_message(
    http: httpx.AsyncClient,
    token: str,
    channel_id: int,
    content: str,
) -> None:
    for chunk in split_discord_message(content):
        response = await http.post(
            f"{DISCORD_API_BASE}/channels/{channel_id}/messages",
            headers={"Authorization": f"Bot {token}"},
            json={"content": chunk, "allowed_mentions": {"parse": []}},
        )
        response.raise_for_status()


def split_discord_message(content: str) -> list[str]:
    if len(content) <= DISCORD_MESSAGE_LIMIT:
        return [content]

    chunks: list[str] = []
    remaining = content
    while remaining:
        candidate = remaining[:SAFE_MESSAGE_LIMIT]
        split_at = max(candidate.rfind("\n\n"), candidate.rfind("\n"), candidate.rfind(" "))
        if split_at < SAFE_MESSAGE_LIMIT // 2:
            split_at = SAFE_MESSAGE_LIMIT
        chunks.append(remaining[:split_at].strip())
        remaining = remaining[split_at:].strip()
    return [chunk for chunk in chunks if chunk]


if __name__ == "__main__":
    asyncio.run(main())

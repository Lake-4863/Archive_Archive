from __future__ import annotations

import asyncio

import discord
from apscheduler.schedulers.asyncio import AsyncIOScheduler

from briefing_bots.digest import build_channel_digest
from briefing_bots.settings import load_config, load_digest_settings
from briefing_bots.storage import init_db, mark_articles_notified, sync_keywords


async def main() -> None:
    settings = load_digest_settings()
    config = load_config(settings.config_path)
    await init_db(settings.database_path)

    channels = config.get("channels", [])
    max_items = int(config.get("digest", {}).get("max_items", 12))
    max_chars = int(config.get("digest", {}).get("max_message_chars", 1800))

    all_keywords = [kw for ch in channels for kw in ch.get("keywords", [])]
    await sync_keywords(settings.database_path, all_keywords)

    intents = discord.Intents.default()
    client = discord.Client(intents=intents)
    scheduler = AsyncIOScheduler(timezone=settings.timezone)

    async def post_all_digests() -> None:
        for channel_config in channels:
            channel_id = channel_config.get("channel_id")
            if not channel_id:
                continue
            try:
                channel = client.get_channel(channel_id) or await client.fetch_channel(channel_id)
                digest, used_urls = await build_channel_digest(
                    settings.database_path, channel_config, max_items, max_chars, settings.openai_model
                )
                await channel.send(digest)
                await mark_articles_notified(settings.database_path, used_urls)
            except Exception as e:
                print(f"Error posting to channel {channel_id}: {e}")

    @client.event
    async def on_ready() -> None:
        schedule = config.get("schedule", {})
        scheduler.add_job(
            post_all_digests,
            "cron",
            hour=int(schedule.get("hour", 8)),
            minute=int(schedule.get("minute", 0)),
            id="daily_digest",
            replace_existing=True,
        )
        if not scheduler.running:
            scheduler.start()
        try:
            synced = await client.http.application_info()
            print(f"Digest bot logged in as {client.user}")
        except Exception:
            print(f"Digest bot logged in as {client.user}")

    await client.start(settings.digest_discord_token)


if __name__ == "__main__":
    asyncio.run(main())

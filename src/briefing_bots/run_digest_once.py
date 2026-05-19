from __future__ import annotations

import asyncio

from briefing_bots.digest import build_channel_digest
from briefing_bots.settings import load_config, load_digest_settings
from briefing_bots.storage import init_db, sync_keywords


async def main() -> None:
    settings = load_digest_settings()
    config = load_config(settings.config_path)
    await init_db(settings.database_path)

    channels = config.get("channels", [])
    max_items = int(config.get("digest", {}).get("max_items", 12))
    max_chars = int(config.get("digest", {}).get("max_message_chars", 1800))

    all_keywords = [kw for ch in channels for kw in ch.get("keywords", [])]
    await sync_keywords(settings.database_path, all_keywords)

    for channel_config in channels:
        name = channel_config.get("name", "")
        print(f"\n=== {name} ===")
        digest = await build_channel_digest(
            settings.database_path, channel_config, max_items, max_chars, settings.openai_model
        )
        print(digest)


if __name__ == "__main__":
    asyncio.run(main())

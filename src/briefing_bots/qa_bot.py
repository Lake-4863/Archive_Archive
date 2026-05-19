from __future__ import annotations

import asyncio

import discord
from discord import app_commands

from briefing_bots.collector import collect_articles
from briefing_bots.qa import History, answer_question
from briefing_bots.settings import load_config, load_qa_settings
from briefing_bots.storage import init_db, upsert_articles

_histories: dict[int, History] = {}


async def main() -> None:
    print("Starting QA bot...")
    settings = load_qa_settings()
    await init_db(settings.database_path)
    print(f"DB initialized, guild_id={settings.discord_guild_id}")

    intents = discord.Intents.default()
    client = discord.Client(intents=intents)
    tree = app_commands.CommandTree(client)

    @tree.command(name="ask", description="収集済み情報から質問に回答（会話の流れを記憶します）")
    @app_commands.describe(question="質問")
    async def ask(interaction: discord.Interaction, question: str) -> None:
        await interaction.response.defer(thinking=True)
        user_id = interaction.user.id
        answer, updated = await answer_question(
            settings.database_path,
            question,
            settings.openai_model,
            history=_histories.get(user_id),
        )
        _histories[user_id] = updated
        await interaction.followup.send(answer[:1900])

    @tree.command(name="collect", description="記事を収集してDBに保存する")
    async def collect(interaction: discord.Interaction) -> None:
        await interaction.response.defer(thinking=True)
        config = load_config(settings.config_path)
        channels = config.get("channels", [])
        max_items = int(config.get("digest", {}).get("max_items", 12))
        total = 0
        for channel_config in channels:
            keywords = channel_config.get("keywords", [])
            sources = channel_config.get("sources", [])
            collected = await collect_articles(sources, settings.openai_model, keywords, max_items)
            total += await upsert_articles(settings.database_path, collected)
        await interaction.followup.send(f"収集完了！新規記事 {total} 件をDBに保存しました。")

    @tree.command(name="reset", description="会話履歴をリセットする")
    async def reset(interaction: discord.Interaction) -> None:
        _histories.pop(interaction.user.id, None)
        await interaction.response.send_message("会話履歴をリセットしました。", ephemeral=True)

    @client.event
    async def on_ready() -> None:
        try:
            synced = await tree.sync()
            print(f"QA bot logged in as {client.user}")
            print(f"Synced {len(synced)} command(s) globally: {[c.name for c in synced]}")
        except Exception as e:
            print(f"Sync failed: {type(e).__name__}: {e}")

    await client.start(settings.qa_discord_token)


if __name__ == "__main__":
    asyncio.run(main())

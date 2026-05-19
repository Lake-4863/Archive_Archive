from __future__ import annotations

import asyncio

import discord
from discord import app_commands

from briefing_bots.qa import History, answer_question
from briefing_bots.settings import load_qa_settings
from briefing_bots.storage import init_db

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

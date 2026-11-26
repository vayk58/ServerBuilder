"""Точка входа ServerBuilder."""
from __future__ import annotations

import asyncio
import logging

import discord
from discord.ext import commands

from config import DATABASE_PATH, GUILD_ID, LOG_LEVEL, TOKEN
from database.db import Database
from utils.errors import on_app_command_error, on_command_error

logging.basicConfig(
    level=getattr(logging, LOG_LEVEL.upper(), logging.INFO),
    format="%(asctime)s | %(levelname)-8s | %(name)s | %(message)s",
)
log = logging.getLogger("serverbuilder")

COGS = [
    "cogs.wizard",
    "cogs.moderation",
    "cogs.welcome",
    "cogs.utility",
    "cogs.setup",
    "cogs.comfort",
    "cogs.tickets",
    "cogs.fun",
    "cogs.reaction_roles",
    "cogs.stats",
    "cogs.giveaways",
    "cogs.health",
    "cogs.antiraid",
    "cogs.community",
]


class ServerBuilderBot(commands.Bot):
    def __init__(self) -> None:
        intents = discord.Intents.default()
        intents.members = True
        intents.message_content = True
        intents.voice_states = True
        intents.presences = True
        super().__init__(command_prefix="!", intents=intents)
        self.db = Database(str(DATABASE_PATH))
        self.tree.on_error = on_app_command_error

    async def setup_hook(self) -> None:
        await self.db.connect()
        for cog in COGS:
            try:
                await self.load_extension(cog)
                log.info("Ког загружен: %s", cog)
            except Exception:
                log.exception("Не удалось загрузить ког %s", cog)

        if GUILD_ID:
            guild = discord.Object(id=GUILD_ID)
            self.tree.copy_global_to(guild=guild)
            await self.tree.sync(guild=guild)
            log.info("Команды синхронизированы для гильдии %s", GUILD_ID)
        else:
            await self.tree.sync()
            log.info("Глобальные команды синхронизированы")

    async def on_ready(self) -> None:
        log.info("Бот запущен как %s (ID: %s)", self.user, self.user.id if self.user else "?")

    async def on_command_error(self, ctx: commands.Context, error: commands.CommandError) -> None:
        await on_command_error(ctx, error)

    async def close(self) -> None:
        await self.db.close()
        await super().close()


async def main() -> None:
    if not TOKEN:
        raise RuntimeError("DISCORD_TOKEN не задан в .env")
    bot = ServerBuilderBot()
    async with bot:
        await bot.start(TOKEN)


if __name__ == "__main__":
    asyncio.run(main())

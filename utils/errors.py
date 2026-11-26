"""Глобальный обработчик ошибок."""
from __future__ import annotations

import logging

import discord
from discord import app_commands
from discord.ext import commands

from utils.embeds import error_embed

log = logging.getLogger(__name__)


async def on_app_command_error(interaction: discord.Interaction, error: app_commands.AppCommandError) -> None:
    if isinstance(error, app_commands.CommandOnCooldown):
        msg = f"⏳ Через **{error.retry_after:.1f}** сек."
    elif isinstance(error, app_commands.MissingPermissions):
        msg = f"🔒 Нужны права: {', '.join(error.missing_permissions)}"
    elif isinstance(error, app_commands.BotMissingPermissions):
        msg = f"🤖 Боту нужны права: {', '.join(error.missing_permissions)}"
    elif isinstance(error, app_commands.CheckFailure):
        msg = f"❌ {error}"
    else:
        log.exception("Ошибка команды", exc_info=error)
        msg = "💥 Внутренняя ошибка."
    try:
        if interaction.response.is_done():
            await interaction.followup.send(embed=error_embed(msg), ephemeral=True)
        else:
            await interaction.response.send_message(embed=error_embed(msg), ephemeral=True)
    except discord.HTTPException:
        pass


async def on_command_error(ctx: commands.Context, error: commands.CommandError) -> None:
    if isinstance(error, commands.CommandNotFound):
        return
    log.exception("Ошибка префиксной команды", exc_info=error)

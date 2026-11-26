"""Хелперы для embed."""
from __future__ import annotations

import discord

from config import BOT_VERSION, COLOR_ERROR, COLOR_PRIMARY, COLOR_SUCCESS, COLOR_WARNING


def base_embed(title: str | None = None, description: str | None = None, color: int = COLOR_PRIMARY) -> discord.Embed:
    embed = discord.Embed(title=title, description=description, color=color)
    embed.set_footer(text=f"ServerBuilder • v{BOT_VERSION}")
    return embed


def success_embed(description: str, title: str = "✅ Готово") -> discord.Embed:
    return base_embed(title=title, description=description, color=COLOR_SUCCESS)


def error_embed(description: str, title: str = "❌ Ошибка") -> discord.Embed:
    return base_embed(title=title, description=description, color=COLOR_ERROR)


def warning_embed(description: str, title: str = "⚠️ Внимание") -> discord.Embed:
    return base_embed(title=title, description=description, color=COLOR_WARNING)

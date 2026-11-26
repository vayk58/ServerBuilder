"""Проверки прав."""
from __future__ import annotations

import discord
from discord import app_commands


def is_moderator() -> app_commands.check:
    async def predicate(interaction: discord.Interaction) -> bool:
        if not isinstance(interaction.user, discord.Member):
            raise app_commands.CheckFailure("Только на сервере.")
        if not interaction.user.guild_permissions.moderate_members:
            raise app_commands.CheckFailure("Нужно право «Модерировать участников».")
        return True
    return app_commands.check(predicate)


def is_admin() -> app_commands.check:
    async def predicate(interaction: discord.Interaction) -> bool:
        if not isinstance(interaction.user, discord.Member):
            raise app_commands.CheckFailure("Только на сервере.")
        if not interaction.user.guild_permissions.administrator:
            raise app_commands.CheckFailure("Нужно право «Администратор».")
        return True
    return app_commands.check(predicate)


def can_manage_guild() -> app_commands.check:
    async def predicate(interaction: discord.Interaction) -> bool:
        if not isinstance(interaction.user, discord.Member):
            raise app_commands.CheckFailure("Только на сервере.")
        if not interaction.user.guild_permissions.manage_guild:
            raise app_commands.CheckFailure("Нужно право «Управление сервером».")
        return True
    return app_commands.check(predicate)

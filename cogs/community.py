"""Правила и предложения."""
from __future__ import annotations

import discord
from discord import app_commands
from discord.ext import commands

from utils.checks import is_admin
from utils.embeds import base_embed, error_embed, success_embed


class RulesView(discord.ui.View):
    def __init__(self, guild_id: int) -> None:
        super().__init__(timeout=None)
        self.guild_id = guild_id
        self.accept_btn.custom_id = f"sb:rules:{guild_id}:accept"

    @discord.ui.button(label="Принимаю", style=discord.ButtonStyle.success)
    async def accept_btn(self, i: discord.Interaction, _: discord.ui.Button) -> None:
        db = i.client.db  # type: ignore[attr-defined]
        row = await db.get_rules(i.guild.id)
        if not row or not row["role_id"]:
            await i.response.send_message(embed=error_embed("Не настроено."), ephemeral=True)
            return
        role = i.guild.get_role(row["role_id"])
        if not role:
            await i.response.send_message(embed=error_embed("Роль удалена."), ephemeral=True)
            return
        try:
            await i.user.add_roles(role, reason="Правила приняты")
            await db.accept_rules(i.guild.id, i.user.id)
            await i.response.send_message(embed=success_embed(f"Роль {role.mention} выдана."), ephemeral=True)
        except discord.Forbidden:
            await i.response.send_message(embed=error_embed("Нет прав."), ephemeral=True)


class SuggestionView(discord.ui.View):
    def __init__(self) -> None:
        super().__init__(timeout=None)

    @discord.ui.button(label="👍", style=discord.ButtonStyle.success, custom_id="sb:suggest:up")
    async def up(self, i: discord.Interaction, _: discord.ui.Button) -> None:
        await self._vote(i, 1)

    @discord.ui.button(label="👎", style=discord.ButtonStyle.danger, custom_id="sb:suggest:down")
    async def down(self, i: discord.Interaction, _: discord.ui.Button) -> None:
        await self._vote(i, -1)

    async def _vote(self, i: discord.Interaction, vote: int) -> None:
        db = i.client.db  # type: ignore[attr-defined]
        sug = await db.get_suggestion_by_message(i.message.id)
        if not sug or sug["status"] != "open":
            await i.response.send_message(embed=error_embed("Закрыто."), ephemeral=True)
            return
        await db.vote_suggestion(sug["id"], i.user.id, vote)
        votes = await db.get_suggestion_votes(sug["id"])
        embed = base_embed(
            title="💡 Предложение",
            description=f"{sug['content']}\n\n👍 **{votes.get(1, 0)}** | 👎 **{votes.get(-1, 0)}**",
        )
        embed.set_footer(text=f"Автор: {sug['author_id']} • ServerBuilder")
        await i.response.edit_message(embed=embed)


class Community(commands.Cog):
    def __init__(self, bot: commands.Bot) -> None:
        self.bot = bot
        self.db = bot.db  # type: ignore[attr-defined]

    async def cog_load(self) -> None:
        self.bot.add_view(SuggestionView())
        rows = await self.db.fetchall("SELECT guild_id FROM guild_rules")
        for r in rows:
            self.bot.add_view(RulesView(r["guild_id"]))

    @app_commands.command(name="rules", description="Панель правил с принятием")
    @is_admin()
    async def rules(self, i: discord.Interaction, role: discord.Role, text: str = "") -> None:
        rules_text = text or "1. Уважайте друг друга\n2. Без спама\n3. Без NSFW\n4. Слушайте модераторов"
        embed = base_embed(
            title="📜 Правила", description=f"{rules_text}\n\nНажмите кнопку ниже для доступа."
        )
        msg = await i.channel.send(embed=embed, view=RulesView(i.guild.id))
        await self.db.set_rules(i.guild.id, i.channel_id, msg.id, role.id, rules_text)
        await i.response.send_message(embed=success_embed(f"Установлено. Роль: {role.mention}."), ephemeral=True)

    @app_commands.command(name="suggest", description="💡 Предложить идею")
    async def suggest(self, i: discord.Interaction, text: str) -> None:
        embed = base_embed(title="💡 Предложение", description=f"{text}\n\n👍 **0** | 👎 **0**")
        embed.set_footer(text=f"Автор: {i.user.id} • ServerBuilder")
        await i.response.send_message(embed=embed, view=SuggestionView())
        msg = await i.original_response()
        await self.db.create_suggestion(i.guild.id, i.channel_id, msg.id, i.user.id, text)

    @app_commands.command(name="suggestion-close", description="Закрыть предложение")
    @is_admin()
    async def close_suggestion(self, i: discord.Interaction, message_id: str, status: str = "accepted") -> None:
        try:
            mid = int(message_id)
        except ValueError:
            await i.response.send_message(embed=error_embed("message_id — число."), ephemeral=True)
            return
        sug = await self.db.get_suggestion_by_message(mid)
        if not sug:
            await i.response.send_message(embed=error_embed("Не найдено."), ephemeral=True)
            return
        await self.db.set_suggestion_status(sug["id"], status)
        await i.response.send_message(embed=success_embed(f"#{sug['id']} → **{status}**."), ephemeral=True)


async def setup(bot: commands.Bot) -> None:
    await bot.add_cog(Community(bot))

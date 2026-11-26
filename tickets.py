"""Тикеты поддержки."""
from __future__ import annotations

import asyncio
import io
from datetime import datetime, timezone

import discord
from discord import app_commands
from discord.ext import commands

from config import PANEL_TICKET_CREATE
from utils.checks import is_admin
from utils.embeds import base_embed, error_embed, success_embed

CATS = {"general": "❓ Вопрос", "report": "🚨 Жалоба", "bug": "🐛 Баг", "other": "📝 Другое"}


class CatSelect(discord.ui.Select):
    def __init__(self) -> None:
        super().__init__(placeholder="Категория", options=[discord.SelectOption(label=v, value=k) for k, v in CATS.items()])

    async def callback(self, i: discord.Interaction) -> None:
        db = i.client.db  # type: ignore[attr-defined]
        cfg = await db.fetchone("SELECT * FROM ticket_settings WHERE guild_id = ?", (i.guild.id,))  # type: ignore[union-attr]
        if not cfg or not cfg["category_id"]:
            await i.response.send_message(embed=error_embed("Тикеты не настроены."), ephemeral=True)
            return
        ex = await db.fetchone("SELECT * FROM tickets WHERE guild_id = ? AND user_id = ? AND status = 'open'", (i.guild.id, i.user.id))  # type: ignore[union-attr]
        if ex:
            await i.response.send_message(embed=error_embed(f"Уже есть тикет: <#{ex['channel_id']}>"), ephemeral=True)
            return
        cat = i.guild.get_channel(cfg["category_id"])  # type: ignore[union-attr]
        sr = i.guild.get_role(cfg["support_role_id"]) if cfg["support_role_id"] else None  # type: ignore[union-attr]
        me = i.guild.me or i.guild.get_member(i.client.user.id)  # type: ignore[union-attr]
        ow = {
            i.guild.default_role: discord.PermissionOverwrite(view_channel=False),  # type: ignore[union-attr]
            i.user: discord.PermissionOverwrite(view_channel=True, send_messages=True),
        }
        if me: ow[me] = discord.PermissionOverwrite(view_channel=True, send_messages=True, manage_channels=True)
        if sr: ow[sr] = discord.PermissionOverwrite(view_channel=True, send_messages=True)
        ch = await i.guild.create_text_channel(  # type: ignore[union-attr]
            name=f"ticket-{i.user.name}"[:100],
            category=cat if isinstance(cat, discord.CategoryChannel) else None,
            overwrites=ow, reason="Тикет",
        )
        await db.execute(
            "INSERT INTO tickets (guild_id, channel_id, user_id, category) VALUES (?, ?, ?, ?)",
            (i.guild.id, ch.id, i.user.id, self.values[0]),  # type: ignore[union-attr]
        )
        await ch.send(
            content=i.user.mention,
            embed=base_embed(title=f"🎫 {CATS[self.values[0]]}", description="Опишите проблему."),
            view=TicketCtrl(),
        )
        await i.response.send_message(embed=success_embed(f"Тикет: {ch.mention}"), ephemeral=True)


class TicketPanel(discord.ui.View):
    def __init__(self) -> None:
        super().__init__(timeout=None)

    @discord.ui.button(label="Создать тикет", style=discord.ButtonStyle.success, custom_id=PANEL_TICKET_CREATE)
    async def create(self, i: discord.Interaction, _: discord.ui.Button) -> None:
        v = discord.ui.View(timeout=120)
        v.add_item(CatSelect())
        await i.response.send_message("Категория:", view=v, ephemeral=True)


class TicketCtrl(discord.ui.View):
    def __init__(self) -> None:
        super().__init__(timeout=None)

    @discord.ui.button(label="Взять", style=discord.ButtonStyle.primary, custom_id="sb:ticket:claim")
    async def claim(self, i: discord.Interaction, _: discord.ui.Button) -> None:
        if not i.user.guild_permissions.manage_messages:  # type: ignore[union-attr]
            await i.response.send_message(embed=error_embed("Только поддержка."), ephemeral=True)
            return
        db = i.client.db  # type: ignore[attr-defined]
        await db.execute("UPDATE tickets SET claimed_by = ? WHERE channel_id = ?", (i.user.id, i.channel_id))
        await i.response.send_message(embed=success_embed(f"Взят: {i.user.mention}"))

    @discord.ui.button(label="Закрыть", style=discord.ButtonStyle.danger, custom_id="sb:ticket:close")
    async def close(self, i: discord.Interaction, _: discord.ui.Button) -> None:
        if not i.user.guild_permissions.manage_messages:  # type: ignore[union-attr]
            await i.response.send_message(embed=error_embed("Только поддержка."), ephemeral=True)
            return
        await i.response.defer()
        db = i.client.db  # type: ignore[attr-defined]
        row = await db.fetchone("SELECT * FROM tickets WHERE channel_id = ?", (i.channel_id,))
        if not row:
            await i.followup.send(embed=error_embed("Не найден."))
            return
        lines = []
        async for m in i.channel.history(limit=1000, oldest_first=True):  # type: ignore[union-attr]
            lines.append(f"[{m.created_at:%Y-%m-%d %H:%M}] {m.author}: {m.content}")
        txt = "\n".join(lines) or "(пусто)"
        f = discord.File(io.BytesIO(txt.encode("utf-8")), filename=f"transcript-{i.channel.name}.txt")  # type: ignore[union-attr]
        cfg = await db.fetchone("SELECT log_channel_id FROM ticket_settings WHERE guild_id = ?", (i.guild.id,))  # type: ignore[union-attr]
        if cfg and cfg["log_channel_id"]:
            lc = i.guild.get_channel(cfg["log_channel_id"])  # type: ignore[union-attr]
            if isinstance(lc, discord.TextChannel):
                try:
                    await lc.send(
                        embed=base_embed(title="🎫 Закрыт",
                                         description=f"**Автор:** <@{row['user_id']}>\n**Закрыл:** {i.user}"),
                        file=f,
                    )
                except discord.HTTPException:
                    pass
        await db.execute(
            "UPDATE tickets SET status = 'closed', closed_at = ? WHERE channel_id = ?",
            (datetime.now(timezone.utc).replace(tzinfo=None), i.channel_id),
        )
        await i.followup.send(embed=success_embed("Закрыт. Удаление через 5 сек."))
        await asyncio.sleep(5)
        try:
            await i.channel.delete(reason="Тикет закрыт")  # type: ignore[union-attr]
        except discord.HTTPException:
            pass


class Tickets(commands.Cog):
    def __init__(self, bot: commands.Bot) -> None:
        self.bot = bot
        self.db = bot.db  # type: ignore[attr-defined]

    async def cog_load(self) -> None:
        self.bot.add_view(TicketPanel())
        self.bot.add_view(TicketCtrl())

    @app_commands.command(name="setup-tickets", description="Настроить панель тикетов")
    @is_admin()
    async def setup_tickets(self, i: discord.Interaction, category: discord.CategoryChannel,
                            support_role: discord.Role, log_channel: discord.TextChannel) -> None:
        await self.db.execute(
            "INSERT OR REPLACE INTO ticket_settings (guild_id, panel_channel_id, category_id, support_role_id, log_channel_id) "
            "VALUES (?, ?, ?, ?, ?)",
            (i.guild.id, i.channel_id, category.id, support_role.id, log_channel.id),  # type: ignore[union-attr]
        )
        await i.channel.send(  # type: ignore[union-attr]
            embed=base_embed(title="🎫 Поддержка", description="Нажмите кнопку."),
            view=TicketPanel(),
        )
        await i.response.send_message(embed=success_embed("Панель создана."), ephemeral=True)


async def setup(bot: commands.Bot) -> None:
    await bot.add_cog(Tickets(bot))

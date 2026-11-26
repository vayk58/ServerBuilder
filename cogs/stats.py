"""Статистика."""
from __future__ import annotations

import io
from datetime import datetime as _dt, timedelta as _td, timezone as _tz

import discord
from discord import app_commands
from discord.ext import commands

from utils.checks import is_moderator
from utils.embeds import base_embed, error_embed


class Stats(commands.Cog):
    def __init__(self, bot: commands.Bot) -> None:
        self.bot = bot
        self.db = bot.db  # type: ignore[attr-defined]

    @app_commands.command(name="stats", description="Топ активных")
    async def stats(self, i: discord.Interaction) -> None:
        tl = await self.db.fetchall(
            "SELECT user_id, level, xp, messages FROM levels WHERE guild_id = ? ORDER BY level DESC, xp DESC LIMIT 10",
            (i.guild.id,),  # type: ignore[union-attr]
        )
        tc = await self.db.fetchall(
            "SELECT moderator_id, COUNT(*) AS cnt FROM cases WHERE guild_id = ? GROUP BY moderator_id ORDER BY cnt DESC LIMIT 5",
            (i.guild.id,),  # type: ignore[union-attr]
        )
        e = base_embed(title=f"📊 {i.guild.name}")  # type: ignore[union-attr]
        if tl:
            e.add_field(name="🏆 По уровню",
                value="\n".join(f"**{k}. <@{r['user_id']}>** — ур.{r['level']} ({r['messages']})" for k, r in enumerate(tl, 1)),
                inline=False)
        if tc:
            e.add_field(name="🛡 Модераторы",
                value="\n".join(f"**{k}. <@{r['moderator_id']}>** — {r['cnt']}" for k, r in enumerate(tc, 1)),
                inline=False)
        e.add_field(name="👥", value=str(i.guild.member_count), inline=True)  # type: ignore[union-attr]
        e.add_field(name="📅", value=f"{(discord.utils.utcnow() - i.guild.created_at).days} дн.", inline=True)  # type: ignore[union-attr]
        await i.response.send_message(embed=e)

    @app_commands.command(name="activity-chart", description="График за 7 дней")
    @is_moderator()
    async def chart(self, i: discord.Interaction) -> None:
        await i.response.defer()
        try:
            import matplotlib
            matplotlib.use("Agg")
            import matplotlib.pyplot as plt
        except ImportError:
            await i.followup.send(embed=error_embed("Установите matplotlib."), ephemeral=True); return
        rows = await self.db.get_activity_by_day(i.guild.id, days=7)  # type: ignore[union-attr]
        if not rows:
            await i.followup.send(embed=error_embed("Нет данных. Активность появится после сообщений."), ephemeral=True); return
        dm = dict(rows)
        labels, values = [], []
        for k in range(6, -1, -1):
            d = (_dt.now(_tz.utc) - _td(days=k)).strftime("%Y-%m-%d")
            labels.append(d[5:]); values.append(dm.get(d, 0))
        fig, ax = plt.subplots(figsize=(8, 4))
        ax.bar(labels, values, color="#5865F2")
        ax.set_title("Активность за 7 дней")
        ax.set_ylabel("Сообщений")
        for s in ("top", "right"): ax.spines[s].set_visible(False)
        buf = io.BytesIO()
        fig.savefig(buf, format="png", dpi=120, bbox_inches="tight")
        plt.close(fig); buf.seek(0)
        await i.followup.send(file=discord.File(buf, filename="activity.png"))

    @app_commands.command(name="audit", description="Аудит модерации")
    @is_moderator()
    async def audit(self, i: discord.Interaction, limit: int = 10) -> None:
        rows = await self.db.fetchall(
            "SELECT * FROM cases WHERE guild_id = ? ORDER BY created_at DESC LIMIT ?",
            (i.guild.id, min(limit, 25)),  # type: ignore[union-attr]
        )
        if not rows:
            await i.response.send_message(embed=error_embed("Пусто."), ephemeral=True); return
        e = base_embed(title="🕵 Аудит")
        for r in rows:
            e.add_field(
                name=f"{r['action'].upper()} · <@{r['user_id']}>",
                value=f"**Мод:** <@{r['moderator_id']}>\n**Причина:** {r['reason'][:80]}\n**Когда:** {r['created_at']}",
                inline=False,
            )
        await i.response.send_message(embed=e, ephemeral=True)


async def setup(bot: commands.Bot) -> None:
    await bot.add_cog(Stats(bot))

"""Розыгрыши (persistent в БД)."""
from __future__ import annotations

import asyncio
import logging
import random
from datetime import datetime, timedelta, timezone

import discord
from discord import app_commands
from discord.ext import commands

from utils.checks import is_admin
from utils.embeds import base_embed, error_embed, success_embed

log = logging.getLogger(__name__)
GC = "sb:giveaway:join"


class GWView(discord.ui.View):
    def __init__(self) -> None:
        super().__init__(timeout=None)

    @discord.ui.button(label="🎉 Участвовать", style=discord.ButtonStyle.success, custom_id=GC)
    async def join(self, i: discord.Interaction, _) -> None:
        db = i.client.db  # type: ignore[attr-defined]
        row = await db.get_giveaway(i.message.id)
        if not row or row["ended"]:
            await i.response.send_message(embed=error_embed("Завершён."), ephemeral=True); return
        parts = set(row["participants"].split(",")) if row["participants"] else set()
        parts.discard("")
        uid = str(i.user.id)
        if uid in parts:
            parts.discard(uid); msg = "Вы больше не участвуете."
        else:
            parts.add(uid); msg = f"Участвуете! Всего: {len(parts)}"
        await db.update_giveaway_participants(i.message.id, ",".join(parts))
        await i.response.send_message(embed=success_embed(msg), ephemeral=True)


class Giveaways(commands.Cog):
    def __init__(self, bot: commands.Bot) -> None:
        self.bot = bot
        self.db = bot.db  # type: ignore[attr-defined]

    async def cog_load(self) -> None:
        self.bot.add_view(GWView())
        rows = await self.db.get_active_giveaways()
        for r in rows:
            end = r["end_at"]
            if isinstance(end, str): end = datetime.fromisoformat(end)
            left = (end - datetime.now(timezone.utc).replace(tzinfo=None)).total_seconds()
            if left <= 0:
                asyncio.create_task(self._finish(r["message_id"]))
            else:
                asyncio.create_task(self._wait(r["message_id"], left))
        log.info("Giveaways: %d", len(rows))

    async def _wait(self, mid: int, delay: float) -> None:
        await asyncio.sleep(delay)
        await self._finish(mid)

    async def _finish(self, mid: int) -> None:
        row = await self.db.get_giveaway(mid)
        if not row or row["ended"]: return
        await self.db.end_giveaway(mid)
        ch = self.bot.get_channel(row["channel_id"])
        if not ch: return
        parts = [int(u) for u in row["participants"].split(",") if u]
        if not parts:
            try:
                await ch.send(embed=base_embed(title="🎉 Завершён", description=f"Приз **{row['prize']}** — нет участников."))
            except discord.HTTPException:
                pass
            return
        winners = random.sample(parts, k=min(row["winners"], len(parts)))
        mentions = ", ".join(f"<@{u}>" for u in winners)
        try:
            await ch.send(content=mentions,
                embed=base_embed(title="🎉 Завершён!",
                    description=f"Приз: **{row['prize']}**\nПобедители: {mentions}"))
        except discord.HTTPException:
            pass

    @app_commands.command(name="giveaway", description="Запустить розыгрыш")
    @is_admin()
    async def giveaway(self, i: discord.Interaction, prize: str, minutes: int, winners: int = 1) -> None:
        if not 1 <= minutes <= 10080:
            await i.response.send_message(embed=error_embed("1–10080 мин."), ephemeral=True); return
        if not 1 <= winners <= 20:
            await i.response.send_message(embed=error_embed("1–20."), ephemeral=True); return
        end = datetime.now(timezone.utc) + timedelta(minutes=minutes)
        msg = await i.channel.send(  # type: ignore[union-attr]
            embed=base_embed(title=f"🎉 {prize}",
                description=f"**Победителей:** {winners}\n**До:** <t:{int(end.timestamp())}:R>\n\nНажмите кнопку!"),
            view=GWView(),
        )
        await self.db.create_giveaway(
            msg.id, i.guild.id, i.channel_id, prize, winners, i.user.id,  # type: ignore[union-attr]
            end.replace(tzinfo=None).isoformat(),
        )
        await i.response.send_message(embed=success_embed(f"{msg.jump_url}"), ephemeral=True)
        asyncio.create_task(self._wait(msg.id, minutes * 60))


async def setup(bot: commands.Bot) -> None:
    await bot.add_cog(Giveaways(bot))

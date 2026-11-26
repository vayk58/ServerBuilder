"""Анти-рейд."""
from __future__ import annotations

import asyncio
import logging
import time
from collections import defaultdict, deque

import discord
from discord import app_commands
from discord.ext import commands

from utils.checks import is_admin
from utils.embeds import base_embed, error_embed, success_embed

log = logging.getLogger(__name__)


class AntiRaid(commands.Cog):
    def __init__(self, bot: commands.Bot) -> None:
        self.bot = bot
        self.db = bot.db  # type: ignore[attr-defined]
        self._joins: dict[int, deque] = defaultdict(lambda: deque(maxlen=100))
        self._lockdown: set[int] = set()

    @commands.Cog.listener()
    async def on_member_join(self, member: discord.Member) -> None:
        if member.bot:
            return
        cfg = await self.db.get_antiraid(member.guild.id)
        if not cfg or not cfg["enabled"]:
            return
        now = time.time()
        q = self._joins[member.guild.id]
        q.append(now)
        window = cfg["time_window"] or 60
        recent = [t for t in q if now - t <= window]
        if len(recent) >= (cfg["join_threshold"] or 10):
            if member.guild.id in self._lockdown:
                return
            await self._lock(member.guild, len(recent))
            self._joins[member.guild.id].clear()

    async def _lock(self, guild: discord.Guild, count: int) -> None:
        self._lockdown.add(guild.id)
        try:
            for ch in guild.channels:
                try:
                    ow = ch.overwrites_for(guild.default_role)
                    ow.view_channel = False
                    await ch.set_permissions(guild.default_role, overwrite=ow, reason="Antiraid")
                except discord.HTTPException:
                    pass
            await self.db.log_antiraid(guild.id, "LOCKDOWN", f"{count} joins")
            cfg = await self.db.get_antiraid(guild.id)
            notify = guild.get_channel(cfg["notify_channel_id"]) if cfg and cfg["notify_channel_id"] else None
            if not notify:
                notify = discord.utils.find(
                    lambda c: isinstance(c, discord.TextChannel) and ("log" in c.name.lower() or "мод" in c.name.lower()),
                    guild.text_channels,
                )
            if notify:
                try:
                    await notify.send(
                        embed=base_embed(
                            title="🚨 АНТИ-РЕЙД АКТИВИРОВАН",
                            description=f"**{count}** входов за короткое время. Сервер в LOCKDOWN.\n`/antiraid unlock` для снятия.",
                            color=0xED4245,
                        )
                    )
                except discord.HTTPException:
                    pass
            log.warning("Antiraid lockdown: %s", guild.id)
        finally:
            await asyncio.sleep(300)

    @app_commands.command(name="antiraid", description="Анти-рейд")
    @app_commands.choices(action=[
        app_commands.Choice(name="enable", value="enable"),
        app_commands.Choice(name="disable", value="disable"),
        app_commands.Choice(name="status", value="status"),
        app_commands.Choice(name="unlock", value="unlock"),
        app_commands.Choice(name="settings", value="settings"),
    ])
    @is_admin()
    async def antiraid(
        self, i: discord.Interaction, action: str,
        threshold: int | None = None, window: int | None = None,
        notify_channel: discord.TextChannel | None = None,
    ) -> None:
        gid = i.guild.id
        if action == "enable":
            await self.db.set_antiraid(gid, enabled=1)
            await i.response.send_message(embed=success_embed("Включён."), ephemeral=True)
        elif action == "disable":
            await self.db.set_antiraid(gid, enabled=0)
            await i.response.send_message(embed=success_embed("Выключен."), ephemeral=True)
        elif action == "unlock":
            self._lockdown.discard(gid)
            count = 0
            for ch in i.guild.channels:
                try:
                    ow = ch.overwrites_for(i.guild.default_role)
                    ow.view_channel = None
                    await ch.set_permissions(i.guild.default_role, overwrite=ow)
                    count += 1
                except discord.HTTPException:
                    pass
            await i.response.send_message(embed=success_embed(f"Lockdown снят. Каналов: {count}."), ephemeral=True)
        elif action == "settings":
            kw = {}
            if threshold is not None: kw["join_threshold"] = max(2, min(100, threshold))
            if window is not None: kw["time_window"] = max(10, min(600, window))
            if notify_channel: kw["notify_channel_id"] = notify_channel.id
            if kw:
                await self.db.set_antiraid(gid, **kw)
            await i.response.send_message(embed=success_embed("Настройки обновлены."), ephemeral=True)
        else:
            cfg = await self.db.get_antiraid(gid)
            if not cfg:
                await i.response.send_message(embed=error_embed("Не настроен."), ephemeral=True)
                return
            embed = base_embed(title="🚨 Анти-рейд — статус")
            embed.add_field(name="Статус", value="✅" if cfg["enabled"] else "❌")
            embed.add_field(name="Порог", value=str(cfg["join_threshold"]))
            embed.add_field(name="Окно", value=f"{cfg['time_window']}с")
            embed.add_field(name="Lockdown", value="🔴" if gid in self._lockdown else "🟢")
            await i.response.send_message(embed=embed, ephemeral=True)


async def setup(bot: commands.Bot) -> None:
    await bot.add_cog(AntiRaid(bot))

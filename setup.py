"""Оформление сервера и бэкапы."""
from __future__ import annotations

import json
import logging
from datetime import datetime

import discord
from discord import app_commands
from discord.ext import commands

from config import BASE_DIR
from utils.checks import can_manage_guild, is_admin
from utils.embeds import base_embed, error_embed, success_embed

log = logging.getLogger(__name__)


class Setup(commands.Cog):
    def __init__(self, bot: commands.Bot) -> None:
        self.bot = bot
        self.db = bot.db  # type: ignore[attr-defined]

    @app_commands.command(name="create-category", description="Создать категорию")
    @can_manage_guild()
    async def create_category(self, i: discord.Interaction, name: str) -> None:
        await i.guild.create_category(name)  # type: ignore[union-attr]
        await i.response.send_message(embed=success_embed(f"**{name}** создана."), ephemeral=True)

    @app_commands.command(name="create-channel", description="Создать канал")
    @app_commands.choices(channel_type=[
        app_commands.Choice(name="Текст", value="text"),
        app_commands.Choice(name="Голос", value="voice"),
    ])
    @can_manage_guild()
    async def create_channel(self, i: discord.Interaction, name: str, channel_type: str, category: discord.CategoryChannel | None = None) -> None:
        if channel_type == "text":
            ch = await i.guild.create_text_channel(name, category=category)  # type: ignore[union-attr]
        else:
            ch = await i.guild.create_voice_channel(name, category=category)  # type: ignore[union-attr]
        await i.response.send_message(embed=success_embed(f"{ch.mention} создан."), ephemeral=True)

    @app_commands.command(name="create-role", description="Создать роль")
    @can_manage_guild()
    async def create_role(self, i: discord.Interaction, name: str, color: str = "#5865F2") -> None:
        try:
            c = discord.Color(int(color.lstrip("#"), 16))
        except ValueError:
            await i.response.send_message(embed=error_embed("HEX неверный."), ephemeral=True)
            return
        r = await i.guild.create_role(name=name, color=c)  # type: ignore[union-attr]
        await i.response.send_message(embed=success_embed(f"{r.mention} создана."), ephemeral=True)

    @app_commands.command(name="backup", description="Бэкап структуры в БД")
    @is_admin()
    async def backup(self, i: discord.Interaction) -> None:
        await i.response.defer(ephemeral=True)
        g = i.guild
        def ow(o):  # type: ignore[no-untyped-def]
            return [{"tid": t.id, "tt": "role" if isinstance(t, discord.Role) else "member",
                     "a": p.pair()[0].value, "d": p.pair()[1].value} for t, p in o.items()]
        data = {
            "name": g.name,  # type: ignore[union-attr]
            "roles": [{"name": r.name, "perm": r.permissions.value, "col": r.color.value,
                       "hoist": r.hoist, "ment": r.mentionable} for r in g.roles if not r.is_default() and not r.managed],  # type: ignore[union-attr]
            "categories": [{"name": c.name, "ow": ow(c.overwrites),
                            "channels": [{"name": ch.name, "t": "text" if isinstance(ch, discord.TextChannel) else "voice",
                                          "topic": getattr(ch, "topic", None), "ow": ow(ch.overwrites)} for ch in c.channels]}
                           for c in g.categories],  # type: ignore[union-attr]
        }
        await self.db.execute("INSERT INTO backups (guild_id, data) VALUES (?, ?)", (g.id, json.dumps(data, ensure_ascii=False)))  # type: ignore[union-attr]
        await i.followup.send(embed=success_embed("Бэкап сохранён в БД."), ephemeral=True)

    @app_commands.command(name="backup-export", description="Экспорт в JSON файл")
    @is_admin()
    async def backup_export(self, i: discord.Interaction) -> None:
        await i.response.defer(ephemeral=True)
        g = i.guild
        d = BASE_DIR / "backups"; d.mkdir(exist_ok=True)
        def ow(o):  # type: ignore[no-untyped-def]
            return [{"tid": t.id, "tt": "role" if isinstance(t, discord.Role) else "member",
                     "a": p.pair()[0].value, "d": p.pair()[1].value} for t, p in o.items()]
        data = {
            "name": g.name, "guild_id": g.id, "ts": datetime.utcnow().isoformat(),  # type: ignore[union-attr]
            "roles": [{"name": r.name, "perm": r.permissions.value, "col": r.color.value,
                       "hoist": r.hoist, "ment": r.mentionable} for r in g.roles if not r.is_default() and not r.managed],  # type: ignore[union-attr]
            "categories": [{"name": c.name, "ow": ow(c.overwrites),
                            "channels": [{"name": ch.name, "t": "text" if isinstance(ch, discord.TextChannel) else "voice",
                                          "topic": getattr(ch, "topic", None), "ow": ow(ch.overwrites)} for ch in c.channels]}
                           for c in g.categories],  # type: ignore[union-attr]
        }
        p = d / f"backup_{g.id}_{datetime.utcnow():%Y%m%d_%H%M%S}.json"  # type: ignore[union-attr]
        p.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
        sz = p.stat().st_size
        if sz <= 8 * 1024 * 1024:
            await i.followup.send(embed=success_embed(f"{p.name} ({sz / 1024:.1f} КБ)"),
                                  file=discord.File(p, filename=p.name), ephemeral=True)
        else:
            await i.followup.send(embed=base_embed(
                title="💾 Бэкап на диске",
                description=f"Размер {sz / 1024 / 1024:.1f} МБ — большой для Discord.\nПуть: `{p}`"
            ), ephemeral=True)

    @app_commands.command(name="backup-import", description="Импорт из JSON")
    @is_admin()
    async def backup_import(self, i: discord.Interaction, file: discord.Attachment) -> None:
        if not file.filename.endswith(".json"):
            await i.response.send_message(embed=error_embed("Нужен .json."), ephemeral=True)
            return
        await i.response.defer(ephemeral=True)
        try:
            data = json.loads((await file.read()).decode("utf-8"))
        except Exception:
            await i.followup.send(embed=error_embed("Не прочитать."), ephemeral=True)
            return
        cr = cc = 0
        ex_r = {r.name for r in i.guild.roles}  # type: ignore[union-attr]
        for r in data.get("roles", []):
            if r["name"] in ex_r: continue
            try:
                await i.guild.create_role(  # type: ignore[union-attr]
                    name=r["name"], permissions=discord.Permissions(r["perm"]),
                    color=discord.Color(r["col"]), hoist=r["hoist"], mentionable=r["ment"],
                )
                cr += 1
            except discord.HTTPException:
                pass
        ex_c = {c.name for c in i.guild.categories}  # type: ignore[union-attr]
        for cat in data.get("categories", []):
            if cat["name"] in ex_c: continue
            try:
                c = await i.guild.create_category(cat["name"])  # type: ignore[union-attr]
                cc += 1
                for ch in cat.get("channels", []):
                    if ch["t"] == "text":
                        await c.create_text_channel(ch["name"], topic=ch.get("topic"))
                    else:
                        await c.create_voice_channel(ch["name"])
            except discord.HTTPException:
                pass
        await i.followup.send(embed=success_embed(f"Ролей: {cr}, категорий: {cc}."), ephemeral=True)


async def setup(bot: commands.Bot) -> None:
    await bot.add_cog(Setup(bot))

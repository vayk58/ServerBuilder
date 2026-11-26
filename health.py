"""Аудит сервера."""
from __future__ import annotations

import discord
from discord import app_commands
from discord.ext import commands

from utils.checks import is_admin
from utils.embeds import base_embed


class Health(commands.Cog):
    def __init__(self, bot: commands.Bot) -> None:
        self.bot = bot
        self.db = bot.db  # type: ignore[attr-defined]

    @app_commands.command(name="health", description="Аудит сервера с оценкой 0-100")
    @is_admin()
    async def health(self, i: discord.Interaction) -> None:
        await i.response.defer()
        g = i.guild
        score = 0
        issues: list[str] = []
        good: list[str] = []

        rules = await self.db.get_rules(g.id)
        if rules and rules["channel_id"] and g.get_channel(rules["channel_id"]):
            score += 10; good.append("📜 Правила")
        else:
            issues.append("📜 **Правила не настроены**")

        ws = await self.db.fetchone("SELECT * FROM welcome_settings WHERE guild_id = ?", (g.id,))
        if ws and ws["verify_role_id"]:
            score += 10; good.append("🔐 Верификация")
        else:
            issues.append("🔐 **Верификация не настроена**")

        if ws and ws["welcome_channel_id"]:
            score += 10; good.append("👋 Приветствие")
        else:
            issues.append("👋 **Нет приветствия**")

        am = await self.db.fetchone("SELECT * FROM automod_settings WHERE guild_id = ?", (g.id,))
        if am and (am["bad_words"] or am["spam"] or am["invites"] or am["mass_mentions"]):
            score += 10; good.append("🛡 Автомод")
        else:
            issues.append("🛡 **Автомод выключен**")

        ar = await self.db.get_antiraid(g.id)
        if ar and ar["enabled"]:
            score += 10; good.append("🚨 Анти-рейд")
        else:
            issues.append("🚨 **Анти-рейд выключен**")

        ts = await self.db.fetchone("SELECT * FROM ticket_settings WHERE guild_id = ?", (g.id,))
        if ts and ts["category_id"]:
            score += 10; good.append("🎫 Тикеты")
        else:
            issues.append("🎫 **Тикеты не настроены**")

        cs = await self.db.get_comfort_settings(g.id)
        if cs and cs["hub_channel_id"]:
            score += 10; good.append("🎧 Приватные комнаты")
        else:
            issues.append("🎧 **Нет приватных комнат**")

        mod_role = discord.utils.find(lambda r: "mod" in r.name.lower() or "модер" in r.name.lower(), g.roles)
        if mod_role:
            score += 10; good.append(f"🛡 Модератор: {mod_role.mention}")
        else:
            issues.append("🛡 **Нет роли модератора**")

        everyone = g.default_role
        dangerous = []
        if everyone.permissions.administrator: dangerous.append("Administrator")
        if everyone.permissions.manage_guild: dangerous.append("Manage Server")
        if everyone.permissions.manage_roles: dangerous.append("Manage Roles")
        if dangerous:
            issues.append(f"⚠️ **Опасные права @everyone:** {', '.join(dangerous)}")
        else:
            score += 10; good.append("✅ @everyone безопасны")

        s = await self.db.get_settings(g.id)
        if s and s["mod_log_channel"]:
            score += 10; good.append("📋 Мод-логи")
        else:
            issues.append("📋 **Нет канала мод-логов**")

        color = 0x57F287 if score >= 80 else (0xFEE75C if score >= 50 else 0xED4245)
        verdict = "🏆 Отлично" if score >= 90 else "✅ Хорошо" if score >= 70 else "⚠️ Требует внимания" if score >= 40 else "🚨 Критично"
        embed = base_embed(title=f"Здоровье: {score}/100", color=color)
        embed.description = f"**{verdict}**"
        if good:
            embed.add_field(name="✅ Работает", value="\n".join(good[:6]), inline=False)
        if issues:
            embed.add_field(name="❗ Проблемы", value="\n".join(issues[:6]), inline=False)
        humans = sum(1 for m in g.members if not m.bot)
        embed.add_field(
            name="📊",
            value=f"👤 {humans} | 🤖 {g.member_count - humans} | 💬 {len(g.text_channels)} | 🔊 {len(g.voice_channels)} | 🎭 {len(g.roles)} | ✨ {g.premium_subscription_count}",
            inline=False,
        )
        await i.followup.send(embed=embed)


async def setup(bot: commands.Bot) -> None:
    await bot.add_cog(Health(bot))

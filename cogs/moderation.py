"""Модерация."""
from __future__ import annotations

import re
import time
from collections import defaultdict, deque
from datetime import timedelta

import discord
from discord import app_commands
from discord.ext import commands

from utils.checks import is_admin, is_moderator
from utils.embeds import base_embed, error_embed, success_embed, warning_embed

INVITE_RE = re.compile(r"(discord\.gg/|discord(app)?\.com/invite/)", re.IGNORECASE)


class Moderation(commands.Cog):
    def __init__(self, bot: commands.Bot) -> None:
        self.bot = bot
        self.db = bot.db  # type: ignore[attr-defined]
        self._spam: dict[tuple[int, int], deque] = defaultdict(lambda: deque(maxlen=6))

    async def _log(self, guild: discord.Guild, embed: discord.Embed) -> None:
        s = await self.db.get_settings(guild.id)
        if not s or not s["mod_log_channel"]:
            return
        ch = guild.get_channel(s["mod_log_channel"])
        if isinstance(ch, discord.TextChannel):
            try:
                await ch.send(embed=embed)
            except discord.HTTPException:
                pass

    async def _case(self, gid: int, uid: int, mid: int, action: str, reason: str, duration: str = "") -> None:
        await self.db.execute(
            "INSERT INTO cases (guild_id, user_id, moderator_id, action, reason, duration) VALUES (?, ?, ?, ?, ?, ?)",
            (gid, uid, mid, action, reason, duration),
        )

    @app_commands.command(name="set-mod-logs", description="Канал логов модерации")
    @is_admin()
    async def set_mod_logs(self, i: discord.Interaction, channel: discord.TextChannel) -> None:
        await self.db.set_mod_log(i.guild.id, channel.id)
        await i.response.send_message(embed=success_embed(f"→ {channel.mention}"), ephemeral=True)

    @app_commands.command(name="ban", description="Забанить")
    @is_moderator()
    async def ban(self, i: discord.Interaction, member: discord.Member, reason: str = "Не указана") -> None:
        if member.top_role >= i.user.top_role and i.user.id != i.guild.owner_id:  # type: ignore[union-attr]
            await i.response.send_message(embed=error_embed("Нельзя банить равного/выше."), ephemeral=True)
            return
        await member.ban(reason=f"{i.user}: {reason}")
        await self._case(i.guild.id, member.id, i.user.id, "ban", reason)
        await self._log(i.guild, base_embed(title="🔨 Бан", description=f"**{member}**\n**Мод:** {i.user}\n**Причина:** {reason}"))
        await i.response.send_message(embed=success_embed(f"**{member}** забанен."))

    @app_commands.command(name="kick", description="Кикнуть")
    @is_moderator()
    async def kick(self, i: discord.Interaction, member: discord.Member, reason: str = "Не указана") -> None:
        await member.kick(reason=f"{i.user}: {reason}")
        await self._case(i.guild.id, member.id, i.user.id, "kick", reason)
        await i.response.send_message(embed=success_embed(f"**{member}** кикнут."))

    @app_commands.command(name="mute", description="Таймаут")
    @is_moderator()
    async def mute(self, i: discord.Interaction, member: discord.Member, minutes: int = 10, reason: str = "Не указана") -> None:
        if not 1 <= minutes <= 40320:
            await i.response.send_message(embed=error_embed("1–40320 мин."), ephemeral=True)
            return
        until = discord.utils.utcnow() + timedelta(minutes=minutes)
        await member.timeout(until, reason=reason)
        await self._case(i.guild.id, member.id, i.user.id, "mute", reason, f"{minutes}m")
        await i.response.send_message(embed=success_embed(f"**{member}** — мут {minutes} мин."))

    @app_commands.command(name="unmute", description="Снять таймаут")
    @is_moderator()
    async def unmute(self, i: discord.Interaction, member: discord.Member) -> None:
        await member.timeout(None)
        await i.response.send_message(embed=success_embed(f"Мут снят с **{member}**."))

    @app_commands.command(name="warn", description="Предупреждение")
    @is_moderator()
    async def warn(self, i: discord.Interaction, member: discord.Member, reason: str) -> None:
        await self.db.execute(
            "INSERT INTO warnings (guild_id, user_id, moderator_id, reason) VALUES (?, ?, ?, ?)",
            (i.guild.id, member.id, i.user.id, reason),
        )
        row = await self.db.fetchone(
            "SELECT COUNT(*) AS c FROM warnings WHERE guild_id = ? AND user_id = ?",
            (i.guild.id, member.id),
        )
        count = row["c"] if row else 0
        await self._case(i.guild.id, member.id, i.user.id, "warn", reason)
        auto = ""
        if count >= 5:
            try:
                await member.ban(reason="Авто-бан 5 варнов"); auto = "\n🚫 Авто-бан!"
            except discord.HTTPException:
                pass
        elif count >= 3:
            try:
                await member.timeout(discord.utils.utcnow() + timedelta(hours=1), reason="Авто-мут")
                auto = "\n🔇 Авто-мут 1 час!"
            except discord.HTTPException:
                pass
        await i.response.send_message(
            embed=warning_embed(f"**{member}** — предупреждение **({count})**. Причина: {reason}{auto}")
        )

    @app_commands.command(name="warnings", description="Список предупреждений")
    @is_moderator()
    async def warnings(self, i: discord.Interaction, member: discord.Member) -> None:
        rows = await self.db.fetchall(
            "SELECT * FROM warnings WHERE guild_id = ? AND user_id = ? ORDER BY created_at DESC LIMIT 20",
            (i.guild.id, member.id),
        )
        if not rows:
            await i.response.send_message(embed=success_embed(f"У **{member}** нет варнов."), ephemeral=True)
            return
        embed = base_embed(title=f"⚠️ Варны — {member}")
        for r in rows:
            embed.add_field(
                name=f"#{r['id']}",
                value=f"**Мод:** <@{r['moderator_id']}>\n**Причина:** {r['reason']}\n**Когда:** {r['created_at']}",
                inline=False,
            )
        await i.response.send_message(embed=embed, ephemeral=True)

    @app_commands.command(name="case", description="История наказаний")
    @is_moderator()
    async def case_cmd(self, i: discord.Interaction, member: discord.Member) -> None:
        rows = await self.db.fetchall(
            "SELECT * FROM cases WHERE guild_id = ? AND user_id = ? ORDER BY created_at DESC LIMIT 25",
            (i.guild.id, member.id),
        )
        if not rows:
            await i.response.send_message(embed=success_embed("Наказаний нет."), ephemeral=True)
            return
        embed = base_embed(title=f"📂 История — {member}")
        for r in rows:
            embed.add_field(
                name=f"{r['action'].upper()} #{r['id']}",
                value=f"**Мод:** <@{r['moderator_id']}>\n**Причина:** {r['reason']}\n**Когда:** {r['created_at']}",
                inline=False,
            )
        await i.response.send_message(embed=embed, ephemeral=True)

    @app_commands.command(name="clear", description="Очистить сообщения")
    @is_moderator()
    async def clear(self, i: discord.Interaction, amount: int = 10) -> None:
        if not 1 <= amount <= 100:
            await i.response.send_message(embed=error_embed("1–100."), ephemeral=True)
            return
        await i.response.defer(ephemeral=True)
        deleted = await i.channel.purge(limit=amount)  # type: ignore[union-attr]
        await i.followup.send(embed=success_embed(f"Удалено **{len(deleted)}**."), ephemeral=True)

    @app_commands.command(name="slowmode", description="Slowmode")
    @is_moderator()
    async def slowmode(self, i: discord.Interaction, seconds: int = 0) -> None:
        if not 0 <= seconds <= 21600:
            await i.response.send_message(embed=error_embed("0–21600."), ephemeral=True)
            return
        await i.channel.edit(slowmode_delay=seconds)  # type: ignore[union-attr]
        await i.response.send_message(embed=success_embed(f"Slowmode: **{seconds}**."))

    @app_commands.command(name="lock", description="Закрыть канал")
    @is_moderator()
    async def lock(self, i: discord.Interaction) -> None:
        ow = i.channel.overwrites_for(i.guild.default_role)  # type: ignore[union-attr]
        ow.send_messages = False
        await i.channel.set_permissions(i.guild.default_role, overwrite=ow)  # type: ignore[union-attr]
        await i.response.send_message(embed=success_embed("Закрыт."))

    @app_commands.command(name="unlock", description="Открыть канал")
    @is_moderator()
    async def unlock(self, i: discord.Interaction) -> None:
        ow = i.channel.overwrites_for(i.guild.default_role)  # type: ignore[union-attr]
        ow.send_messages = None
        await i.channel.set_permissions(i.guild.default_role, overwrite=ow)  # type: ignore[union-attr]
        await i.response.send_message(embed=success_embed("Открыт."))

    @app_commands.command(name="automod", description="Автомодерация")
    @is_admin()
    @app_commands.choices(option=[
        app_commands.Choice(name="bad_words", value="bad_words"),
        app_commands.Choice(name="spam", value="spam"),
        app_commands.Choice(name="invites", value="invites"),
        app_commands.Choice(name="mass_mentions", value="mass_mentions"),
    ])
    async def automod(self, i: discord.Interaction, option: str, enabled: bool) -> None:
        existing = await self.db.fetchone("SELECT * FROM automod_settings WHERE guild_id = ?", (i.guild.id,))
        if not existing:
            await self.db.execute("INSERT INTO automod_settings (guild_id) VALUES (?)", (i.guild.id,))
        await self.db.execute(f"UPDATE automod_settings SET {option} = ? WHERE guild_id = ?", (1 if enabled else 0, i.guild.id))
        await i.response.send_message(embed=success_embed(f"`{option}`: {'ON' if enabled else 'OFF'}"), ephemeral=True)

    @app_commands.command(name="addword", description="Добавить слово")
    @is_admin()
    async def addword(self, i: discord.Interaction, word: str) -> None:
        await self.db.add_bad_word(i.guild.id, word)
        await i.response.send_message(embed=success_embed(f"`{word}` добавлено."), ephemeral=True)

    @app_commands.command(name="removeword", description="Удалить слово")
    @is_admin()
    async def removeword(self, i: discord.Interaction, word: str) -> None:
        await self.db.remove_bad_word(i.guild.id, word)
        await i.response.send_message(embed=success_embed(f"`{word}` удалено."), ephemeral=True)

    @app_commands.command(name="listwords", description="Бан-слова")
    @is_admin()
    async def listwords(self, i: discord.Interaction) -> None:
        words = await self.db.get_bad_words(i.guild.id)
        if not words:
            await i.response.send_message(embed=error_embed("Пусто."), ephemeral=True)
            return
        await i.response.send_message(
            embed=base_embed(title="🚫 Бан-слова", description=", ".join(f"`{w}`" for w in words)), ephemeral=True
        )

    @commands.Cog.listener()
    async def on_message(self, message: discord.Message) -> None:
        if message.author.bot or not message.guild or message.author.guild_permissions.manage_messages:
            return
        st = await self.db.fetchone("SELECT * FROM automod_settings WHERE guild_id = ?", (message.guild.id,))
        if not st:
            return
        if st["spam"]:
            key = (message.guild.id, message.author.id)
            now = time.time()
            q = self._spam[key]
            q.append(now)
            if len(q) == 6 and q[-1] - q[0] < 5:
                try:
                    await message.author.timeout(discord.utils.utcnow() + timedelta(minutes=5), reason="Спам")
                    await message.channel.send(embed=warning_embed(f"{message.author.mention} — таймаут за спам."), delete_after=10)
                except discord.HTTPException:
                    pass
                return
        if st["bad_words"]:
            words = await self.db.get_bad_words(message.guild.id)
            if words and any(w in message.content.lower() for w in words):
                await message.delete()
                await message.channel.send(embed=warning_embed(f"{message.author.mention} — недопустимая лексика."), delete_after=5)
                return
        if st["invites"] and INVITE_RE.search(message.content):
            if not message.author.guild_permissions.manage_guild:
                await message.delete()
                await message.channel.send(embed=warning_embed(f"{message.author.mention} — реклама."), delete_after=5)
                return
        if st["mass_mentions"] and len(message.mentions) >= 5:
            await message.delete()
            try:
                await message.author.timeout(discord.utils.utcnow() + timedelta(minutes=10), reason="Mass mention")
            except discord.HTTPException:
                pass


async def setup(bot: commands.Bot) -> None:
    await bot.add_cog(Moderation(bot))

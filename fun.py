"""Экономика, уровни, магазин, мини-игры."""
from __future__ import annotations

import asyncio
import random
from datetime import datetime, timedelta, timezone

import discord
from discord import app_commands
from discord.ext import commands

from utils.embeds import base_embed, error_embed, success_embed

DAILY = 100
WORK_MIN, WORK_MAX = 20, 80
TRIVIA = [
    ("Столица Франции?", "париж"),
    ("Сколько будет 7 * 8?", "56"),
    ("Газ в атмосфере Земли?", "азот"),
]


class Fun(commands.Cog):
    def __init__(self, bot: commands.Bot) -> None:
        self.bot = bot
        self.db = bot.db  # type: ignore[attr-defined]

    @app_commands.command(name="balance", description="Баланс")
    async def balance(self, i: discord.Interaction, member: discord.Member | None = None) -> None:
        t = member or i.user
        await self.db.ensure_economy(i.guild.id, t.id)  # type: ignore[union-attr]
        e = await self.db.get_economy(i.guild.id, t.id)  # type: ignore[union-attr]
        l = await self.db.get_level(i.guild.id, t.id)  # type: ignore[union-attr]
        em = base_embed(title=f"💼 {t.display_name}")
        em.set_thumbnail(url=t.display_avatar.url)
        em.add_field(name="Баланс", value=f"💰 {e['balance']}")
        em.add_field(name="Банк", value=f"🏦 {e['bank']}")
        if l: em.add_field(name="Уровень", value=f"⭐ {l['level']} ({l['xp']} XP)")
        await i.response.send_message(embed=em)

    @app_commands.command(name="daily", description="Ежедневная награда")
    async def daily(self, i: discord.Interaction) -> None:
        await self.db.ensure_economy(i.guild.id, i.user.id)  # type: ignore[union-attr]
        e = await self.db.get_economy(i.guild.id, i.user.id)  # type: ignore[union-attr]
        now = datetime.now(timezone.utc).replace(tzinfo=None)
        last = e["last_daily"]
        if last and isinstance(last, str): last = datetime.fromisoformat(last)
        if last and (now - last) < timedelta(hours=22):
            left = timedelta(hours=22) - (now - last)
            await i.response.send_message(embed=error_embed(f"Через {str(left).split('.')[0]}"), ephemeral=True)
            return
        streak = (e["daily_streak"] or 0) + 1 if last and (now - last) < timedelta(hours=48) else 1
        amt = DAILY + streak * 10
        await self.db.add_money(i.guild.id, i.user.id, amt)  # type: ignore[union-attr]
        await self.db.update_economy(i.guild.id, i.user.id, daily_streak=streak, last_daily=now)  # type: ignore[union-attr]
        await i.response.send_message(embed=success_embed(f"💰 +**{amt}** (стрик {streak})"))

    @app_commands.command(name="work", description="Поработать")
    async def work(self, i: discord.Interaction) -> None:
        await self.db.ensure_economy(i.guild.id, i.user.id)  # type: ignore[union-attr]
        e = await self.db.get_economy(i.guild.id, i.user.id)  # type: ignore[union-attr]
        now = datetime.now(timezone.utc).replace(tzinfo=None)
        last = e["last_work"]
        if last and isinstance(last, str): last = datetime.fromisoformat(last)
        if last and (now - last) < timedelta(hours=4):
            left = timedelta(hours=4) - (now - last)
            await i.response.send_message(embed=error_embed(f"Отдых: {str(left).split('.')[0]}"), ephemeral=True)
            return
        amt = random.randint(WORK_MIN, WORK_MAX)
        await self.db.add_money(i.guild.id, i.user.id, amt)  # type: ignore[union-attr]
        await self.db.update_economy(i.guild.id, i.user.id, last_work=now)  # type: ignore[union-attr]
        await i.response.send_message(embed=success_embed(f"Поработал: +**{amt}**"))

    @app_commands.command(name="pay", description="Перевести")
    async def pay(self, i: discord.Interaction, member: discord.Member, amount: int) -> None:
        if amount < 1 or member.bot or member.id == i.user.id:
            await i.response.send_message(embed=error_embed("Некорректно."), ephemeral=True)
            return
        await self.db.ensure_economy(i.guild.id, i.user.id)  # type: ignore[union-attr]
        e = await self.db.get_economy(i.guild.id, i.user.id)  # type: ignore[union-attr]
        if e["balance"] < amount:
            await i.response.send_message(embed=error_embed("Недостаточно."), ephemeral=True)
            return
        await self.db.add_money(i.guild.id, i.user.id, -amount)  # type: ignore[union-attr]
        await self.db.add_money(i.guild.id, member.id, amount)  # type: ignore[union-attr]
        await i.response.send_message(embed=success_embed(f"💸 {amount} → {member.mention}"))

    @app_commands.command(name="deposit", description="В банк")
    async def deposit(self, i: discord.Interaction, amount: int) -> None:
        await self.db.ensure_economy(i.guild.id, i.user.id)  # type: ignore[union-attr]
        e = await self.db.get_economy(i.guild.id, i.user.id)  # type: ignore[union-attr]
        if amount < 1 or e["balance"] < amount:
            await i.response.send_message(embed=error_embed("Недостаточно."), ephemeral=True)
            return
        await self.db.execute(
            "UPDATE economy SET balance = balance - ?, bank = bank + ? WHERE guild_id = ? AND user_id = ?",
            (amount, amount, i.guild.id, i.user.id),  # type: ignore[union-attr]
        )
        await i.response.send_message(embed=success_embed(f"🏦 +{amount}"))

    @app_commands.command(name="withdraw", description="Из банка")
    async def withdraw(self, i: discord.Interaction, amount: int) -> None:
        await self.db.ensure_economy(i.guild.id, i.user.id)  # type: ignore[union-attr]
        e = await self.db.get_economy(i.guild.id, i.user.id)  # type: ignore[union-attr]
        if amount < 1 or e["bank"] < amount:
            await i.response.send_message(embed=error_embed("В банке мало."), ephemeral=True)
            return
        await self.db.execute(
            "UPDATE economy SET balance = balance + ?, bank = bank - ? WHERE guild_id = ? AND user_id = ?",
            (amount, amount, i.guild.id, i.user.id),  # type: ignore[union-attr]
        )
        await i.response.send_message(embed=success_embed(f"💰 -{amount}"))

    @app_commands.command(name="leaderboard", description="Топ богачей")
    async def leaderboard(self, i: discord.Interaction) -> None:
        rows = await self.db.fetchall(
            "SELECT user_id, balance FROM economy WHERE guild_id = ? ORDER BY balance DESC LIMIT 10",
            (i.guild.id,),  # type: ignore[union-attr]
        )
        if not rows:
            await i.response.send_message(embed=error_embed("Пусто."), ephemeral=True)
            return
        e = base_embed(title="🏆 Топ")
        for idx, r in enumerate(rows, 1):
            e.add_field(name=f"{idx}. <@{r['user_id']}>", value=f"💰 {r['balance']}", inline=False)
        await i.response.send_message(embed=e)

    @commands.Cog.listener()
    async def on_message(self, m: discord.Message) -> None:
        if m.author.bot or not m.guild or m.content.startswith("!"):
            return
        _, lvl, lvled = await self.db.add_xp(m.guild.id, m.author.id, random.randint(5, 15))
        if lvled:
            try:
                await m.channel.send(f"🎉 {m.author.mention} достиг **{lvl}** уровня!", delete_after=15)
            except discord.HTTPException:
                pass

    @app_commands.command(name="rank", description="Ранг")
    async def rank(self, i: discord.Interaction, member: discord.Member | None = None) -> None:
        t = member or i.user
        row = await self.db.get_level(i.guild.id, t.id)  # type: ignore[union-attr]
        if not row:
            await i.response.send_message(embed=error_embed("Нет данных."), ephemeral=True)
            return
        e = base_embed(title=f"⭐ {t.display_name}")
        e.set_thumbnail(url=t.display_avatar.url)
        e.add_field(name="Уровень", value=str(row["level"]))
        e.add_field(name="XP", value=str(row["xp"]))
        e.add_field(name="Сообщений", value=str(row["messages"]))
        await i.response.send_message(embed=e)

    @app_commands.command(name="shop", description="Магазин ролей")
    async def shop(self, i: discord.Interaction) -> None:
        rows = await self.db.fetchall("SELECT * FROM shop_items WHERE guild_id = ?", (i.guild.id,))  # type: ignore[union-attr]
        if not rows:
            await i.response.send_message(embed=error_embed("Пусто."), ephemeral=True)
            return
        e = base_embed(title="🛒 Магазин")
        for r in rows:
            e.add_field(name=f"#{r['id']} {r['name']}", value=f"💰 {r['price']}", inline=False)
        await i.response.send_message(embed=e)

    @app_commands.command(name="addshop", description="Добавить товар")
    @app_commands.default_permissions(administrator=True)
    async def addshop(self, i: discord.Interaction, role: discord.Role, price: int, name: str = "") -> None:
        await self.db.execute(
            "INSERT INTO shop_items (guild_id, role_id, name, price) VALUES (?, ?, ?, ?)",
            (i.guild.id, role.id, name or role.name, price),  # type: ignore[union-attr]
        )
        await i.response.send_message(embed=success_embed("Добавлено."), ephemeral=True)

    @app_commands.command(name="buy", description="Купить")
    async def buy(self, i: discord.Interaction, item_id: int) -> None:
        item = await self.db.fetchone("SELECT * FROM shop_items WHERE id = ? AND guild_id = ?", (item_id, i.guild.id))  # type: ignore[union-attr]
        if not item:
            await i.response.send_message(embed=error_embed("Нет товара."), ephemeral=True)
            return
        await self.db.ensure_economy(i.guild.id, i.user.id)  # type: ignore[union-attr]
        e = await self.db.get_economy(i.guild.id, i.user.id)  # type: ignore[union-attr]
        if e["balance"] < item["price"]:
            await i.response.send_message(embed=error_embed("Недостаточно."), ephemeral=True)
            return
        role = i.guild.get_role(item["role_id"])  # type: ignore[union-attr]
        if not role:
            await i.response.send_message(embed=error_embed("Роль удалена."), ephemeral=True)
            return
        try:
            await i.user.add_roles(role, reason="Покупка")  # type: ignore[union-attr]
        except discord.Forbidden:
            await i.response.send_message(embed=error_embed("Нет прав."), ephemeral=True)
            return
        await self.db.add_money(i.guild.id, i.user.id, -item["price"])  # type: ignore[union-attr]
        await i.response.send_message(embed=success_embed(f"Куплено: {item['name']}"))

    @app_commands.command(name="8ball", description="Магический шар")
    async def eb(self, i: discord.Interaction, question: str) -> None:
        ans = ["Да", "Нет", "Возможно", "Определённо", "Сомнительно", "Спроси позже"]
        await i.response.send_message(embed=base_embed(title="🎱", description=f"**{question}**\n→ {random.choice(ans)}"))

    @app_commands.command(name="coinflip", description="Монетка")
    async def cf(self, i: discord.Interaction) -> None:
        await i.response.send_message(embed=base_embed(title="Монетка", description=random.choice(["🪙 Орёл", "🪙 Решка"])))

    @app_commands.command(name="dice", description="Кубик")
    async def dice(self, i: discord.Interaction, sides: int = 6) -> None:
        sides = max(2, min(100, sides))
        await i.response.send_message(embed=base_embed(title=f"🎲 d{sides}", description=f"**{random.randint(1, sides)}**"))

    @app_commands.command(name="trivia", description="Викторина")
    async def trivia(self, i: discord.Interaction) -> None:
        q, a = random.choice(TRIVIA)
        await i.response.send_message(embed=base_embed(title="🧠", description=q))
        try:
            m = await self.bot.wait_for("message", timeout=30,
                check=lambda x: x.author == i.user and x.channel == i.channel)
        except asyncio.TimeoutError:
            return
        if m.content.strip().lower() == a:
            await m.reply(embed=success_embed("Правильно! +50"))
            await self.db.add_money(i.guild.id, i.user.id, 50)  # type: ignore[union-attr]
        else:
            await m.reply(embed=error_embed(f"Ответ: **{a}**"))


async def setup(bot: commands.Bot) -> None:
    await bot.add_cog(Fun(bot))

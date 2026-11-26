"""build_cogs_a.py — наполняет первые 6 когов ServerBuilder.

Запуск: python build_cogs_a.py
После — build_cogs_b.py (остальные 8).
"""
from __future__ import annotations

from pathlib import Path

BASE = Path(__file__).resolve().parent
COGS = BASE / "cogs"
COGS.mkdir(exist_ok=True)


def write(name: str, content: str) -> None:
    path = COGS / name
    path.write_text(content, encoding="utf-8")
    print(f"[ok] cogs/{name}  ({len(content)} байт)")


# ─────────────────────────────────────────────────────────
# 1. WIZARD
# ─────────────────────────────────────────────────────────
WIZARD = r'''"""Мастер создания сервера."""
from __future__ import annotations

import logging

import discord
from discord import app_commands
from discord.ext import commands

from utils.checks import is_admin
from utils.embeds import base_embed, error_embed, success_embed

log = logging.getLogger(__name__)

SERVER_TYPES: dict[str, dict] = {
    "gaming": {
        "name": "🎮 Гейминг",
        "categories": [
            ("📢 Информация", [("📜-правила", "text"), ("📣-объявления", "text"), ("👋-приветствие", "text")]),
            ("🎮 Игровая", [("💬-общий", "text"), ("🎯-поиск-тимы", "text"), ("🏆-ачивки", "text"), ("🔊 Общий войс", "voice"), ("➕ Создать комнату", "voice")]),
            ("🎧 Приватки", []),
        ],
        "roles": [("🎮 Игрок", 0x5865F2), ("🎯 Активный", 0x57F287), ("👑 Админ", 0xED4245)],
    },
    "community": {
        "name": "💬 Сообщество",
        "categories": [
            ("📢 Информация", [("📜-правила", "text"), ("📣-объявления", "text"), ("👋-приветствие", "text")]),
            ("💬 Общение", [("💬-общий", "text"), ("🎲-флуд", "text"), ("🖼-медиа", "text"), ("🔊 Голосовой", "voice")]),
            ("🎫 Поддержка", [("🎫-тикеты", "text")]),
        ],
        "roles": [("👤 Участник", 0x99AAB5), ("⭐ Активный", 0xFEE75C), ("🛡 Модератор", 0x3498DB), ("👑 Админ", 0xED4245)],
    },
    "study": {
        "name": "📚 Учёба",
        "categories": [
            ("📚 Информация", [("📜-правила", "text"), ("📅-расписание", "text")]),
            ("✏️ Учёба", [("💬-общий", "text"), ("❓-вопросы", "text"), ("📝-конспекты", "text"), ("🔊 Совместная учёба", "voice")]),
        ],
        "roles": [("🎓 Студент", 0x3498DB), ("📖 Отличник", 0x57F287), ("👑 Админ", 0xED4245)],
    },
    "business": {
        "name": "💼 Бизнес",
        "categories": [
            ("💼 Информация", [("📜-правила", "text"), ("📣-новости", "text")]),
            ("🏢 Офис", [("💼-общий", "text"), ("📊-проекты", "text"), ("🔊 Переговорная", "voice")]),
            ("🎫 Клиенты", [("🎫-заявки", "text")]),
        ],
        "roles": [("👔 Сотрудник", 0x2ECC71), ("💎 Клиент", 0x9B59B6), ("👑 Админ", 0xED4245)],
    },
    "creative": {
        "name": "🎨 Творчество",
        "categories": [
            ("📢 Информация", [("📜-правила", "text"), ("📣-объявления", "text")]),
            ("🎨 Творчество", [("💬-общий", "text"), ("🖼-галерея", "text"), ("🎵-музыка", "text"), ("🔊 Голосовой", "voice")]),
        ],
        "roles": [("🎨 Художник", 0xE91E63), ("🎵 Музыкант", 0x9C27B0), ("👑 Админ", 0xED4245)],
    },
}

FEATURES: dict[str, str] = {
    "verify": "🔐 Верификация",
    "tickets": "🎫 Тикеты",
    "rules": "📜 Правила",
    "automod": "🛡 Автомод",
    "autorole": "🎭 Автороль",
    "welcome": "👋 Приветствие",
    "economy": "💰 Экономика",
    "antiraid": "🚨 Анти-рейд",
}


class Session:
    def __init__(self) -> None:
        self.server_type: str | None = None
        self.features: set[str] = set()
        self.created: list[str] = []


class TypeSelect(discord.ui.Select):
    def __init__(self, s: Session) -> None:
        self.s = s
        super().__init__(
            placeholder="1) Тип сервера",
            options=[discord.SelectOption(label=v["name"], value=k) for k, v in SERVER_TYPES.items()],
        )

    async def callback(self, i: discord.Interaction) -> None:
        self.s.server_type = self.values[0]
        v = discord.ui.View(timeout=300)
        v.add_item(FeatSelect(self.s))
        v.add_item(CreateBtn(self.s, i.client))
        await i.response.edit_message(
            embed=base_embed(
                title="Шаг 2 из 3",
                description=f"Тип: **{SERVER_TYPES[self.s.server_type]['name']}**\nВыберите фичи и нажмите Создать.",
            ),
            view=v,
        )


class FeatSelect(discord.ui.Select):
    def __init__(self, s: Session) -> None:
        self.s = s
        super().__init__(
            placeholder="2) Фичи",
            min_values=0, max_values=len(FEATURES),
            options=[discord.SelectOption(label=v, value=k) for k, v in FEATURES.items()],
        )

    async def callback(self, i: discord.Interaction) -> None:
        self.s.features = set(self.values)
        chosen = "\n".join(f"✅ {FEATURES[k]}" for k in self.values) or "_пусто_"
        await i.response.edit_message(
            embed=base_embed(
                title="Шаг 2 из 3",
                description=f"Тип: **{SERVER_TYPES[self.s.server_type]['name']}**\nФичи:\n{chosen}",
            ),
            view=self.view,
        )


class CreateBtn(discord.ui.Button):
    def __init__(self, s: Session, bot: commands.Bot) -> None:
        super().__init__(label="Создать", style=discord.ButtonStyle.success)
        self.s = s
        self.bot = bot

    async def callback(self, i: discord.Interaction) -> None:
        if not self.s.server_type:
            await i.response.send_message(embed=error_embed("Выберите тип."), ephemeral=True)
            return
        await i.response.edit_message(embed=base_embed(title="Создаю..."), view=None)
        g = i.guild
        s = self.s
        tpl = SERVER_TYPES[s.server_type]

        role_map: dict[str, discord.Role] = {}
        for name, color in tpl["roles"]:
            try:
                role_map[name] = await g.create_role(name=name, color=discord.Color(color), reason="Wizard")
                s.created.append(f"🎭 {name}")
            except discord.HTTPException:
                pass

        for cat_name, channels in tpl["categories"]:
            try:
                cat = await g.create_category(cat_name)
            except discord.HTTPException:
                continue
            for ch_name, ch_type in channels:
                try:
                    if ch_type == "text":
                        await cat.create_text_channel(ch_name)
                    else:
                        await cat.create_voice_channel(ch_name)
                except discord.HTTPException:
                    pass

        admin_role = role_map.get("👑 Админ")

        if "welcome" in s.features:
            w_ch = discord.utils.get(g.text_channels, name="👋-приветствие")
            if w_ch:
                await self.bot.db.execute("INSERT OR IGNORE INTO welcome_settings (guild_id) VALUES (?)", (g.id,))
                await self.bot.db.execute("UPDATE welcome_settings SET welcome_channel_id = ? WHERE guild_id = ?", (w_ch.id, g.id))
                s.created.append("👋 Приветствие")

        if "automod" in s.features:
            await self.bot.db.execute(
                "INSERT OR IGNORE INTO automod_settings (guild_id, bad_words, spam, invites, mass_mentions) VALUES (?, 1, 1, 1, 1)",
                (g.id,),
            )
            s.created.append("🛡 Автомод")

        if "antiraid" in s.features:
            await self.bot.db.set_antiraid(g.id, enabled=1, join_threshold=10, time_window=60, action="lockdown")
            s.created.append("🚨 Анти-рейд")

        if "autorole" in s.features:
            member_role = discord.utils.get(g.roles, name="👤 Участник") or discord.utils.get(g.roles, name="🎮 Игрок")
            if member_role:
                await self.bot.db.execute("INSERT OR IGNORE INTO welcome_settings (guild_id) VALUES (?)", (g.id,))
                await self.bot.db.execute("UPDATE welcome_settings SET autorole_id = ? WHERE guild_id = ?", (member_role.id, g.id))
                s.created.append(f"🎭 Автороль → {member_role.name}")

        if "verify" in s.features:
            verify_role = await g.create_role(name="✅ Верифицирован", color=discord.Color.green())
            info_cat = discord.utils.get(g.categories, name="📢 Информация")
            verify_ch = await g.create_text_channel("✅-верификация", category=info_cat)
            try:
                from cogs.welcome import VerifyView
                await verify_ch.send(embed=base_embed(title="🔐 Верификация", description="Нажмите кнопку ниже."), view=VerifyView())
            except Exception:
                log.exception("Verify panel")
            await self.bot.db.execute("INSERT OR IGNORE INTO welcome_settings (guild_id) VALUES (?)", (g.id,))
            await self.bot.db.execute("UPDATE welcome_settings SET verify_role_id = ? WHERE guild_id = ?", (verify_role.id, g.id))
            s.created.append("🔐 Верификация")

        if "rules" in s.features and admin_role:
            rules_ch = discord.utils.get(g.text_channels, name="📜-правила")
            if rules_ch:
                try:
                    from cogs.community import RulesView
                    embed = base_embed(
                        title="📜 Правила",
                        description="1. Уважайте друг друга\n2. Без спама\n3. Без NSFW\n4. Слушайте модераторов\n\nНажмите кнопку ниже.",
                    )
                    msg = await rules_ch.send(embed=embed, view=RulesView(g.id))
                    await self.bot.db.set_rules(g.id, rules_ch.id, msg.id, admin_role.id, "Стандартные")
                    s.created.append("📜 Правила")
                except Exception:
                    log.exception("Rules")

        if "tickets" in s.features:
            tickets_ch = discord.utils.get(g.text_channels, name="🎫-тикеты")
            support_role = discord.utils.get(g.roles, name="🛡 Модератор") or admin_role
            if tickets_ch and support_role and admin_role:
                try:
                    from cogs.tickets import TicketPanelView
                    await tickets_ch.send(
                        embed=base_embed(title="🎫 Поддержка", description="Нажмите кнопку."),
                        view=TicketPanelView(),
                    )
                    cat = discord.utils.get(g.categories, name="🎫 Поддержка")
                    if not cat:
                        cat = await g.create_category("🎫 Тикеты")
                    await self.bot.db.execute(
                        "INSERT OR REPLACE INTO ticket_settings (guild_id, panel_channel_id, category_id, support_role_id, log_channel_id) VALUES (?, ?, ?, ?, ?)",
                        (g.id, tickets_ch.id, cat.id, support_role.id, tickets_ch.id),
                    )
                    s.created.append("🎫 Тикеты")
                except Exception:
                    log.exception("Tickets")

        if "economy" in s.features:
            await self.bot.db.ensure_economy(g.id, i.user.id)
            s.created.append("💰 Экономика")

        summary = "\n".join(s.created[-30:]) if s.created else "_ничего_"
        await i.edit_original_response(
            embed=success_embed(
                f"Сервер **{g.name}** готов!\n\n**Создано:**\n{summary}\n\nДальше: `/health`, `/room setup`"
            ),
        )


class Wizard(commands.Cog):
    def __init__(self, bot: commands.Bot) -> None:
        self.bot = bot

    @app_commands.command(name="start", description="Мастер создания сервера с нуля за 30 секунд")
    @is_admin()
    async def start(self, i: discord.Interaction) -> None:
        s = Session()
        v = discord.ui.View(timeout=300)
        v.add_item(TypeSelect(s))
        await i.response.send_message(
            embed=base_embed(title="Мастер — шаг 1 из 3", description="Выберите тип сервера."),
            view=v, ephemeral=True,
        )


async def setup(bot: commands.Bot) -> None:
    await bot.add_cog(Wizard(bot))
'''

# ─────────────────────────────────────────────────────────
# 2. HEALTH
# ─────────────────────────────────────────────────────────
HEALTH = r'''"""Аудит сервера."""
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
'''

# ─────────────────────────────────────────────────────────
# 3. ANTIRAID
# ─────────────────────────────────────────────────────────
ANTIRAID = r'''"""Анти-рейд."""
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
'''

# ─────────────────────────────────────────────────────────
# 4. COMMUNITY
# ─────────────────────────────────────────────────────────
COMMUNITY = r'''"""Правила и предложения."""
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
'''

# ─────────────────────────────────────────────────────────
# 5. MODERATION
# ─────────────────────────────────────────────────────────
MODERATION = r'''"""Модерация."""
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
'''

# ─────────────────────────────────────────────────────────
# 6. WELCOME
# ─────────────────────────────────────────────────────────
WELCOME = r'''"""Приветствие и верификация."""
from __future__ import annotations

import io
import logging
from typing import Optional

import aiohttp
import discord
from discord import app_commands
from discord.ext import commands
from PIL import Image, ImageDraw, ImageFont, ImageOps

from config import BASE_DIR, PANEL_VERIFY
from utils.checks import is_admin
from utils.embeds import base_embed, error_embed, success_embed

log = logging.getLogger(__name__)
FONT_PATH = BASE_DIR / "assets" / "font.ttf"


class VerifyView(discord.ui.View):
    def __init__(self) -> None:
        super().__init__(timeout=None)

    @discord.ui.button(label="Подтвердить", style=discord.ButtonStyle.success, custom_id=PANEL_VERIFY)
    async def verify(self, i: discord.Interaction, _: discord.ui.Button) -> None:
        db = i.client.db  # type: ignore[attr-defined]
        row = await db.fetchone("SELECT verify_role_id FROM welcome_settings WHERE guild_id = ?", (i.guild.id,))  # type: ignore[union-attr]
        if not row or not row["verify_role_id"]:
            await i.response.send_message(embed=error_embed("Не настроено."), ephemeral=True)
            return
        role = i.guild.get_role(row["verify_role_id"])  # type: ignore[union-attr]
        if not role:
            await i.response.send_message(embed=error_embed("Роль удалена."), ephemeral=True)
            return
        try:
            await i.user.add_roles(role, reason="Верификация")  # type: ignore[union-attr]
            await i.response.send_message(embed=success_embed("Верифицированы!"), ephemeral=True)
        except discord.Forbidden:
            await i.response.send_message(embed=error_embed("Нет прав."), ephemeral=True)


class Welcome(commands.Cog):
    def __init__(self, bot: commands.Bot) -> None:
        self.bot = bot
        self.db = bot.db  # type: ignore[attr-defined]

    async def cog_load(self) -> None:
        self.bot.add_view(VerifyView())

    async def _settings(self, gid: int):
        row = await self.db.fetchone("SELECT * FROM welcome_settings WHERE guild_id = ?", (gid,))
        if not row:
            await self.db.execute("INSERT INTO welcome_settings (guild_id) VALUES (?)", (gid,))
            row = await self.db.fetchone("SELECT * FROM welcome_settings WHERE guild_id = ?", (gid,))
        return row

    async def _image(self, member: discord.Member) -> Optional[discord.File]:
        try:
            size = (800, 300)
            s = await self._settings(member.guild.id)
            bg_url = s["background_url"] if s else None
            bg: Image.Image
            if bg_url:
                try:
                    async with aiohttp.ClientSession() as sess:
                        async with sess.get(bg_url, timeout=aiohttp.ClientTimeout(total=5)) as resp:
                            if resp.status == 200:
                                data = await resp.read()
                                bg = ImageOps.fit(Image.open(io.BytesIO(data)).convert("RGB"), size)
                            else:
                                bg = Image.new("RGB", size, (40, 44, 90))
                except Exception:
                    bg = Image.new("RGB", size, (40, 44, 90))
            else:
                bg = Image.new("RGB", size, (40, 44, 90))
            draw = ImageDraw.Draw(bg)
            ab = await member.display_avatar.with_size(256).read()
            av = ImageOps.fit(Image.open(io.BytesIO(ab)).convert("RGBA"), (200, 200))
            mask = Image.new("L", (200, 200), 0)
            ImageDraw.Draw(mask).ellipse((0, 0, 200, 200), fill=255)
            bg.paste(av, (50, 50), mask)
            fb = fs = None
            try:
                if FONT_PATH.exists():
                    fb = ImageFont.truetype(str(FONT_PATH), 44)
                    fs = ImageFont.truetype(str(FONT_PATH), 28)
            except OSError:
                pass
            if not fb:
                for name in ("arial.ttf", "DejaVuSans.ttf", "Roboto-Regular.ttf", "LiberationSans-Regular.ttf"):
                    try:
                        fb = ImageFont.truetype(name, 44); fs = ImageFont.truetype(name, 28); break
                    except OSError:
                        continue
            if not fb:
                fb = fs = ImageFont.load_default()
            draw.text((300, 100), f"Welcome, {member.name}!"[:25], fill=(255, 255, 255), font=fb)
            draw.text((300, 170), f"Member #{member.guild.member_count}", fill=(200, 200, 220), font=fs)
            buf = io.BytesIO()
            bg.save(buf, format="PNG")
            buf.seek(0)
            return discord.File(buf, filename="welcome.png")
        except Exception:
            log.exception("Welcome image")
            return None

    @commands.Cog.listener()
    async def on_member_join(self, member: discord.Member) -> None:
        s = await self._settings(member.guild.id)
        if s["autorole_id"]:
            role = member.guild.get_role(s["autorole_id"])
            if role:
                try:
                    await member.add_roles(role, reason="Autorole")
                except discord.Forbidden:
                    pass
        if s["welcome_channel_id"]:
            ch = member.guild.get_channel(s["welcome_channel_id"])
            if isinstance(ch, discord.TextChannel):
                text = (s["welcome_text"] or "Добро пожаловать, {user}!").format(
                    user=member.mention, name=member.name, server=member.guild.name
                )
                embed = base_embed(title="👋 Новый участник", description=text)
                embed.set_thumbnail(url=member.display_avatar.url)
                try:
                    f = await self._image(member)
                    if f:
                        embed.set_image(url="attachment://welcome.png")
                        await ch.send(content=member.mention, embed=embed, file=f)
                    else:
                        await ch.send(content=member.mention, embed=embed)
                except discord.HTTPException:
                    pass

    @commands.Cog.listener()
    async def on_member_remove(self, member: discord.Member) -> None:
        s = await self._settings(member.guild.id)
        if s["goodbye_channel_id"]:
            ch = member.guild.get_channel(s["goodbye_channel_id"])
            if isinstance(ch, discord.TextChannel):
                text = (s["goodbye_text"] or "Пока, {user}...").format(name=member.name)
                try:
                    await ch.send(embed=base_embed(title="👋 Ушёл", description=text))
                except discord.HTTPException:
                    pass

    @app_commands.command(name="setwelcome", description="Настроить приветствие")
    @is_admin()
    async def setwelcome(self, i: discord.Interaction, channel: discord.TextChannel, text: str = "") -> None:
        await self._settings(i.guild.id)  # type: ignore[union-attr]
        await self.db.execute("UPDATE welcome_settings SET welcome_channel_id = ? WHERE guild_id = ?", (channel.id, i.guild.id))
        if text:
            await self.db.execute("UPDATE welcome_settings SET welcome_text = ? WHERE guild_id = ?", (text, i.guild.id))
        await i.response.send_message(embed=success_embed(f"→ {channel.mention}"), ephemeral=True)

    @app_commands.command(name="setgoodbye", description="Настроить прощание")
    @is_admin()
    async def setgoodbye(self, i: discord.Interaction, channel: discord.TextChannel, text: str = "") -> None:
        await self._settings(i.guild.id)  # type: ignore[union-attr]
        await self.db.execute("UPDATE welcome_settings SET goodbye_channel_id = ? WHERE guild_id = ?", (channel.id, i.guild.id))
        if text:
            await self.db.execute("UPDATE welcome_settings SET goodbye_text = ? WHERE guild_id = ?", (text, i.guild.id))
        await i.response.send_message(embed=success_embed(f"→ {channel.mention}"), ephemeral=True)

    @app_commands.command(name="setautorole", description="Автороль")
    @is_admin()
    async def setautorole(self, i: discord.Interaction, role: discord.Role) -> None:
        await self._settings(i.guild.id)  # type: ignore[union-attr]
        await self.db.execute("UPDATE welcome_settings SET autorole_id = ? WHERE guild_id = ?", (role.id, i.guild.id))
        await i.response.send_message(embed=success_embed(f"→ {role.mention}"), ephemeral=True)

    @app_commands.command(name="setwelcome-bg", description="Фон приветствия")
    @is_admin()
    async def set_bg(self, i: discord.Interaction, url: str = "") -> None:
        await self._settings(i.guild.id)  # type: ignore[union-attr]
        await self.db.execute("UPDATE welcome_settings SET background_url = ? WHERE guild_id = ?", (url or None, i.guild.id))
        await i.response.send_message(embed=success_embed("Сброшен." if not url else f"Фон: <{url}>"), ephemeral=True)

    @app_commands.command(name="setup-verify", description="Панель верификации")
    @is_admin()
    async def setup_verify(self, i: discord.Interaction, role: discord.Role) -> None:
        await self._settings(i.guild.id)  # type: ignore[union-attr]
        await self.db.execute("UPDATE welcome_settings SET verify_role_id = ? WHERE guild_id = ?", (role.id, i.guild.id))
        embed = base_embed(title="🔐 Верификация", description="Нажмите кнопку ниже.")
        await i.channel.send(embed=embed, view=VerifyView())  # type: ignore[union-attr]
        await i.response.send_message(embed=success_embed("Панель создана."), ephemeral=True)


async def setup(bot: commands.Bot) -> None:
    await bot.add_cog(Welcome(bot))
'''


def main() -> None:
    print(f"Project: {BASE}\n")
    print("Пишу 6 когов (часть A):\n")
    write("wizard.py", WIZARD)
    write("health.py", HEALTH)
    write("antiraid.py", ANTIRAID)
    write("community.py", COMMUNITY)
    write("moderation.py", MODERATION)
    write("welcome.py", WELCOME)
    print("\n" + "=" * 50)
    print("OK. 6 когов готовы.")
    print("Дальше: python build_cogs_b.py (ещё 8 когов)")
    print("=" * 50)


if __name__ == "__main__":
    main()
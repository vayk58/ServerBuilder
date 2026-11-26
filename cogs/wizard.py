"""Мастер создания сервера."""
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

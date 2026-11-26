"""build_cogs_b.py — наполняет оставшиеся 8 когов ServerBuilder.

Запуск: python build_cogs_b.py
После этого бот готов к запуску.
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
# UTILITY
# ─────────────────────────────────────────────────────────
UTILITY = r'''"""Утилиты и информация."""
from __future__ import annotations

import json

import discord
from discord import app_commands
from discord.ext import commands

from utils.checks import is_admin, is_moderator
from utils.embeds import base_embed, error_embed, success_embed


class EmbedModal(discord.ui.Modal, title="Конструктор embed"):
    t = discord.ui.TextInput(label="Заголовок", max_length=256, required=False)
    d = discord.ui.TextInput(label="Описание", style=discord.TextStyle.paragraph, max_length=4000)
    c = discord.ui.TextInput(label="Цвет (#5865F2)", max_length=7, required=False)
    img = discord.ui.TextInput(label="URL картинки", required=False)
    ft = discord.ui.TextInput(label="Footer", max_length=2048, required=False)

    def __init__(self, ch) -> None:
        super().__init__()
        self.ch = ch

    async def on_submit(self, i: discord.Interaction) -> None:
        color = 0x5865F2
        if self.c.value.strip():
            try:
                color = int(self.c.value.strip().lstrip("#"), 16)
            except ValueError:
                await i.response.send_message(embed=error_embed("HEX неверный."), ephemeral=True)
                return
        e = discord.Embed(title=self.t.value or None, description=self.d.value, color=color)
        if self.img.value.strip():
            e.set_image(url=self.img.value.strip())
        if self.ft.value.strip():
            e.set_footer(text=self.ft.value)
        try:
            await self.ch.send(embed=e)
            await i.response.send_message(embed=success_embed(f"→ {self.ch.mention}"), ephemeral=True)
        except discord.HTTPException:
            await i.response.send_message(embed=error_embed("Не удалось."), ephemeral=True)


class PollView(discord.ui.View):
    def __init__(self, mid: int, q: str, opts: list[str]) -> None:
        super().__init__(timeout=None)
        self.mid = mid
        self.q = q
        self.opts = opts
        for idx, opt in enumerate(opts):
            b = discord.ui.Button(
                label=f"{idx + 1}. {opt}"[:80], style=discord.ButtonStyle.secondary,
                custom_id=f"sb:poll:{mid}:{idx}", row=idx // 5,
            )
            b.callback = self._cb(idx)
            self.add_item(b)

    def _cb(self, idx: int):
        async def cb(i: discord.Interaction) -> None:
            db = i.client.db  # type: ignore[attr-defined]
            await db.vote_poll(self.mid, i.user.id, idx)
            votes = await db.get_poll_votes(self.mid)
            await i.response.edit_message(embed=self._embed(votes))
        return cb

    def _embed(self, votes: dict[int, list[int]]) -> discord.Embed:
        total = sum(len(v) for v in votes.values()) or 1
        lines = []
        for i2, opt in enumerate(self.opts):
            cnt = len(votes.get(i2, []))
            pct = round(cnt / total * 100)
            bar = "█" * (pct // 10) + "░" * (10 - pct // 10)
            lines.append(f"**{i2 + 1}. {opt}**\n`{bar}` {pct}% ({cnt})")
        return base_embed(title=f"📊 {self.q}", description="\n\n".join(lines))


class Utility(commands.Cog):
    def __init__(self, bot: commands.Bot) -> None:
        self.bot = bot
        self.db = bot.db  # type: ignore[attr-defined]

    async def cog_load(self) -> None:
        for r in await self.db.get_all_polls():
            try:
                opts = json.loads(r["options"])
            except Exception:
                continue
            self.bot.add_view(PollView(r["message_id"], r["question"], opts), message_id=r["message_id"])

    @app_commands.command(name="serverinfo", description="Информация о сервере")
    async def serverinfo(self, i: discord.Interaction) -> None:
        g = i.guild
        humans = sum(1 for m in g.members if not m.bot)  # type: ignore[union-attr]
        e = base_embed(title=f"📊 {g.name}")  # type: ignore[union-attr]
        if g.icon:  # type: ignore[union-attr]
            e.set_thumbnail(url=g.icon.url)  # type: ignore[union-attr]
        e.add_field(name="ID", value=str(g.id), inline=True)  # type: ignore[union-attr]
        e.add_field(name="Владелец", value=g.owner.mention if g.owner else "—", inline=True)  # type: ignore[union-attr]
        e.add_field(name="Создан", value=g.created_at.strftime("%d.%m.%Y"), inline=True)  # type: ignore[union-attr]
        e.add_field(name="Участники", value=f"👤 {humans} / 🤖 {g.member_count - humans}", inline=True)  # type: ignore[union-attr]
        e.add_field(name="Каналы", value=f"💬 {len(g.text_channels)} / 🔊 {len(g.voice_channels)}", inline=True)  # type: ignore[union-attr]
        e.add_field(name="Роли", value=str(len(g.roles)), inline=True)  # type: ignore[union-attr]
        e.add_field(name="Бусты", value=f"✨ {g.premium_subscription_count} (ур.{g.premium_tier})", inline=True)  # type: ignore[union-attr]
        await i.response.send_message(embed=e)

    @app_commands.command(name="userinfo", description="Информация о пользователе")
    async def userinfo(self, i: discord.Interaction, member: discord.Member | None = None) -> None:
        m = member or i.user
        e = base_embed(title=f"👤 {m}")
        e.set_thumbnail(url=m.display_avatar.url)
        e.add_field(name="ID", value=str(m.id), inline=True)
        e.add_field(name="Бот", value="Да" if m.bot else "Нет", inline=True)
        e.add_field(name="Создан", value=m.created_at.strftime("%d.%m.%Y"), inline=True)
        if isinstance(m, discord.Member) and m.joined_at:
            e.add_field(name="Присоединился", value=m.joined_at.strftime("%d.%m.%Y"), inline=True)
            roles = [r.mention for r in m.roles if r != i.guild.default_role][:10]  # type: ignore[union-attr]
            if roles:
                e.add_field(name="Роли", value=", ".join(roles), inline=False)
        await i.response.send_message(embed=e)

    @app_commands.command(name="avatar", description="Аватар")
    async def avatar(self, i: discord.Interaction, member: discord.Member | None = None) -> None:
        m = member or i.user
        e = base_embed(title=f"🖼 {m.display_name}")
        e.set_image(url=m.display_avatar.with_size(1024).url)
        await i.response.send_message(embed=e)

    @app_commands.command(name="banner", description="Баннер")
    async def banner(self, i: discord.Interaction, member: discord.Member | None = None) -> None:
        m = member or i.user
        u = await self.bot.fetch_user(m.id)
        if not u.banner:
            await i.response.send_message(embed=error_embed("Нет баннера."), ephemeral=True)
            return
        e = base_embed(title=f"🎨 {m.display_name}")
        e.set_image(url=u.banner.url)
        await i.response.send_message(embed=e)

    @app_commands.command(name="roleinfo", description="Информация о роли")
    async def roleinfo(self, i: discord.Interaction, role: discord.Role) -> None:
        e = base_embed(title=f"🎭 {role.name}")
        e.add_field(name="ID", value=str(role.id), inline=True)
        e.add_field(name="Цвет", value=str(role.color), inline=True)
        e.add_field(name="Позиция", value=str(role.position), inline=True)
        e.add_field(name="Участников", value=str(len(role.members)), inline=True)
        await i.response.send_message(embed=e)

    @app_commands.command(name="poll", description="Опрос (варианты через |)")
    async def poll(self, i: discord.Interaction, question: str, options: str) -> None:
        opts = [o.strip() for o in options.split("|") if o.strip()]
        if not 2 <= len(opts) <= 10:
            await i.response.send_message(embed=error_embed("2–10 вариантов."), ephemeral=True)
            return
        m = await i.channel.send(embed=base_embed(title=f"📊 {question}", description="..."))  # type: ignore[union-attr]
        v = PollView(m.id, question, opts)
        await m.edit(embed=v._embed({}), view=v)
        await self.db.create_poll(m.id, i.guild.id, i.channel_id, question, json.dumps(opts, ensure_ascii=False))
        await i.response.send_message(embed=success_embed(f"Опрос: {m.jump_url}"), ephemeral=True)

    @app_commands.command(name="embed", description="Embed через модалку")
    @is_moderator()
    async def embed_cmd(self, i: discord.Interaction, channel: discord.TextChannel | None = None) -> None:
        await i.response.send_modal(EmbedModal(channel or i.channel))

    @app_commands.command(name="say", description="Текст от бота")
    @is_moderator()
    async def say(self, i: discord.Interaction, text: str) -> None:
        await i.channel.send(text)  # type: ignore[union-attr]
        await i.response.send_message(embed=success_embed("Отправлено."), ephemeral=True)

    @app_commands.command(name="announce", description="Объявление через @everyone")
    @is_admin()
    async def announce(self, i: discord.Interaction, title: str, text: str, channel: discord.TextChannel | None = None) -> None:
        ch = channel or i.channel
        await ch.send(content="@everyone", embed=base_embed(title=f"📢 {title}", description=text))  # type: ignore[union-attr]
        await i.response.send_message(embed=success_embed(f"→ {ch.mention}"), ephemeral=True)


async def setup(bot: commands.Bot) -> None:
    await bot.add_cog(Utility(bot))
'''

# ─────────────────────────────────────────────────────────
# SETUP
# ─────────────────────────────────────────────────────────
SETUP = r'''"""Оформление сервера и бэкапы."""
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
'''

# ─────────────────────────────────────────────────────────
# TICKETS
# ─────────────────────────────────────────────────────────
TICKETS = r'''"""Тикеты поддержки."""
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
'''

# ─────────────────────────────────────────────────────────
# FUN
# ─────────────────────────────────────────────────────────
FUN = r'''"""Экономика, уровни, магазин, мини-игры."""
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
'''

# ─────────────────────────────────────────────────────────
# COMFORT
# ─────────────────────────────────────────────────────────
COMFORT = r'''"""Комфорт: приватные комнаты, AFK, QoL."""
from __future__ import annotations

import asyncio
import logging
from datetime import datetime, timedelta, timezone
from typing import Optional

import discord
from discord import app_commands
from discord.ext import commands, tasks

from config import PANEL_ROOM_CONTROL
from utils.checks import is_admin, is_moderator
from utils.embeds import base_embed, error_embed, success_embed

log = logging.getLogger(__name__)
RC = f"{PANEL_ROOM_CONTROL}:view"
PC = "sb:privroom:view"


class RenameModal(discord.ui.Modal):
    name = discord.ui.TextInput(label="Название", max_length=100)
    def __init__(self, cid: int) -> None:
        super().__init__(title="✏️ Переименовать")
        self.cid = cid
    async def on_submit(self, i: discord.Interaction) -> None:
        ch = i.guild.get_channel(self.cid) if i.guild else None  # type: ignore[union-attr]
        if not ch:
            await i.response.send_message(embed=error_embed("Нет."), ephemeral=True); return
        try:
            await ch.edit(name=self.name.value)
            await i.response.send_message(embed=success_embed(f"→ {self.name.value}"), ephemeral=True)
        except discord.Forbidden:
            await i.response.send_message(embed=error_embed("Нет прав."), ephemeral=True)


class LimitModal(discord.ui.Modal, title="👥 Лимит"):
    lim = discord.ui.TextInput(label="0–99", max_length=2)
    def __init__(self, cid: int) -> None:
        super().__init__()
        self.cid = cid
    async def on_submit(self, i: discord.Interaction) -> None:
        try:
            v = int(self.lim.value); assert 0 <= v <= 99
        except (ValueError, AssertionError):
            await i.response.send_message(embed=error_embed("0–99."), ephemeral=True); return
        ch = i.guild.get_channel(self.cid) if i.guild else None  # type: ignore[union-attr]
        if isinstance(ch, discord.VoiceChannel):
            await ch.edit(user_limit=v)
            await i.response.send_message(embed=success_embed(f"Лимит: {v}"), ephemeral=True)


class RoomView(discord.ui.View):
    def __init__(self, cid: int) -> None:
        super().__init__(timeout=None)
        self.cid = cid
    async def _ch(self, i: discord.Interaction) -> Optional[discord.VoiceChannel]:
        ch = i.guild.get_channel(self.cid) if i.guild else None  # type: ignore[union-attr]
        if not isinstance(ch, discord.VoiceChannel):
            await i.response.send_message(embed=error_embed("Удалена."), ephemeral=True); return None
        return ch
    async def interaction_check(self, i: discord.Interaction) -> bool:
        row = await i.client.db.get_temp_room(self.cid)  # type: ignore[attr-defined]
        if not row or i.user.id != row["owner_id"]:
            await i.response.send_message(embed=error_embed("Только владелец."), ephemeral=True)
            return False
        return True

    @discord.ui.button(label="✏️ Имя", style=discord.ButtonStyle.secondary, custom_id=f"{RC}:rename", row=0)
    async def rn(self, i: discord.Interaction, _) -> None:
        if await self._ch(i): await i.response.send_modal(RenameModal(self.cid))

    @discord.ui.button(label="👥 Лимит", style=discord.ButtonStyle.secondary, custom_id=f"{RC}:limit", row=0)
    async def lm(self, i: discord.Interaction, _) -> None:
        if await self._ch(i): await i.response.send_modal(LimitModal(self.cid))

    @discord.ui.button(label="🔒", style=discord.ButtonStyle.danger, custom_id=f"{RC}:lock", row=1)
    async def lock(self, i: discord.Interaction, _) -> None:
        ch = await self._ch(i)
        if not ch: return
        ow = ch.overwrites_for(i.guild.default_role); ow.connect = False  # type: ignore[union-attr]
        await ch.set_permissions(i.guild.default_role, overwrite=ow)  # type: ignore[union-attr]
        await i.response.send_message(embed=success_embed("Закрыто."), ephemeral=True)

    @discord.ui.button(label="🔓", style=discord.ButtonStyle.success, custom_id=f"{RC}:unlock", row=1)
    async def unlock(self, i: discord.Interaction, _) -> None:
        ch = await self._ch(i)
        if not ch: return
        ow = ch.overwrites_for(i.guild.default_role); ow.connect = None  # type: ignore[union-attr]
        await ch.set_permissions(i.guild.default_role, overwrite=ow)  # type: ignore[union-attr]
        await i.response.send_message(embed=success_embed("Открыто."), ephemeral=True)

    @discord.ui.button(label="👻", style=discord.ButtonStyle.secondary, custom_id=f"{RC}:hide", row=1)
    async def hide(self, i: discord.Interaction, _) -> None:
        ch = await self._ch(i)
        if not ch: return
        ow = ch.overwrites_for(i.guild.default_role); ow.view_channel = False  # type: ignore[union-attr]
        await ch.set_permissions(i.guild.default_role, overwrite=ow)  # type: ignore[union-attr]
        await i.response.send_message(embed=success_embed("Скрыто."), ephemeral=True)

    @discord.ui.button(label="👁", style=discord.ButtonStyle.secondary, custom_id=f"{RC}:show", row=1)
    async def show(self, i: discord.Interaction, _) -> None:
        ch = await self._ch(i)
        if not ch: return
        ow = ch.overwrites_for(i.guild.default_role); ow.view_channel = None  # type: ignore[union-attr]
        await ch.set_permissions(i.guild.default_role, overwrite=ow)  # type: ignore[union-attr]
        await i.response.send_message(embed=success_embed("Показано."), ephemeral=True)

    @discord.ui.button(label="👑", style=discord.ButtonStyle.primary, custom_id=f"{RC}:transfer", row=2)
    async def transfer(self, i: discord.Interaction, _) -> None:
        ch = await self._ch(i)
        if not ch: return
        row = await i.client.db.get_temp_room(self.cid)  # type: ignore[attr-defined]
        owner = row["owner_id"] if row else 0
        mem = [m for m in ch.members if m.id != owner]
        if not mem:
            await i.response.send_message(embed=error_embed("Нет других."), ephemeral=True); return
        sel = discord.ui.Select(placeholder="Новый владелец",
            options=[discord.SelectOption(label=m.display_name, value=str(m.id)) for m in mem[:25]])
        async def cb(inter: discord.Interaction) -> None:
            nid = int(sel.values[0])
            await inter.client.db.update_temp_room_owner(self.cid, nid)  # type: ignore[attr-defined]
            await inter.response.send_message(embed=success_embed(f"→ <@{nid}>"), ephemeral=True)
        sel.callback = cb
        v = discord.ui.View(timeout=60); v.add_item(sel)
        await i.response.send_message("Выберите:", view=v, ephemeral=True)

    @discord.ui.button(label="🚫", style=discord.ButtonStyle.danger, custom_id=f"{RC}:kick", row=2)
    async def kick(self, i: discord.Interaction, _) -> None:
        ch = await self._ch(i)
        if not ch: return
        row = await i.client.db.get_temp_room(self.cid)  # type: ignore[attr-defined]
        owner = row["owner_id"] if row else 0
        mem = [m for m in ch.members if m.id != owner]
        if not mem:
            await i.response.send_message(embed=error_embed("Пусто."), ephemeral=True); return
        sel = discord.ui.Select(placeholder="Кого",
            options=[discord.SelectOption(label=m.display_name, value=str(m.id)) for m in mem[:25]])
        async def cb(inter: discord.Interaction) -> None:
            m = i.guild.get_member(int(sel.values[0]))  # type: ignore[union-attr]
            if m and m.voice and m.voice.channel and m.voice.channel.id == ch.id:
                try:
                    await m.move_to(None)
                    await inter.response.send_message(embed=success_embed(f"{m.mention}"), ephemeral=True)
                except discord.HTTPException:
                    await inter.response.send_message(embed=error_embed("Ошибка."), ephemeral=True)
        sel.callback = cb
        v = discord.ui.View(timeout=60); v.add_item(sel)
        await i.response.send_message("Выберите:", view=v, ephemeral=True)

    @discord.ui.button(label="🗑", style=discord.ButtonStyle.danger, custom_id=f"{RC}:delete", row=2)
    async def delete(self, i: discord.Interaction, _) -> None:
        ch = await self._ch(i)
        if ch:
            cog = i.client.get_cog("Comfort")
            if cog and hasattr(cog, "_dtasks"):
                t = cog._dtasks.pop(ch.id, None)  # type: ignore[attr-defined]
                if t: t.cancel()
            await ch.delete(reason="Владелец удалил")
            await i.client.db.delete_temp_room(ch.id)  # type: ignore[attr-defined]
            await i.response.send_message(embed=success_embed("Удалено."), ephemeral=True)


class PrivView(discord.ui.View):
    def __init__(self, cid: int) -> None:
        super().__init__(timeout=None)
        self.cid = cid
    async def interaction_check(self, i: discord.Interaction) -> bool:
        row = await i.client.db.get_private_room(self.cid)  # type: ignore[attr-defined]
        if not row or i.user.id != row["owner_id"]:
            await i.response.send_message(embed=error_embed("Только владелец."), ephemeral=True)
            return False
        return True

    @discord.ui.button(label="➕", style=discord.ButtonStyle.success, custom_id=f"{PC}:add")
    async def add(self, i: discord.Interaction, _) -> None:
        ch = i.guild.get_channel(self.cid)  # type: ignore[union-attr]
        if not ch: return
        await i.response.send_message("Упомяните:", ephemeral=True)
        try:
            m: discord.Message = await i.client.wait_for("message", timeout=60,
                check=lambda x: x.author == i.user and x.channel_id == i.channel_id)  # type: ignore[attr-defined]
        except asyncio.TimeoutError:
            return
        if m.mentions:
            u = m.mentions[0]
            await ch.set_permissions(u, view_channel=True, send_messages=True, read_message_history=True)
            await i.followup.send(embed=success_embed(f"{u.mention} добавлен."), ephemeral=True)

    @discord.ui.button(label="➖", style=discord.ButtonStyle.secondary, custom_id=f"{PC}:remove")
    async def remove(self, i: discord.Interaction, _) -> None:
        ch = i.guild.get_channel(self.cid)  # type: ignore[union-attr]
        if not ch: return
        await i.response.send_message("Упомяните:", ephemeral=True)
        try:
            m: discord.Message = await i.client.wait_for("message", timeout=60,
                check=lambda x: x.author == i.user and x.channel_id == i.channel_id)  # type: ignore[attr-defined]
        except asyncio.TimeoutError:
            return
        if m.mentions:
            await ch.set_permissions(m.mentions[0], overwrite=None)
            await i.followup.send(embed=success_embed("Убран."), ephemeral=True)

    @discord.ui.button(label="✏️", style=discord.ButtonStyle.secondary, custom_id=f"{PC}:rename")
    async def rn(self, i: discord.Interaction, _) -> None:
        await i.response.send_modal(RenameModal(self.cid))

    @discord.ui.button(label="🗑", style=discord.ButtonStyle.danger, custom_id=f"{PC}:close")
    async def close(self, i: discord.Interaction, _) -> None:
        ch = i.guild.get_channel(self.cid)  # type: ignore[union-attr]
        if ch:
            await ch.delete(reason="Владелец закрыл")
            await i.client.db.delete_private_room(ch.id)  # type: ignore[attr-defined]
            await i.response.send_message(embed=success_embed("Закрыто."), ephemeral=True)


class Comfort(commands.Cog):
    def __init__(self, bot: commands.Bot) -> None:
        self.bot = bot
        self.db = bot.db  # type: ignore[attr-defined]
        self._dtasks: dict[int, asyncio.Task] = {}

    async def cog_load(self) -> None:
        for r in await self.db.get_all_temp_rooms():
            if r["panel_message_id"]:
                self.bot.add_view(RoomView(r["channel_id"]), message_id=r["panel_message_id"])
        for p in await self.db.get_all_private_rooms():
            if p["panel_message_id"]:
                self.bot.add_view(PrivView(p["channel_id"]), message_id=p["panel_message_id"])
        self.reminder_loop.start()
        self.cleanup_loop.start()

    async def cog_unload(self) -> None:
        self.reminder_loop.cancel()
        self.cleanup_loop.cancel()
        for t in self._dtasks.values():
            t.cancel()

    @tasks.loop(minutes=1)
    async def reminder_loop(self) -> None:
        now = datetime.now(timezone.utc).replace(tzinfo=None)
        for r in await self.db.fetchall("SELECT * FROM reminders WHERE done = 0 AND remind_at <= ?", (now,)):
            ch = self.bot.get_channel(r["channel_id"])
            if ch:
                try:
                    await ch.send(f"⏰ <@{r['user_id']}>: **{r['message']}**")
                except discord.HTTPException:
                    pass
            await self.db.execute("UPDATE reminders SET done = 1 WHERE id = ?", (r["id"],))

    @tasks.loop(hours=6)
    async def cleanup_loop(self) -> None:
        cutoff = (datetime.now(timezone.utc) - timedelta(days=7)).replace(tzinfo=None)
        for r in await self.db.fetchall("SELECT * FROM private_rooms WHERE last_active < ?", (cutoff,)):
            ch = self.bot.get_channel(r["channel_id"])
            if ch:
                try:
                    await ch.delete(reason="Неактивно")
                except discord.HTTPException:
                    pass
            await self.db.delete_private_room(r["channel_id"])
        await self.db.cleanup_old_logs(30)

    @commands.Cog.listener()
    async def on_voice_state_update(self, member: discord.Member, before: discord.VoiceState, after: discord.VoiceState) -> None:
        if member.bot or not member.guild: return
        s = await self.db.get_comfort_settings(member.guild.id)
        if not s: return
        afk = s["afk_channel_id"]
        if afk:
            if after.channel and after.channel.id == afk and (not before.channel or before.channel.id != afk):
                row = await self.db.get_afk(member.guild.id, member.id)
                if not row:
                    await self.db.set_afk(member.guild.id, member.id, "в AFK-канале", member.nick)
                    try:
                        await member.edit(nick=f"{s['afk_suffix'] or '[AFK] '}{member.display_name}"[:32])
                    except discord.Forbidden:
                        pass
            elif before.channel and before.channel.id == afk and (not after.channel or after.channel.id != afk):
                row = await self.db.remove_afk(member.guild.id, member.id)
                if row:
                    try:
                        await member.edit(nick=row["old_nick"])
                    except discord.Forbidden:
                        pass
        hub = s["hub_channel_id"]
        if hub and after.channel and after.channel.id == hub:
            await self._create_room(member, s); return
        if before.channel and (not hub or before.channel.id != hub):
            if await self.db.get_temp_room(before.channel.id):
                await self._sched_delete(before.channel, s["delete_timeout"] or 30)

    async def _create_room(self, member: discord.Member, s) -> None:
        try:
            cat = member.guild.get_channel(s["category_id"]) if s["category_id"] else None
            game = ""
            if s["use_game_in_name"]:
                for a in member.activities:
                    if isinstance(a, discord.Game):
                        game = a.name; break
            name = (s["room_template"] or "🔊 {user}").format(user=member.display_name, count=0, game=game)[:100]
            me = member.guild.me or member.guild.get_member(self.bot.user.id)  # type: ignore[union-attr]
            ow = {
                member.guild.default_role: discord.PermissionOverwrite(view_channel=True, connect=True),
                member: discord.PermissionOverwrite(manage_channels=True, move_members=True, mute_members=True, deafen_members=True),
            }
            if me:
                ow[me] = discord.PermissionOverwrite(manage_channels=True, move_members=True, view_channel=True)
            room = await member.guild.create_voice_channel(
                name=name, category=cat if isinstance(cat, discord.CategoryChannel) else None,
                overwrites=ow, reason=f"Комната {member}",
            )
            await member.move_to(room)
            await self.db.add_temp_room(room.id, member.guild.id, member.id, s["category_id"])
            msg = await room.send(embed=base_embed(title="🎛 Управление", description=f"{member.mention}, это твоя комната."), view=RoomView(room.id))
            await self.db.update_temp_room_panel(room.id, msg.id)
        except discord.Forbidden:
            log.warning("Нет прав: %s", member.guild.id)
        except discord.HTTPException:
            log.exception("create_room")

    async def _sched_delete(self, ch: discord.VoiceChannel, timeout: int) -> None:
        if ch.id in self._dtasks:
            self._dtasks[ch.id].cancel()
        async def _do() -> None:
            await asyncio.sleep(timeout)
            fresh = ch.guild.get_channel(ch.id)
            if isinstance(fresh, discord.VoiceChannel) and len(fresh.members) == 0:
                try:
                    await fresh.delete(reason="Пусто")
                except discord.NotFound:
                    pass
                finally:
                    await self.db.delete_temp_room(ch.id)
                    self._dtasks.pop(ch.id, None)
        self._dtasks[ch.id] = asyncio.create_task(_do())

    @commands.Cog.listener()
    async def on_message(self, m: discord.Message) -> None:
        if m.author.bot or not m.guild: return
        afk = await self.db.remove_afk(m.guild.id, m.author.id)
        if afk:
            try:
                await m.author.edit(nick=afk["old_nick"])
            except discord.Forbidden:
                pass
            await m.channel.send(f"👋 С возвращением, {m.author.mention}!", delete_after=10)
        if m.mentions:
            for u in m.mentions:
                if u.bot: continue
                row = await self.db.get_afk(m.guild.id, u.id)
                if row:
                    await m.channel.send(f"💤 **{u.display_name}** AFK: *{row['reason']}*", delete_after=15)
        await self.db.log_message(m.guild.id, m.channel_id, m.author.id)
        if await self.db.get_private_room(m.channel_id):
            await self.db.touch_private_room(m.channel_id)

    @commands.Cog.listener()
    async def on_message_delete(self, m: discord.Message) -> None:
        if m.author.bot or not m.guild: return
        await self.db.save_snipe(m.channel_id, m.guild.id, m.id, m.author.id, str(m.author), m.content or "[вложение]")

    @app_commands.command(name="room", description="Управление комнатой / setup")
    @app_commands.choices(action=[
        app_commands.Choice(name="info", value="info"),
        app_commands.Choice(name="setup", value="setup"),
    ])
    async def room(self, i: discord.Interaction, action: str = "info") -> None:
        if action == "setup":
            await self._setup(i)
        else:
            rooms = await self.db.get_user_temp_rooms(i.guild.id, i.user.id)  # type: ignore[union-attr]
            if not rooms:
                await i.response.send_message(embed=error_embed("Нет комнат. Зайдите в хаб."), ephemeral=True); return
            e = base_embed(title="🎧 Ваши комнаты")
            for r in rooms[:10]:
                link = f"<#{r['channel_id']}>"
                if r["panel_message_id"]:
                    jump = f"https://discord.com/channels/{i.guild.id}/{r['channel_id']}/{r['panel_message_id']}"  # type: ignore[union-attr]
                    link = f"{link} ([панель]({jump}))"
                e.add_field(name="Комната", value=link, inline=False)
            await i.response.send_message(embed=e, ephemeral=True)

    async def _setup(self, i: discord.Interaction) -> None:
        if not i.user.guild_permissions.administrator:  # type: ignore[union-attr]
            await i.response.send_message(embed=error_embed("Только админ."), ephemeral=True); return
        vc = list(i.guild.voice_channels)[:25]  # type: ignore[union-attr]
        cats = list(i.guild.categories)[:25]  # type: ignore[union-attr]
        if not vc or not cats:
            await i.response.send_message(embed=error_embed("Создайте ≥1 войс и ≥1 категорию."), ephemeral=True); return
        hub = discord.ui.Select(placeholder="1) Канал-хаб",
            options=[discord.SelectOption(label=c.name, value=str(c.id)) for c in vc])
        cat = discord.ui.Select(placeholder="2) Категория",
            options=[discord.SelectOption(label=c.name, value=str(c.id)) for c in cats])
        afk_opts = [discord.SelectOption(label="(нет)", value="0")] + [
            discord.SelectOption(label=c.name, value=str(c.id)) for c in vc]
        afk = discord.ui.Select(placeholder="3) AFK (опц.)", options=afk_opts, required=False)
        v = discord.ui.View(timeout=180)
        v.add_item(hub); v.add_item(cat); v.add_item(afk)
        async def save(inter: discord.Interaction) -> None:
            if not hub.values or not cat.values:
                await inter.response.send_message(embed=error_embed("Выберите хаб и категорию."), ephemeral=True); return
            await self.db.upsert_comfort_settings(
                inter.guild.id,
                hub_channel_id=int(hub.values[0]),
                category_id=int(cat.values[0]),
                afk_channel_id=int(afk.values[0]) if afk.values and afk.values[0] != "0" else None,
            )
            await inter.response.send_message(embed=success_embed("Сохранено."), ephemeral=True)
        btn = discord.ui.Button(label="Сохранить", style=discord.ButtonStyle.success)
        btn.callback = save
        v.add_item(btn)
        await i.response.send_message(embed=base_embed(title="⚙️ Настройка"), view=v, ephemeral=True)

    @app_commands.command(name="privateroom", description="Приватные текстовые комнаты")
    @app_commands.choices(action=[
        app_commands.Choice(name="create", value="create"),
        app_commands.Choice(name="list", value="list"),
        app_commands.Choice(name="delete", value="delete"),
    ])
    async def priv(self, i: discord.Interaction, action: str = "list") -> None:
        if action == "create":
            s = await self.db.get_comfort_settings(i.guild.id)  # type: ignore[union-attr]
            cat = None
            if s and s["private_category_id"]:
                cat = i.guild.get_channel(s["private_category_id"])  # type: ignore[union-attr]
            if not isinstance(cat, discord.CategoryChannel): cat = None
            ex = await self.db.get_user_private_rooms(i.guild.id, i.user.id)  # type: ignore[union-attr]
            if len(ex) >= 3:
                await i.response.send_message(embed=error_embed("Лимит: 3."), ephemeral=True); return
            me = i.guild.me or i.guild.get_member(i.client.user.id)  # type: ignore[union-attr]
            ow = {
                i.guild.default_role: discord.PermissionOverwrite(view_channel=False),  # type: ignore[union-attr]
                i.user: discord.PermissionOverwrite(view_channel=True, send_messages=True, manage_channels=True),
            }
            if me: ow[me] = discord.PermissionOverwrite(view_channel=True, send_messages=True, manage_channels=True)
            ch = await i.guild.create_text_channel(name=f"💬-{i.user.name}"[:100], category=cat, overwrites=ow, reason="Приватка")  # type: ignore[union-attr]
            msg = await ch.send(embed=base_embed(title="🔒 Приватка"), view=PrivView(ch.id))
            await self.db.add_private_room(ch.id, i.guild.id, i.user.id, msg.id)  # type: ignore[union-attr]
            await i.response.send_message(embed=success_embed(f"{ch.mention}"), ephemeral=True)
        elif action == "delete":
            rows = await self.db.get_user_private_rooms(i.guild.id, i.user.id)  # type: ignore[union-attr]
            if not rows:
                await i.response.send_message(embed=error_embed("Нет."), ephemeral=True); return
            sel = discord.ui.Select(placeholder="Какую?",
                options=[discord.SelectOption(label=f"#{r['channel_id']}", value=str(r["channel_id"])) for r in rows[:25]])
            async def cb(inter: discord.Interaction) -> None:
                cid = int(sel.values[0])
                ch2 = inter.guild.get_channel(cid)  # type: ignore[union-attr]
                if ch2:
                    try:
                        await ch2.delete(reason="Владелец")
                    except discord.HTTPException:
                        pass
                await inter.client.db.delete_private_room(cid)  # type: ignore[attr-defined]
                await inter.response.send_message(embed=success_embed("Удалено."), ephemeral=True)
            sel.callback = cb
            v = discord.ui.View(timeout=60); v.add_item(sel)
            await i.response.send_message("Выберите:", view=v, ephemeral=True)
        else:
            rows = await self.db.get_user_private_rooms(i.guild.id, i.user.id)  # type: ignore[union-attr]
            if not rows:
                await i.response.send_message(embed=error_embed("Нет."), ephemeral=True); return
            e = base_embed(title="🔒 Ваши приватки")
            for r in rows:
                e.add_field(name=f"<#{r['channel_id']}>", value=f"Активность: {r['last_active']}", inline=False)
            await i.response.send_message(embed=e, ephemeral=True)

    @app_commands.command(name="afk", description="AFK")
    async def afk(self, i: discord.Interaction, reason: str = "Без причины") -> None:
        if not isinstance(i.user, discord.Member): return
        await self.db.set_afk(i.guild.id, i.user.id, reason, i.user.nick)  # type: ignore[union-attr]
        try:
            await i.user.edit(nick=f"[AFK] {i.user.display_name}"[:32])
        except discord.Forbidden:
            pass
        await i.response.send_message(embed=success_embed(f"AFK: {reason}"), ephemeral=True)

    @app_commands.command(name="remind", description="Напоминание")
    async def remind(self, i: discord.Interaction, minutes: int, text: str) -> None:
        if not 1 <= minutes <= 10080:
            await i.response.send_message(embed=error_embed("1–10080."), ephemeral=True); return
        when = datetime.now(timezone.utc).replace(tzinfo=None) + timedelta(minutes=minutes)
        await self.db.execute(
            "INSERT INTO reminders (user_id, guild_id, channel_id, message, remind_at) VALUES (?, ?, ?, ?, ?)",
            (i.user.id, i.guild.id, i.channel_id, text, when),  # type: ignore[union-attr]
        )
        await i.response.send_message(embed=success_embed(f"Через {minutes} мин."), ephemeral=True)

    @app_commands.command(name="bookmark", description="Закладка")
    async def bookmark(self, i: discord.Interaction, message_id: str, channel: discord.TextChannel | None = None) -> None:
        ch = channel or i.channel
        try:
            m = await ch.fetch_message(int(message_id))  # type: ignore[union-attr]
        except (discord.NotFound, ValueError):
            await i.response.send_message(embed=error_embed("Нет."), ephemeral=True); return
        await self.db.execute(
            "INSERT INTO bookmarks (user_id, guild_id, message_id, channel_id, content, author_id) VALUES (?, ?, ?, ?, ?, ?)",
            (i.user.id, i.guild.id, m.id, ch.id, m.content[:1900], m.author.id),  # type: ignore[union-attr]
        )
        await i.response.send_message(embed=success_embed(f"{m.jump_url}"), ephemeral=True)

    @app_commands.command(name="bookmarks", description="Мои закладки")
    async def bookmarks(self, i: discord.Interaction) -> None:
        rows = await self.db.fetchall(
            "SELECT * FROM bookmarks WHERE user_id = ? AND guild_id = ? ORDER BY created_at DESC LIMIT 10",
            (i.user.id, i.guild.id),  # type: ignore[union-attr]
        )
        if not rows:
            await i.response.send_message(embed=error_embed("Пусто."), ephemeral=True); return
        e = base_embed(title="🔖 Закладки")
        for r in rows:
            e.add_field(name=f"<@{r['author_id']}>",
                value=f"{r['content'][:100]}\n[перейти](https://discord.com/channels/{r['guild_id']}/{r['channel_id']}/{r['message_id']})",
                inline=False)
        await i.response.send_message(embed=e, ephemeral=True)

    @app_commands.command(name="timer", description="Таймер")
    async def timer(self, i: discord.Interaction, seconds: int, text: str = "⏰ Время вышло!") -> None:
        if not 10 <= seconds <= 86400:
            await i.response.send_message(embed=error_embed("10–86400."), ephemeral=True); return
        await i.response.send_message(embed=success_embed(f"Таймер {seconds}с."), ephemeral=True)
        ch = i.channel
        um = i.user.mention
        async def f() -> None:
            await asyncio.sleep(seconds)
            if ch:
                try:
                    await ch.send(f"{um} — {text}")
                except discord.HTTPException:
                    pass
        asyncio.create_task(f())

    @app_commands.command(name="snipe", description="Последнее удалённое")
    @is_moderator()
    async def snipe(self, i: discord.Interaction) -> None:
        row = await self.db.get_snipe(i.channel_id)
        if not row:
            await i.response.send_message(embed=error_embed("Пусто."), ephemeral=True); return
        await i.response.send_message(embed=base_embed(
            title="🔍 Snipe",
            description=f"**{row['author_name']}**: {row['content']}\n\n*{row['deleted_at']}*",
        ), ephemeral=True)

    @app_commands.command(name="purge-bots", description="Очистить сообщения ботов")
    @is_moderator()
    async def purge_bots(self, i: discord.Interaction, amount: int = 50) -> None:
        await i.response.defer(ephemeral=True)
        d = await i.channel.purge(limit=min(amount, 200), check=lambda m: m.author.bot)  # type: ignore[union-attr]
        await i.followup.send(embed=success_embed(f"{len(d)}"), ephemeral=True)

    @app_commands.command(name="move-all", description="Переместить всех из войса в войс")
    @is_moderator()
    async def move_all(self, i: discord.Interaction, source: discord.VoiceChannel, target: discord.VoiceChannel) -> None:
        n = 0
        for m in list(source.members):
            try:
                await m.move_to(target); n += 1
            except discord.HTTPException:
                pass
        await i.response.send_message(embed=success_embed(f"Перемещено: {n}."), ephemeral=True)

    @app_commands.command(name="status", description="Статус бота")
    @is_admin()
    async def status(self, i: discord.Interaction, text: str) -> None:
        await self.bot.change_presence(activity=discord.Game(name=text[:128]))
        await i.response.send_message(embed=success_embed(f"→ {text}"), ephemeral=True)


async def setup(bot: commands.Bot) -> None:
    await bot.add_cog(Comfort(bot))
'''

# ─────────────────────────────────────────────────────────
# REACTION ROLES
# ─────────────────────────────────────────────────────────
RR = r'''"""Реакционные роли (persistent)."""
from __future__ import annotations

import discord
from discord import app_commands
from discord.ext import commands

from utils.checks import is_admin
from utils.embeds import error_embed, success_embed


class RoleSelect(discord.ui.Select):
    def __init__(self, mid: int, pairs: list[tuple[str, int]]) -> None:
        self.mid = mid
        super().__init__(
            placeholder="Выберите роли", min_values=0, max_values=len(pairs),
            options=[discord.SelectOption(label=n, value=str(rid)) for n, rid in pairs[:25]],
            custom_id=f"sb:rr:{mid}",
        )

    async def callback(self, i: discord.Interaction) -> None:
        db = i.client.db  # type: ignore[attr-defined]
        rows = await db.fetchall("SELECT role_id FROM reaction_roles WHERE message_id = ?", (self.mid,))
        all_ids = {r["role_id"] for r in rows}
        selected = {int(v) for v in self.values}
        added, removed = [], []
        for rid in all_ids:
            r = i.guild.get_role(rid)  # type: ignore[union-attr]
            if not r: continue
            if rid in selected and r not in i.user.roles:  # type: ignore[union-attr]
                await i.user.add_roles(r, reason="Reaction role")  # type: ignore[union-attr]
                added.append(r.name)
            elif rid not in selected and r in i.user.roles:  # type: ignore[union-attr]
                await i.user.remove_roles(r, reason="Reaction role")  # type: ignore[union-attr]
                removed.append(r.name)
        msg = []
        if added: msg.append(f"✅ {', '.join(added)}")
        if removed: msg.append(f"❌ {', '.join(removed)}")
        await i.response.send_message("\n".join(msg) or "—", ephemeral=True)


class ReactionRoles(commands.Cog):
    def __init__(self, bot: commands.Bot) -> None:
        self.bot = bot
        self.db = bot.db  # type: ignore[attr-defined]

    async def cog_load(self) -> None:
        rows = await self.db.fetchall("SELECT * FROM reaction_roles")
        groups: dict[int, list[tuple[str, int]]] = {}
        for r in rows:
            g = self.bot.get_guild(r["guild_id"])
            if not g: continue
            role = g.get_role(r["role_id"])
            if not role: continue
            groups.setdefault(r["message_id"], []).append((role.name, r["role_id"]))
        for mid, pairs in groups.items():
            v = discord.ui.View(timeout=None)
            v.add_item(RoleSelect(mid, pairs))
            self.bot.add_view(v, message_id=mid)

    @app_commands.command(name="reactionrole", description="Создать панель ролей")
    @is_admin()
    async def create(self, i: discord.Interaction,
                     role1: discord.Role, role2: discord.Role | None = None,
                     role3: discord.Role | None = None, role4: discord.Role | None = None,
                     role5: discord.Role | None = None) -> None:
        roles = [r for r in (role1, role2, role3, role4, role5) if r is not None]
        if not roles:
            await i.response.send_message(embed=error_embed("Хотя бы одна роль."), ephemeral=True); return
        msg = await i.channel.send(embed=discord.Embed(  # type: ignore[union-attr]
            title="🎭 Выбор ролей", description="Выберите в меню ниже.", color=0x5865F2,
        ))
        v = discord.ui.View(timeout=None)
        v.add_item(RoleSelect(msg.id, [(r.name, r.id) for r in roles]))
        await msg.edit(view=v)
        for r in roles:
            await self.db.execute(
                "INSERT INTO reaction_roles (guild_id, message_id, channel_id, role_id, emoji, mode) VALUES (?, ?, ?, ?, ?, 'select')",
                (i.guild.id, msg.id, msg.channel.id, r.id, ""),  # type: ignore[union-attr]
            )
        await i.response.send_message(embed=success_embed("Панель создана."), ephemeral=True)


async def setup(bot: commands.Bot) -> None:
    await bot.add_cog(ReactionRoles(bot))
'''

# ─────────────────────────────────────────────────────────
# STATS
# ─────────────────────────────────────────────────────────
STATS = r'''"""Статистика."""
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
'''

# ─────────────────────────────────────────────────────────
# GIVEAWAYS
# ─────────────────────────────────────────────────────────
GW = r'''"""Розыгрыши (persistent в БД)."""
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
'''


def main() -> None:
    print(f"Project: {BASE}\n")
    print("Пишу 8 когов (часть B):\n")
    write("utility.py", UTILITY)
    write("setup.py", SETUP)
    write("tickets.py", TICKETS)
    write("fun.py", FUN)
    write("comfort.py", COMFORT)
    write("reaction_roles.py", RR)
    write("stats.py", STATS)
    write("giveaways.py", GW)
    print("\n" + "=" * 50)
    print("OK. Все 14 когов готовы!")
    print("=" * 50)
    print("\nЗапуск:")
    print("  1. Создайте .env (из .env.example), вставьте DISCORD_TOKEN")
    print("  2. pip install -r requirements.txt")
    print("  3. python main.py")


if __name__ == "__main__":
    main()
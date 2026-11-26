"""Утилиты и информация."""
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

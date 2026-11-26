"""Приветствие и верификация."""
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

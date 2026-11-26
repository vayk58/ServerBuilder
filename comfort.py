"""Комфорт: приватные комнаты, AFK, QoL."""
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

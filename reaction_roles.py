"""Реакционные роли (persistent)."""
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

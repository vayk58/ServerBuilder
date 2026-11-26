"""build.py — создаёт структуру ServerBuilder и записывает базовые файлы.

Запуск: python build.py
После него запустите build_cogs.py (наполнит cogs/ реальным кодом).
"""
from __future__ import annotations

from pathlib import Path

BASE = Path(__file__).resolve().parent
OVERWRITE_BASE = True
OVERWRITE_COGS = False

FOLDERS = ["database", "utils", "cogs", "assets", "data", "backups"]

FILES: dict[str, str] = {}

FILES["requirements.txt"] = (
    "discord.py>=2.3.2\n"
    "aiosqlite>=0.19.0\n"
    "python-dotenv>=1.0.0\n"
    "Pillow>=10.0.0\n"
    "matplotlib>=3.8.0\n"
    "aiohttp>=3.9.0\n"
)

FILES[".env.example"] = (
    "DISCORD_TOKEN=your_bot_token_here\n"
    "GUILD_ID=\n"
    "LOG_LEVEL=INFO\n"
    "DATABASE_PATH=serverbuilder.db\n"
)

FILES[".gitignore"] = (
    ".env\n"
    "*.db\n"
    "*.db-wal\n"
    "*.db-shm\n"
    "venv/\n"
    "__pycache__/\n"
    "*.pyc\n"
    "data/\n"
    "backups/\n"
    "assets/font.ttf\n"
)

FILES["config.py"] = r'''"""Конфигурация бота."""
from __future__ import annotations

import os
from pathlib import Path

from dotenv import load_dotenv

BASE_DIR = Path(__file__).resolve().parent
load_dotenv(BASE_DIR / ".env", encoding="utf-8")

TOKEN: str | None = os.getenv("DISCORD_TOKEN")
GUILD_ID: int | None = int(os.getenv("GUILD_ID")) if os.getenv("GUILD_ID") else None
LOG_LEVEL: str = os.getenv("LOG_LEVEL", "INFO")
DATABASE_PATH: Path = BASE_DIR / os.getenv("DATABASE_PATH", "serverbuilder.db")

COLOR_PRIMARY = 0x5865F2
COLOR_SUCCESS = 0x57F287
COLOR_WARNING = 0xFEE75C
COLOR_ERROR = 0xED4245
COLOR_INFO = 0x3498DB

BOT_VERSION = "1.2.0"

PANEL_ROOM_CONTROL = "sb:room_control"
PANEL_TICKET_CREATE = "sb:ticket_create"
PANEL_VERIFY = "sb:verify"
'''

FILES["main.py"] = r'''"""Точка входа ServerBuilder."""
from __future__ import annotations

import asyncio
import logging

import discord
from discord.ext import commands

from config import DATABASE_PATH, GUILD_ID, LOG_LEVEL, TOKEN
from database.db import Database
from utils.errors import on_app_command_error, on_command_error

logging.basicConfig(
    level=getattr(logging, LOG_LEVEL.upper(), logging.INFO),
    format="%(asctime)s | %(levelname)-8s | %(name)s | %(message)s",
)
log = logging.getLogger("serverbuilder")

COGS = [
    "cogs.wizard",
    "cogs.moderation",
    "cogs.welcome",
    "cogs.utility",
    "cogs.setup",
    "cogs.comfort",
    "cogs.tickets",
    "cogs.fun",
    "cogs.reaction_roles",
    "cogs.stats",
    "cogs.giveaways",
    "cogs.health",
    "cogs.antiraid",
    "cogs.community",
]


class ServerBuilderBot(commands.Bot):
    def __init__(self) -> None:
        intents = discord.Intents.default()
        intents.members = True
        intents.message_content = True
        intents.voice_states = True
        intents.presences = True
        super().__init__(command_prefix="!", intents=intents)
        self.db = Database(str(DATABASE_PATH))
        self.tree.on_error = on_app_command_error

    async def setup_hook(self) -> None:
        await self.db.connect()
        for cog in COGS:
            try:
                await self.load_extension(cog)
                log.info("Ког загружен: %s", cog)
            except Exception:
                log.exception("Не удалось загрузить ког %s", cog)

        if GUILD_ID:
            guild = discord.Object(id=GUILD_ID)
            self.tree.copy_global_to(guild=guild)
            await self.tree.sync(guild=guild)
            log.info("Команды синхронизированы для гильдии %s", GUILD_ID)
        else:
            await self.tree.sync()
            log.info("Глобальные команды синхронизированы")

    async def on_ready(self) -> None:
        log.info("Бот запущен как %s (ID: %s)", self.user, self.user.id if self.user else "?")

    async def on_command_error(self, ctx: commands.Context, error: commands.CommandError) -> None:
        await on_command_error(ctx, error)

    async def close(self) -> None:
        await self.db.close()
        await super().close()


async def main() -> None:
    if not TOKEN:
        raise RuntimeError("DISCORD_TOKEN не задан в .env")
    bot = ServerBuilderBot()
    async with bot:
        await bot.start(TOKEN)


if __name__ == "__main__":
    asyncio.run(main())
'''

FILES["database/db.py"] = r'''"""Асинхронный слой БД."""
from __future__ import annotations

import logging
from typing import Any, Optional

import aiosqlite

log = logging.getLogger(__name__)

SCHEMA = """
CREATE TABLE IF NOT EXISTS guilds (guild_id INTEGER PRIMARY KEY, created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP);
CREATE TABLE IF NOT EXISTS settings (guild_id INTEGER PRIMARY KEY, mod_log_channel INTEGER, snipe_enabled INTEGER DEFAULT 1);
CREATE TABLE IF NOT EXISTS warnings (id INTEGER PRIMARY KEY AUTOINCREMENT, guild_id INTEGER NOT NULL, user_id INTEGER NOT NULL, moderator_id INTEGER NOT NULL, reason TEXT NOT NULL, created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP);
CREATE TABLE IF NOT EXISTS cases (id INTEGER PRIMARY KEY AUTOINCREMENT, guild_id INTEGER NOT NULL, user_id INTEGER NOT NULL, moderator_id INTEGER NOT NULL, action TEXT NOT NULL, reason TEXT NOT NULL, duration TEXT, created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP);
CREATE TABLE IF NOT EXISTS automod_settings (guild_id INTEGER PRIMARY KEY, bad_words INTEGER DEFAULT 1, spam INTEGER DEFAULT 1, invites INTEGER DEFAULT 1, mass_mentions INTEGER DEFAULT 1, log_channel_id INTEGER);
CREATE TABLE IF NOT EXISTS bad_words (guild_id INTEGER NOT NULL, word TEXT NOT NULL, PRIMARY KEY (guild_id, word));
CREATE TABLE IF NOT EXISTS message_log (id INTEGER PRIMARY KEY AUTOINCREMENT, guild_id INTEGER NOT NULL, channel_id INTEGER NOT NULL, user_id INTEGER NOT NULL, ts TIMESTAMP DEFAULT CURRENT_TIMESTAMP);
CREATE INDEX IF NOT EXISTS idx_messages_guild_ts ON message_log(guild_id, ts);
CREATE TABLE IF NOT EXISTS snipe_cache (channel_id INTEGER PRIMARY KEY, guild_id INTEGER NOT NULL, message_id INTEGER NOT NULL, author_id INTEGER NOT NULL, author_name TEXT NOT NULL, content TEXT, deleted_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP);
CREATE TABLE IF NOT EXISTS welcome_settings (guild_id INTEGER PRIMARY KEY, welcome_channel_id INTEGER, goodbye_channel_id INTEGER, welcome_text TEXT DEFAULT 'Добро пожаловать, {user}!', goodbye_text TEXT DEFAULT 'Пока, {user}...', autorole_id INTEGER, verify_role_id INTEGER, verify_channel_id INTEGER, background_url TEXT);
CREATE TABLE IF NOT EXISTS tickets (id INTEGER PRIMARY KEY AUTOINCREMENT, guild_id INTEGER NOT NULL, channel_id INTEGER NOT NULL, user_id INTEGER NOT NULL, category TEXT DEFAULT 'general', status TEXT DEFAULT 'open', claimed_by INTEGER, created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP, closed_at TIMESTAMP);
CREATE TABLE IF NOT EXISTS ticket_settings (guild_id INTEGER PRIMARY KEY, panel_channel_id INTEGER, category_id INTEGER, support_role_id INTEGER, log_channel_id INTEGER);
CREATE TABLE IF NOT EXISTS economy (guild_id INTEGER NOT NULL, user_id INTEGER NOT NULL, balance INTEGER DEFAULT 0, bank INTEGER DEFAULT 0, daily_streak INTEGER DEFAULT 0, last_daily TIMESTAMP, last_work TIMESTAMP, PRIMARY KEY (guild_id, user_id));
CREATE TABLE IF NOT EXISTS levels (guild_id INTEGER NOT NULL, user_id INTEGER NOT NULL, xp INTEGER DEFAULT 0, level INTEGER DEFAULT 0, messages INTEGER DEFAULT 0, PRIMARY KEY (guild_id, user_id));
CREATE TABLE IF NOT EXISTS shop_items (id INTEGER PRIMARY KEY AUTOINCREMENT, guild_id INTEGER NOT NULL, role_id INTEGER NOT NULL, name TEXT NOT NULL, price INTEGER NOT NULL, stock INTEGER DEFAULT -1);
CREATE TABLE IF NOT EXISTS reaction_roles (id INTEGER PRIMARY KEY AUTOINCREMENT, guild_id INTEGER NOT NULL, message_id INTEGER NOT NULL, channel_id INTEGER NOT NULL, role_id INTEGER NOT NULL, emoji TEXT NOT NULL, mode TEXT DEFAULT 'reaction');
CREATE TABLE IF NOT EXISTS backups (id INTEGER PRIMARY KEY AUTOINCREMENT, guild_id INTEGER NOT NULL, data TEXT NOT NULL, created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP);
CREATE TABLE IF NOT EXISTS temp_rooms (channel_id INTEGER PRIMARY KEY, guild_id INTEGER NOT NULL, owner_id INTEGER NOT NULL, category_id INTEGER, panel_message_id INTEGER, created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP, settings_json TEXT DEFAULT '{}');
CREATE TABLE IF NOT EXISTS private_rooms (channel_id INTEGER PRIMARY KEY, guild_id INTEGER NOT NULL, owner_id INTEGER NOT NULL, invited_users TEXT DEFAULT '', panel_message_id INTEGER, last_active TIMESTAMP DEFAULT CURRENT_TIMESTAMP);
CREATE TABLE IF NOT EXISTS comfort_settings (guild_id INTEGER PRIMARY KEY, hub_channel_id INTEGER, category_id INTEGER, afk_channel_id INTEGER, private_category_id INTEGER, room_template TEXT DEFAULT '🔊 {user} — комната', delete_timeout INTEGER DEFAULT 30, default_user_limit INTEGER DEFAULT 0, afk_suffix TEXT DEFAULT '[AFK] ', use_game_in_name INTEGER DEFAULT 0);
CREATE TABLE IF NOT EXISTS bookmarks (id INTEGER PRIMARY KEY AUTOINCREMENT, user_id INTEGER NOT NULL, guild_id INTEGER NOT NULL, message_id INTEGER NOT NULL, channel_id INTEGER NOT NULL, content TEXT NOT NULL, author_id INTEGER NOT NULL, created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP);
CREATE TABLE IF NOT EXISTS reminders (id INTEGER PRIMARY KEY AUTOINCREMENT, user_id INTEGER NOT NULL, guild_id INTEGER NOT NULL, channel_id INTEGER NOT NULL, message TEXT NOT NULL, remind_at TIMESTAMP NOT NULL, done INTEGER DEFAULT 0);
CREATE TABLE IF NOT EXISTS afk (guild_id INTEGER NOT NULL, user_id INTEGER NOT NULL, reason TEXT NOT NULL, old_nick TEXT, PRIMARY KEY (guild_id, user_id));
CREATE TABLE IF NOT EXISTS giveaways (message_id INTEGER PRIMARY KEY, guild_id INTEGER NOT NULL, channel_id INTEGER NOT NULL, prize TEXT NOT NULL, winners INTEGER NOT NULL, host_id INTEGER NOT NULL, end_at TIMESTAMP NOT NULL, participants TEXT DEFAULT '', ended INTEGER DEFAULT 0);
CREATE TABLE IF NOT EXISTS polls (message_id INTEGER PRIMARY KEY, guild_id INTEGER NOT NULL, channel_id INTEGER NOT NULL, question TEXT NOT NULL, options TEXT NOT NULL);
CREATE TABLE IF NOT EXISTS poll_votes (message_id INTEGER NOT NULL, user_id INTEGER NOT NULL, option_idx INTEGER NOT NULL, PRIMARY KEY (message_id, user_id));
CREATE TABLE IF NOT EXISTS guild_rules (guild_id INTEGER PRIMARY KEY, channel_id INTEGER, message_id INTEGER, role_id INTEGER, rules_text TEXT);
CREATE TABLE IF NOT EXISTS rules_accepted (guild_id INTEGER NOT NULL, user_id INTEGER NOT NULL, accepted_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP, PRIMARY KEY (guild_id, user_id));
CREATE TABLE IF NOT EXISTS suggestions (id INTEGER PRIMARY KEY AUTOINCREMENT, guild_id INTEGER NOT NULL, channel_id INTEGER NOT NULL, message_id INTEGER NOT NULL, author_id INTEGER NOT NULL, content TEXT NOT NULL, status TEXT DEFAULT 'open', created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP);
CREATE TABLE IF NOT EXISTS suggestion_votes (suggestion_id INTEGER NOT NULL, user_id INTEGER NOT NULL, vote INTEGER NOT NULL, PRIMARY KEY (suggestion_id, user_id));
CREATE TABLE IF NOT EXISTS antiraid_settings (guild_id INTEGER PRIMARY KEY, enabled INTEGER DEFAULT 1, join_threshold INTEGER DEFAULT 10, time_window INTEGER DEFAULT 60, action TEXT DEFAULT 'lockdown', notify_channel_id INTEGER);
CREATE TABLE IF NOT EXISTS antiraid_log (id INTEGER PRIMARY KEY AUTOINCREMENT, guild_id INTEGER NOT NULL, event TEXT NOT NULL, details TEXT, created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP);
"""


class Database:
    def __init__(self, path: str) -> None:
        self.path = path
        self._conn: aiosqlite.Connection | None = None

    async def connect(self) -> None:
        self._conn = await aiosqlite.connect(self.path)
        self._conn.row_factory = aiosqlite.Row
        await self._conn.execute("PRAGMA journal_mode=WAL;")
        await self._conn.executescript(SCHEMA)
        await self._conn.commit()
        log.info("БД подключена: %s", self.path)

    async def close(self) -> None:
        if self._conn:
            await self._conn.close()
            self._conn = None

    async def execute(self, sql: str, params: tuple[Any, ...] = ()) -> aiosqlite.Cursor:
        if not self._conn:
            raise RuntimeError("Database is not connected")
        cur = await self._conn.execute(sql, params)
        await self._conn.commit()
        return cur

    async def fetchone(self, sql: str, params: tuple[Any, ...] = ()) -> Optional[aiosqlite.Row]:
        if not self._conn:
            raise RuntimeError("Database is not connected")
        async with self._conn.execute(sql, params) as cur:
            return await cur.fetchone()

    async def fetchall(self, sql: str, params: tuple[Any, ...] = ()) -> list[aiosqlite.Row]:
        if not self._conn:
            raise RuntimeError("Database is not connected")
        async with self._conn.execute(sql, params) as cur:
            return await cur.fetchall()

    async def get_comfort_settings(self, guild_id: int):
        return await self.fetchone("SELECT * FROM comfort_settings WHERE guild_id = ?", (guild_id,))

    async def upsert_comfort_settings(self, guild_id: int, **kwargs: Any) -> None:
        existing = await self.get_comfort_settings(guild_id)
        if existing:
            keys = ", ".join(f"{k} = ?" for k in kwargs)
            await self.execute(f"UPDATE comfort_settings SET {keys} WHERE guild_id = ?", (*kwargs.values(), guild_id))
        else:
            cols = ", ".join(kwargs.keys())
            ph = ", ".join("?" for _ in kwargs)
            await self.execute(f"INSERT INTO comfort_settings (guild_id, {cols}) VALUES (?, {ph})", (guild_id, *kwargs.values()))

    async def add_temp_room(self, channel_id: int, guild_id: int, owner_id: int, category_id: int | None, panel_message_id: int | None = None) -> None:
        await self.execute("INSERT OR REPLACE INTO temp_rooms (channel_id, guild_id, owner_id, category_id, panel_message_id) VALUES (?, ?, ?, ?, ?)", (channel_id, guild_id, owner_id, category_id, panel_message_id))

    async def update_temp_room_panel(self, channel_id: int, panel_message_id: int) -> None:
        await self.execute("UPDATE temp_rooms SET panel_message_id = ? WHERE channel_id = ?", (panel_message_id, channel_id))

    async def update_temp_room_owner(self, channel_id: int, owner_id: int) -> None:
        await self.execute("UPDATE temp_rooms SET owner_id = ? WHERE channel_id = ?", (owner_id, channel_id))

    async def get_temp_room(self, channel_id: int):
        return await self.fetchone("SELECT * FROM temp_rooms WHERE channel_id = ?", (channel_id,))

    async def delete_temp_room(self, channel_id: int) -> None:
        await self.execute("DELETE FROM temp_rooms WHERE channel_id = ?", (channel_id,))

    async def get_user_temp_rooms(self, guild_id: int, owner_id: int):
        return await self.fetchall("SELECT * FROM temp_rooms WHERE guild_id = ? AND owner_id = ?", (guild_id, owner_id))

    async def get_all_temp_rooms(self):
        return await self.fetchall("SELECT * FROM temp_rooms")

    async def add_private_room(self, channel_id: int, guild_id: int, owner_id: int, panel_message_id: int | None = None) -> None:
        await self.execute("INSERT OR REPLACE INTO private_rooms (channel_id, guild_id, owner_id, panel_message_id) VALUES (?, ?, ?, ?)", (channel_id, guild_id, owner_id, panel_message_id))

    async def get_private_room(self, channel_id: int):
        return await self.fetchone("SELECT * FROM private_rooms WHERE channel_id = ?", (channel_id,))

    async def get_user_private_rooms(self, guild_id: int, owner_id: int):
        return await self.fetchall("SELECT * FROM private_rooms WHERE guild_id = ? AND owner_id = ?", (guild_id, owner_id))

    async def get_all_private_rooms(self):
        return await self.fetchall("SELECT * FROM private_rooms")

    async def delete_private_room(self, channel_id: int) -> None:
        await self.execute("DELETE FROM private_rooms WHERE channel_id = ?", (channel_id,))

    async def touch_private_room(self, channel_id: int) -> None:
        await self.execute("UPDATE private_rooms SET last_active = CURRENT_TIMESTAMP WHERE channel_id = ?", (channel_id,))

    async def get_afk(self, guild_id: int, user_id: int):
        return await self.fetchone("SELECT * FROM afk WHERE guild_id = ? AND user_id = ?", (guild_id, user_id))

    async def set_afk(self, guild_id: int, user_id: int, reason: str, old_nick: str | None) -> None:
        await self.execute("INSERT OR REPLACE INTO afk (guild_id, user_id, reason, old_nick) VALUES (?, ?, ?, ?)", (guild_id, user_id, reason, old_nick))

    async def remove_afk(self, guild_id: int, user_id: int):
        row = await self.get_afk(guild_id, user_id)
        if row:
            await self.execute("DELETE FROM afk WHERE guild_id = ? AND user_id = ?", (guild_id, user_id))
        return row

    async def get_economy(self, guild_id: int, user_id: int):
        return await self.fetchone("SELECT * FROM economy WHERE guild_id = ? AND user_id = ?", (guild_id, user_id))

    async def ensure_economy(self, guild_id: int, user_id: int) -> None:
        await self.execute("INSERT OR IGNORE INTO economy (guild_id, user_id) VALUES (?, ?)", (guild_id, user_id))

    async def add_money(self, guild_id: int, user_id: int, amount: int) -> None:
        await self.ensure_economy(guild_id, user_id)
        await self.execute("UPDATE economy SET balance = balance + ? WHERE guild_id = ? AND user_id = ?", (amount, guild_id, user_id))

    async def update_economy(self, guild_id: int, user_id: int, **kwargs: Any) -> None:
        await self.ensure_economy(guild_id, user_id)
        keys = ", ".join(f"{k} = ?" for k in kwargs)
        await self.execute(f"UPDATE economy SET {keys} WHERE guild_id = ? AND user_id = ?", (*kwargs.values(), guild_id, user_id))

    async def get_level(self, guild_id: int, user_id: int):
        return await self.fetchone("SELECT * FROM levels WHERE guild_id = ? AND user_id = ?", (guild_id, user_id))

    async def add_xp(self, guild_id: int, user_id: int, xp: int) -> tuple[int, int, bool]:
        row = await self.get_level(guild_id, user_id)
        if not row:
            await self.execute("INSERT INTO levels (guild_id, user_id, xp, level, messages) VALUES (?, ?, ?, 0, 1)", (guild_id, user_id, xp))
            return xp, 0, False
        new_xp = row["xp"] + xp
        level = row["level"]
        leveled = False
        while new_xp >= 5 * (level + 1) ** 2:
            new_xp -= 5 * (level + 1) ** 2
            level += 1
            leveled = True
        await self.execute("UPDATE levels SET xp = ?, level = ?, messages = messages + 1 WHERE guild_id = ? AND user_id = ?", (new_xp, level, guild_id, user_id))
        return new_xp, level, leveled

    async def get_settings(self, guild_id: int):
        return await self.fetchone("SELECT * FROM settings WHERE guild_id = ?", (guild_id,))

    async def set_mod_log(self, guild_id: int, channel_id: int) -> None:
        await self.execute("INSERT OR IGNORE INTO settings (guild_id) VALUES (?)", (guild_id,))
        await self.execute("UPDATE settings SET mod_log_channel = ? WHERE guild_id = ?", (channel_id, guild_id))

    async def get_bad_words(self, guild_id: int) -> list[str]:
        rows = await self.fetchall("SELECT word FROM bad_words WHERE guild_id = ?", (guild_id,))
        return [r["word"] for r in rows]

    async def add_bad_word(self, guild_id: int, word: str) -> None:
        await self.execute("INSERT OR IGNORE INTO bad_words (guild_id, word) VALUES (?, ?)", (guild_id, word.lower()))

    async def remove_bad_word(self, guild_id: int, word: str) -> None:
        await self.execute("DELETE FROM bad_words WHERE guild_id = ? AND word = ?", (guild_id, word.lower()))

    async def log_message(self, guild_id: int, channel_id: int, user_id: int) -> None:
        await self.execute("INSERT INTO message_log (guild_id, channel_id, user_id) VALUES (?, ?, ?)", (guild_id, channel_id, user_id))

    async def get_activity_by_day(self, guild_id: int, days: int = 7) -> list[tuple[str, int]]:
        rows = await self.fetchall("SELECT DATE(ts) AS day, COUNT(*) AS cnt FROM message_log WHERE guild_id = ? AND ts >= DATE('now', ?) GROUP BY DATE(ts) ORDER BY day", (guild_id, f"-{days} days"))
        return [(r["day"], r["cnt"]) for r in rows]

    async def cleanup_old_logs(self, days: int = 30) -> None:
        await self.execute("DELETE FROM message_log WHERE ts < DATE('now', ?)", (f"-{days} days",))

    async def save_snipe(self, channel_id: int, guild_id: int, message_id: int, author_id: int, author_name: str, content: str) -> None:
        await self.execute("INSERT OR REPLACE INTO snipe_cache (channel_id, guild_id, message_id, author_id, author_name, content) VALUES (?, ?, ?, ?, ?, ?)", (channel_id, guild_id, message_id, author_id, author_name, content[:1900]))

    async def get_snipe(self, channel_id: int):
        return await self.fetchone("SELECT * FROM snipe_cache WHERE channel_id = ?", (channel_id,))

    async def create_giveaway(self, message_id: int, guild_id: int, channel_id: int, prize: str, winners: int, host_id: int, end_at: str) -> None:
        await self.execute("INSERT OR REPLACE INTO giveaways (message_id, guild_id, channel_id, prize, winners, host_id, end_at) VALUES (?, ?, ?, ?, ?, ?, ?)", (message_id, guild_id, channel_id, prize, winners, host_id, end_at))

    async def get_giveaway(self, message_id: int):
        return await self.fetchone("SELECT * FROM giveaways WHERE message_id = ?", (message_id,))

    async def get_active_giveaways(self):
        return await self.fetchall("SELECT * FROM giveaways WHERE ended = 0")

    async def update_giveaway_participants(self, message_id: int, participants: str) -> None:
        await self.execute("UPDATE giveaways SET participants = ? WHERE message_id = ?", (participants, message_id))

    async def end_giveaway(self, message_id: int) -> None:
        await self.execute("UPDATE giveaways SET ended = 1 WHERE message_id = ?", (message_id,))

    async def create_poll(self, message_id: int, guild_id: int, channel_id: int, question: str, options_json: str) -> None:
        await self.execute("INSERT OR REPLACE INTO polls (message_id, guild_id, channel_id, question, options) VALUES (?, ?, ?, ?, ?)", (message_id, guild_id, channel_id, question, options_json))

    async def get_poll(self, message_id: int):
        return await self.fetchone("SELECT * FROM polls WHERE message_id = ?", (message_id,))

    async def get_all_polls(self):
        return await self.fetchall("SELECT * FROM polls")

    async def vote_poll(self, message_id: int, user_id: int, option_idx: int) -> None:
        await self.execute("INSERT OR REPLACE INTO poll_votes (message_id, user_id, option_idx) VALUES (?, ?, ?)", (message_id, user_id, option_idx))

    async def get_poll_votes(self, message_id: int) -> dict[int, list[int]]:
        rows = await self.fetchall("SELECT option_idx, user_id FROM poll_votes WHERE message_id = ?", (message_id,))
        result: dict[int, list[int]] = {}
        for r in rows:
            result.setdefault(r["option_idx"], []).append(r["user_id"])
        return result

    async def get_rules(self, guild_id: int):
        return await self.fetchone("SELECT * FROM guild_rules WHERE guild_id = ?", (guild_id,))

    async def set_rules(self, guild_id: int, channel_id: int, message_id: int, role_id: int, text: str) -> None:
        await self.execute("INSERT OR REPLACE INTO guild_rules (guild_id, channel_id, message_id, role_id, rules_text) VALUES (?, ?, ?, ?, ?)", (guild_id, channel_id, message_id, role_id, text))

    async def accept_rules(self, guild_id: int, user_id: int) -> None:
        await self.execute("INSERT OR IGNORE INTO rules_accepted (guild_id, user_id) VALUES (?, ?)", (guild_id, user_id))

    async def has_accepted_rules(self, guild_id: int, user_id: int) -> bool:
        row = await self.fetchone("SELECT 1 FROM rules_accepted WHERE guild_id = ? AND user_id = ?", (guild_id, user_id))
        return bool(row)

    async def create_suggestion(self, guild_id: int, channel_id: int, message_id: int, author_id: int, content: str) -> int:
        cur = await self.execute("INSERT INTO suggestions (guild_id, channel_id, message_id, author_id, content) VALUES (?, ?, ?, ?, ?)", (guild_id, channel_id, message_id, author_id, content))
        return cur.lastrowid  # type: ignore[return-value]

    async def get_suggestion(self, suggestion_id: int):
        return await self.fetchone("SELECT * FROM suggestions WHERE id = ?", (suggestion_id,))

    async def get_suggestion_by_message(self, message_id: int):
        return await self.fetchone("SELECT * FROM suggestions WHERE message_id = ?", (message_id,))

    async def vote_suggestion(self, suggestion_id: int, user_id: int, vote: int) -> None:
        await self.execute("INSERT OR REPLACE INTO suggestion_votes (suggestion_id, user_id, vote) VALUES (?, ?, ?)", (suggestion_id, user_id, vote))

    async def get_suggestion_votes(self, suggestion_id: int) -> dict[int, int]:
        rows = await self.fetchall("SELECT vote, COUNT(*) AS c FROM suggestion_votes WHERE suggestion_id = ? GROUP BY vote", (suggestion_id,))
        return {r["vote"]: r["c"] for r in rows}

    async def set_suggestion_status(self, suggestion_id: int, status: str) -> None:
        await self.execute("UPDATE suggestions SET status = ? WHERE id = ?", (status, suggestion_id))

    async def get_antiraid(self, guild_id: int):
        return await self.fetchone("SELECT * FROM antiraid_settings WHERE guild_id = ?", (guild_id,))

    async def set_antiraid(self, guild_id: int, **kwargs: Any) -> None:
        existing = await self.get_antiraid(guild_id)
        if existing:
            keys = ", ".join(f"{k} = ?" for k in kwargs)
            await self.execute(f"UPDATE antiraid_settings SET {keys} WHERE guild_id = ?", (*kwargs.values(), guild_id))
        else:
            cols = ", ".join(kwargs.keys())
            ph = ", ".join("?" for _ in kwargs)
            await self.execute(f"INSERT INTO antiraid_settings (guild_id, {cols}) VALUES (?, {ph})", (guild_id, *kwargs.values()))

    async def log_antiraid(self, guild_id: int, event: str, details: str = "") -> None:
        await self.execute("INSERT INTO antiraid_log (guild_id, event, details) VALUES (?, ?, ?)", (guild_id, event, details))
'''

FILES["utils/embeds.py"] = r'''"""Хелперы для embed."""
from __future__ import annotations

import discord

from config import BOT_VERSION, COLOR_ERROR, COLOR_PRIMARY, COLOR_SUCCESS, COLOR_WARNING


def base_embed(title: str | None = None, description: str | None = None, color: int = COLOR_PRIMARY) -> discord.Embed:
    embed = discord.Embed(title=title, description=description, color=color)
    embed.set_footer(text=f"ServerBuilder • v{BOT_VERSION}")
    return embed


def success_embed(description: str, title: str = "✅ Готово") -> discord.Embed:
    return base_embed(title=title, description=description, color=COLOR_SUCCESS)


def error_embed(description: str, title: str = "❌ Ошибка") -> discord.Embed:
    return base_embed(title=title, description=description, color=COLOR_ERROR)


def warning_embed(description: str, title: str = "⚠️ Внимание") -> discord.Embed:
    return base_embed(title=title, description=description, color=COLOR_WARNING)
'''

FILES["utils/checks.py"] = r'''"""Проверки прав."""
from __future__ import annotations

import discord
from discord import app_commands


def is_moderator() -> app_commands.check:
    async def predicate(interaction: discord.Interaction) -> bool:
        if not isinstance(interaction.user, discord.Member):
            raise app_commands.CheckFailure("Только на сервере.")
        if not interaction.user.guild_permissions.moderate_members:
            raise app_commands.CheckFailure("Нужно право «Модерировать участников».")
        return True
    return app_commands.check(predicate)


def is_admin() -> app_commands.check:
    async def predicate(interaction: discord.Interaction) -> bool:
        if not isinstance(interaction.user, discord.Member):
            raise app_commands.CheckFailure("Только на сервере.")
        if not interaction.user.guild_permissions.administrator:
            raise app_commands.CheckFailure("Нужно право «Администратор».")
        return True
    return app_commands.check(predicate)


def can_manage_guild() -> app_commands.check:
    async def predicate(interaction: discord.Interaction) -> bool:
        if not isinstance(interaction.user, discord.Member):
            raise app_commands.CheckFailure("Только на сервере.")
        if not interaction.user.guild_permissions.manage_guild:
            raise app_commands.CheckFailure("Нужно право «Управление сервером».")
        return True
    return app_commands.check(predicate)
'''

FILES["utils/errors.py"] = r'''"""Глобальный обработчик ошибок."""
from __future__ import annotations

import logging

import discord
from discord import app_commands
from discord.ext import commands

from utils.embeds import error_embed

log = logging.getLogger(__name__)


async def on_app_command_error(interaction: discord.Interaction, error: app_commands.AppCommandError) -> None:
    if isinstance(error, app_commands.CommandOnCooldown):
        msg = f"⏳ Через **{error.retry_after:.1f}** сек."
    elif isinstance(error, app_commands.MissingPermissions):
        msg = f"🔒 Нужны права: {', '.join(error.missing_permissions)}"
    elif isinstance(error, app_commands.BotMissingPermissions):
        msg = f"🤖 Боту нужны права: {', '.join(error.missing_permissions)}"
    elif isinstance(error, app_commands.CheckFailure):
        msg = f"❌ {error}"
    else:
        log.exception("Ошибка команды", exc_info=error)
        msg = "💥 Внутренняя ошибка."
    try:
        if interaction.response.is_done():
            await interaction.followup.send(embed=error_embed(msg), ephemeral=True)
        else:
            await interaction.response.send_message(embed=error_embed(msg), ephemeral=True)
    except discord.HTTPException:
        pass


async def on_command_error(ctx: commands.Context, error: commands.CommandError) -> None:
    if isinstance(error, commands.CommandNotFound):
        return
    log.exception("Ошибка префиксной команды", exc_info=error)
'''

FILES["Dockerfile"] = (
    "FROM python:3.11-slim\n\n"
    "ENV PYTHONUNBUFFERED=1 \\\n"
    "    PYTHONDONTWRITEBYTECODE=1 \\\n"
    "    PIP_NO_CACHE_DIR=1\n\n"
    "WORKDIR /app\n\n"
    "RUN apt-get update && apt-get install -y --no-install-recommends \\\n"
    "    libjpeg62-turbo libpng16-16 libfreetype6 \\\n"
    "    && rm -rf /var/lib/apt/lists/*\n\n"
    "COPY requirements.txt .\n"
    "RUN pip install --no-cache-dir -r requirements.txt\n\n"
    "COPY . .\n\n"
    "RUN useradd -m -u 1000 bot && chown -R bot:bot /app\n"
    "USER bot\n\n"
    'CMD ["python", "main.py"]\n'
)

FILES["docker-compose.yml"] = (
    'version: "3.9"\n\n'
    "services:\n"
    "  serverbuilder:\n"
    "    build: .\n"
    "    container_name: serverbuilder\n"
    "    restart: unless-stopped\n"
    "    env_file:\n"
    "      - .env\n"
    "    volumes:\n"
    "      - ./data:/app/data\n"
    "    logging:\n"
    "      driver: json-file\n"
    "      options:\n"
    '        max-size: "10m"\n'
    '        max-file: "3"\n'
)

# README через список строк — без triple-quotes, никаких проблем с парсингом
README_LINES = [
    "# ServerBuilder",
    "",
    "Полнофункциональный Discord-бот для создания и управления серверами.",
    "",
    "## Установка",
    "",
    "1. pip install -r requirements.txt",
    "2. Создайте .env (скопируйте .env.example), вставьте DISCORD_TOKEN",
    "3. python main.py",
    "",
    "## Права бота",
    "",
    "Manage Channels, Manage Roles, Move Members, Kick Members, Ban Members,",
    "Moderate Members, Manage Messages, Manage Nicknames, Embed Links,",
    "Read Message History, Send Messages, Use Application Commands.",
    "",
    "## Intents (Developer Portal > Bot)",
    "",
    "- MESSAGE CONTENT INTENT",
    "- SERVER MEMBERS INTENT",
    "- PRESENCE INTENT",
    "",
    "## Команды",
    "",
    "### Мастер",
    "- /start — создать сервер с нуля за 30 секунд",
    "",
    "### Аудит",
    "- /health — оценка сервера 0-100",
    "",
    "### Анти-рейд",
    "- /antiraid enable|disable|status|unlock|settings",
    "",
    "### Community",
    "- /rules — правила с принятием",
    "- /suggest — предложения",
    "- /suggestion-close",
    "",
    "### Модерация",
    "- /ban /kick /mute /unmute /warn /warnings /case",
    "- /clear /slowmode /lock /unlock",
    "- /automod /addword /removeword /listwords",
    "- /set-mod-logs",
    "",
    "### Welcome",
    "- /setwelcome /setgoodbye /setautorole /setwelcome-bg /setup-verify",
    "",
    "### Тикеты",
    "- /setup-tickets",
    "",
    "### Comfort",
    "- /room info|setup",
    "- /privateroom create|list|delete",
    "- /afk /remind /timer /bookmark /bookmarks",
    "- /snipe /purge-bots /move-all /status",
    "",
    "### Fun",
    "- /balance /daily /work /pay /deposit /withdraw",
    "- /leaderboard /rank /shop /addshop /buy",
    "- /8ball /coinflip /dice /trivia",
    "",
    "### Setup",
    "- /create-category /create-channel /create-role",
    "- /backup /restore /backup-export /backup-import",
    "",
    "### Reaction Roles",
    "- /reactionrole",
    "",
    "### Stats",
    "- /stats /activity-chart /audit",
    "",
    "### Giveaways",
    "- /giveaway",
    "",
    "## Docker",
    "",
    "    docker compose up -d --build",
    "    docker compose logs -f",
]

# ── Заглушки cog'ов ──
COG_STUB = r'''"""Заглушка. Запустите build_cogs.py для наполнения."""
from __future__ import annotations

import discord
from discord.ext import commands


class Placeholder(commands.Cog):
    def __init__(self, bot: commands.Bot) -> None:
        self.bot = bot


async def setup(bot: commands.Bot) -> None:
    await bot.add_cog(Placeholder(bot))
'''

COG_NAMES = [
    "wizard", "moderation", "welcome", "utility", "setup", "comfort",
    "tickets", "fun", "reaction_roles", "stats", "giveaways",
    "health", "antiraid", "community",
]

EMPTY_FILES = [
    "database/__init__.py",
    "cogs/__init__.py",
    "utils/__init__.py",
    "assets/.gitkeep",
    "data/.gitkeep",
    "backups/.gitkeep",
]


def write_file(rel: str, content: str, overwrite: bool) -> None:
    path = BASE / rel
    path.parent.mkdir(parents=True, exist_ok=True)
    if path.exists() and not overwrite:
        print(f"  [skip] {rel}")
        return
    path.write_text(content, encoding="utf-8")
    print(f"  [ok]   {rel}")


def main() -> None:
    print(f"Project: {BASE}\n")

    print("Folders:")
    for folder in FOLDERS:
        (BASE / folder).mkdir(parents=True, exist_ok=True)
        print(f"  [ok]   {folder}/")

    print("\nBase files:")
    for rel, content in FILES.items():
        write_file(rel, content, OVERWRITE_BASE)

    print("\nREADME.md:")
    write_file("README.md", "\n".join(README_LINES) + "\n", OVERWRITE_BASE)

    print("\nEmpty files:")
    for rel in EMPTY_FILES:
        write_file(rel, "", OVERWRITE_BASE)

    print("\nCog stubs:")
    for name in COG_NAMES:
        write_file(f"cogs/{name}.py", COG_STUB, OVERWRITE_COGS)

    print("\n" + "=" * 50)
    print("DONE. Структура готова!")
    print("=" * 50)
    print("\nNext:")
    print("  1. python build_cogs.py  (наполнит коги)")
    print("  2. Создайте .env с токеном")
    print("  3. python main.py")


if __name__ == "__main__":
    main()
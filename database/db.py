"""Асинхронный слой БД."""
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

"""Конфигурация бота."""
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

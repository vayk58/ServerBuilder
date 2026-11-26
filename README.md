# ServerBuilder

Полнофункциональный Discord-бот для создания и управления серверами.

## Установка

1. `pip install -r requirements.txt`
2. Создайте `.env` на основе `.env.example` и укажите `DISCORD_TOKEN`.
3. Запустите `python main.py`.

## Права бота

Manage Channels, Manage Roles, Move Members, Kick Members, Ban Members,
Moderate Members, Manage Messages, Manage Nicknames, Embed Links,
Read Message History, Send Messages, Use Application Commands.

## Intents (Developer Portal > Bot)

- MESSAGE CONTENT INTENT
- SERVER MEMBERS INTENT
- PRESENCE INTENT

## Приложение и команды

`/panel` открывает интерактивное приватное меню с разделами: создание сервера, сообщество, безопасность, развлечения и инструменты.

### Создание сервера
- `/start` — мастер создания сервера по шаблону.
- `/serveridea` — план каналов, ролей и первого события для выбранной тематики.
- `/health` — аудит настроек сервера.
- `/create-category`, `/create-channel`, `/create-role` — оформление структуры.
- `/backup`, `/backup-export`, `/backup-import` — резервные копии.

### Сообщество и полезные инструменты
- `/rules`, `/suggest`, `/poll`, `/setup-tickets` — правила, предложения, опросы и поддержка.
- `/setwelcome`, `/reactionrole` — приветствие и роли.
- `/serverinfo`, `/userinfo`, `/avatar`, `/banner`, `/roleinfo` — информация о сервере и участниках.
- `/remind`, `/bookmark`, `/stats`, `/activity-chart` — повседневные инструменты и статистика.
- `/icebreaker` — случайная тема для начала разговора.

### Безопасность и модерация
- `/ban`, `/kick`, `/mute`, `/unmute`, `/warn`, `/warnings`, `/case`.
- `/clear`, `/slowmode`, `/lock`, `/unlock`, `/automod`, `/antiraid`.
- `/set-mod-logs` — канал журналов модерации.

### Развлечения
- `/8ball`, `/coinflip`, `/dice`, `/trivia` — мини-игры.
- `/daily`, `/work`, `/pay`, `/deposit`, `/withdraw`, `/balance` — экономика.
- `/rank`, `/leaderboard`, `/shop`, `/buy` — уровни и магазин.
- `/giveaway` — розыгрыш.

## Docker

```bash
docker compose up -d --build
docker compose logs -f
```

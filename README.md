# ServerBuilder

Полнофункциональный Discord-бот для создания и управления серверами.

## Установка

1. pip install -r requirements.txt
2. Создайте .env (скопируйте .env.example), вставьте DISCORD_TOKEN
3. python main.py

## Права бота

Manage Channels, Manage Roles, Move Members, Kick Members, Ban Members,
Moderate Members, Manage Messages, Manage Nicknames, Embed Links,
Read Message History, Send Messages, Use Application Commands.

## Intents (Developer Portal > Bot)

- MESSAGE CONTENT INTENT
- SERVER MEMBERS INTENT
- PRESENCE INTENT

## Команды

### Мастер
- /start — создать сервер с нуля за 30 секунд

### Аудит
- /health — оценка сервера 0-100

### Анти-рейд
- /antiraid enable|disable|status|unlock|settings

### Community
- /rules — правила с принятием
- /suggest — предложения
- /suggestion-close

### Модерация
- /ban /kick /mute /unmute /warn /warnings /case
- /clear /slowmode /lock /unlock
- /automod /addword /removeword /listwords
- /set-mod-logs

### Welcome
- /setwelcome /setgoodbye /setautorole /setwelcome-bg /setup-verify

### Тикеты
- /setup-tickets

### Comfort
- /room info|setup
- /privateroom create|list|delete
- /afk /remind /timer /bookmark /bookmarks
- /snipe /purge-bots /move-all /status

### Fun
- /balance /daily /work /pay /deposit /withdraw
- /leaderboard /rank /shop /addshop /buy
- /8ball /coinflip /dice /trivia

### Setup
- /create-category /create-channel /create-role
- /backup /restore /backup-export /backup-import

### Reaction Roles
- /reactionrole

### Stats
- /stats /activity-chart /audit

### Giveaways
- /giveaway

## Docker

    docker compose up -d --build
    docker compose logs -f

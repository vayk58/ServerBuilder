"""Интерактивная панель ServerBuilder и идеи для сервера."""
from __future__ import annotations

import random

import discord
from discord import app_commands
from discord.ext import commands

from utils.embeds import base_embed

SECTIONS: dict[str, tuple[str, str, str]] = {
    "create": (
        "🧱 Создание сервера",
        "Соберите основу сервера и оформите структуру.",
        "`/start` — мастер создания сервера\n`/serveridea` — готовая идея структуры\n`/create-category` — создать категорию\n`/create-channel` — создать канал\n`/create-role` — создать роль\n`/backup` и `/backup-export` — сохранить структуру\n`/health` — проверить настройки сервера",
    ),
    "community": (
        "💬 Сообщество",
        "Инструменты для участников и общения.",
        "`/rules` — правила и кнопка принятия\n`/suggest` — предложить идею\n`/poll` — интерактивный опрос\n`/setup-tickets` — настроить поддержку\n`/setwelcome` — приветствие\n`/reactionrole` — роли по реакциям\n`/icebreaker` — тема для разговора",
    ),
    "moderation": (
        "🛡️ Порядок и безопасность",
        "Настройте защиту и инструменты модерации.",
        "`/ban`, `/kick`, `/mute` — управление участниками\n`/warn` и `/warnings` — предупреждения\n`/clear` — очистка сообщений\n`/automod` — автомодерация\n`/antiraid` — защита от рейдов\n`/set-mod-logs` — журнал модерации",
    ),
    "fun": (
        "🎮 Развлечения",
        "Мини-игры, уровни и активность сообщества.",
        "`/8ball` — магический шар\n`/coinflip` и `/dice` — быстрые игры\n`/trivia` — викторина с наградой\n`/daily` и `/work` — монеты\n`/rank` и `/leaderboard` — уровни и таблица лидеров\n`/giveaway` — розыгрыш",
    ),
    "tools": (
        "🧰 Полезные инструменты",
        "Информация о сервере и участниках.",
        "`/serverinfo` — информация о сервере\n`/userinfo` — информация об участнике\n`/avatar` и `/banner` — изображения профиля\n`/roleinfo` — информация о роли\n`/remind` и `/bookmark` — напоминания и закладки\n`/stats` и `/activity-chart` — статистика",
    ),
}

SERVER_IDEAS: dict[str, dict[str, object]] = {
    "gaming": {
        "title": "🎮 Игровое сообщество",
        "channels": "📢 информация: `правила`, `анонсы`, `роли`\n🎮 игры: `общий`, `поиск-команды`, `медиа`\n🔊 голосовые: `лобби`, `комната 1`, `комната 2`\n🏆 активность: `ивенты`, `результаты`",
        "roles": "`Игрок`, `Ищу команду`, `Стример`, `Модератор`",
        "event": "вечер совместной игры с голосованием за игру недели",
    },
    "community": {
        "title": "💬 Дружное сообщество",
        "channels": "📢 старт: `правила`, `знакомство`, `объявления`\n💬 общение: `общий`, `вопросы`, `медиа`, `мемы`\n🎫 помощь: `поддержка`, `предложения`\n🔊 голосовые: `общая`, `тихая комната`",
        "roles": "`Участник`, `Новичок`, `Организатор`, `Модератор`",
        "event": "еженедельный вопрос дня и голосование за лучшее предложение",
    },
    "study": {
        "title": "📚 Учёба и взаимопомощь",
        "channels": "📢 старт: `правила`, `расписание`, `объявления`\n📚 предметы: `математика`, `языки`, `другие-предметы`\n📝 материалы: `конспекты`, `полезные-ссылки`\n🔊 фокус: `совместная-учёба`, `перерыв`",
        "roles": "`Ученик`, `Наставник`, `Предмет: ...`, `Модератор`",
        "event": "тихий совместный учебный час с коротким перерывом и итогами",
    },
    "business": {
        "title": "💼 Команда или проект",
        "channels": "📢 информация: `правила`, `новости`, `онбординг`\n💼 работа: `общий`, `задачи`, `идеи`, `результаты`\n🎫 запросы: `поддержка`, `заявки`\n🔊 встречи: `переговорная`, `комната команды`",
        "roles": "`Команда`, `Клиент`, `Менеджер`, `Модератор`",
        "event": "короткая еженедельная встреча: победы, планы и одна главная задача",
    },
    "creative": {
        "title": "🎨 Творческая мастерская",
        "channels": "📢 старт: `правила`, `анонсы`, `знакомство`\n🎨 творчество: `галерея`, `процесс`, `обратная-связь`\n🎵 сцена: `музыка`, `идеи`, `коллаборации`\n🔊 голосовые: `мастерская`, `лаунж`",
        "roles": "`Художник`, `Музыкант`, `Автор`, `Критик-конструктивно`",
        "event": "творческий челлендж недели с добровольной темой и доброй обратной связью",
    },
}

ICEBREAKERS = [
    "Какую игру, книгу или сериал ты бы хотел забыть, чтобы пройти или посмотреть заново?",
    "Какой навык ты бы освоил мгновенно, если бы это было возможно?",
    "Как выглядит твой идеальный выходной?",
    "Какую песню ты готов слушать на повторе?",
    "Какое маленькое событие недавно подняло тебе настроение?",
    "Если бы у нашего сервера был талисман, кто или что это было бы?",
    "Какую тему ты можешь обсуждать часами?",
    "Какое место ты мечтаешь посетить и почему?",
]


class SectionSelect(discord.ui.Select):
    def __init__(self) -> None:
        super().__init__(
            placeholder="Выберите раздел",
            min_values=1,
            max_values=1,
            options=[
                discord.SelectOption(label=title, value=key, description=description)
                for key, (title, description, _) in SECTIONS.items()
            ],
        )

    async def callback(self, interaction: discord.Interaction) -> None:
        key = self.values[0]
        title, description, commands_text = SECTIONS[key]
        embed = base_embed(title=title, description=description)
        embed.add_field(name="Команды", value=commands_text, inline=False)
        embed.set_footer(text="ServerBuilder • выберите другой раздел в меню")
        await interaction.response.edit_message(embed=embed, view=self.view)


class DashboardView(discord.ui.View):
    def __init__(self, owner_id: int) -> None:
        super().__init__(timeout=180)
        self.owner_id = owner_id
        self.add_item(SectionSelect())

    async def interaction_check(self, interaction: discord.Interaction) -> bool:
        if interaction.user.id != self.owner_id:
            await interaction.response.send_message(
                "Эта панель открыта другим участником. Вызовите `/panel`, чтобы открыть свою.",
                ephemeral=True,
            )
            return False
        return True


class Dashboard(commands.Cog):
    def __init__(self, bot: commands.Bot) -> None:
        self.bot = bot

    @app_commands.command(name="panel", description="Открыть меню ServerBuilder по разделам")
    async def panel(self, interaction: discord.Interaction) -> None:
        embed = base_embed(
            title="✨ ServerBuilder — центр управления",
            description=(
                "Выберите раздел в меню ниже: создание сервера, сообщество, безопасность, "
                "развлечения или полезные инструменты.\n\n"
                "Начните с `/start`, чтобы собрать сервер по шаблону, или откройте `/health`, "
                "чтобы проверить настройки."
            ),
        )
        embed.add_field(
            name="🚀 Быстрый старт",
            value="`/start` · мастер сервера  |  `/serveridea` · идея структуры  |  `/health` · аудит",
            inline=False,
        )
        embed.set_footer(text="Меню доступно только вам • ServerBuilder")
        await interaction.response.send_message(
            embed=embed, view=DashboardView(interaction.user.id), ephemeral=True
        )

    @app_commands.command(name="serveridea", description="Получить идею структуры Discord-сервера")
    @app_commands.choices(server_type=[
        app_commands.Choice(name="Игровое сообщество", value="gaming"),
        app_commands.Choice(name="Дружное сообщество", value="community"),
        app_commands.Choice(name="Учёба", value="study"),
        app_commands.Choice(name="Команда или проект", value="business"),
        app_commands.Choice(name="Творческая мастерская", value="creative"),
    ])
    async def serveridea(self, interaction: discord.Interaction, server_type: str) -> None:
        idea = SERVER_IDEAS[server_type]
        embed = base_embed(title=str(idea["title"]), description="Готовый план — адаптируйте его под своё сообщество.")
        embed.add_field(name="🗂️ Каналы и категории", value=str(idea["channels"]), inline=False)
        embed.add_field(name="🎭 Идеи ролей", value=str(idea["roles"]), inline=False)
        embed.add_field(name="🎉 Идея для первого события", value=str(idea["event"]), inline=False)
        embed.set_footer(text="Чтобы создать структуру автоматически, запустите `/start` и выберите шаблон.")
        await interaction.response.send_message(embed=embed, ephemeral=True)

    @app_commands.command(name="icebreaker", description="Случайная тема, чтобы начать разговор")
    async def icebreaker(self, interaction: discord.Interaction) -> None:
        await interaction.response.send_message(
            embed=base_embed(title="🧊 Тема для разговора", description=random.choice(ICEBREAKERS))
        )


async def setup(bot: commands.Bot) -> None:
    await bot.add_cog(Dashboard(bot))

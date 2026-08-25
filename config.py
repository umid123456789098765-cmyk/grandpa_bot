import os

# Токен бота от @BotFather. Задаётся через переменную окружения BOT_TOKEN,
# либо впишите его прямо сюда вместо "".
BOT_TOKEN = os.environ.get("BOT_TOKEN", "8845184206:AAFgxY5TiapgtkXFByVovPnyQdMkZHDYdqc")

# Путь к файлу базы данных SQLite
DB_PATH = os.path.join(os.path.dirname(__file__), "grandpa_bot.db")

# Через сколько часов молчания дедушки бот напишет родным ("проверка активности")
SILENCE_ALERT_HOURS = 20

# Во сколько (час, 0-23, по времени сервера) слать ежедневный вопрос "Как дела?"
DAILY_CHECKIN_HOUR = 10
DAILY_CHECKIN_MINUTE = 0

# Как часто (в минутах) проверять и рассылать напоминания
REMINDER_CHECK_INTERVAL_MINUTES = 1

# ---------- Обязательная подписка на канал ----------
# Username вашего канала (с собачкой) — бот проверяет, состоит ли в нём пользователь.
# Бот должен быть добавлен в этот канал АДМИНИСТРАТОРОМ, иначе проверка не сработает.
REQUIRED_CHANNEL_USERNAME = os.environ.get("REQUIRED_CHANNEL_USERNAME", "@dasturchi_log")

# Ссылка на канал, которую увидит пользователь (кнопка "Подписаться")
REQUIRED_CHANNEL_URL = os.environ.get("REQUIRED_CHANNEL_URL", "https://t.me/dasturchi_log")

# Текст, который бот покажет ПОСЛЕ того, как пользователь подписался
AFTER_SUBSCRIBE_MESSAGE = (
    "Спасибо за подписку! 🎉 Теперь вам доступны все возможности бота."
)

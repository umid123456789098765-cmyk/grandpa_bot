from telegram import ReplyKeyboardMarkup, KeyboardButton

# Крупные, понятные кнопки для дедушки — вместо мелких /команд
BTN_REMIND_ADD = "⏰ Добавить напоминание"
BTN_REMIND_LIST = "📋 Мои напоминания"
BTN_FAMILY_CALL = "📞 Позвонить внукам"
BTN_HOW_I_AM = "🙂 Как я себя чувствую"
BTN_HELP = "❓ Помощь"

SENIOR_KEYBOARD = ReplyKeyboardMarkup(
    [
        [KeyboardButton(BTN_REMIND_ADD)],
        [KeyboardButton(BTN_REMIND_LIST)],
        [KeyboardButton(BTN_FAMILY_CALL)],
        [KeyboardButton(BTN_HOW_I_AM)],
        [KeyboardButton(BTN_HELP)],
    ],
    resize_keyboard=True,
    one_time_keyboard=False,
)

# Кнопки для родственника (второй "профиль" бота)
BTN_LINK = "🔗 Привязать бабушку/дедушку по коду"
BTN_MY_SENIORS = "👴 Мои подопечные"

FAMILY_KEYBOARD = ReplyKeyboardMarkup(
    [
        [KeyboardButton(BTN_LINK)],
        [KeyboardButton(BTN_MY_SENIORS)],
    ],
    resize_keyboard=True,
    one_time_keyboard=False,
)

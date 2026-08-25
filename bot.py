import logging

from telegram import Update
from telegram.ext import (
    Application, ApplicationBuilder, CommandHandler, MessageHandler,
    CallbackQueryHandler, ConversationHandler, ContextTypes, filters,
)

import database as db
import handlers as h
from keyboards import (
    BTN_REMIND_ADD, BTN_REMIND_LIST, BTN_FAMILY_CALL, BTN_HOW_I_AM, BTN_HELP,
    BTN_LINK, BTN_MY_SENIORS,
)
from scheduler import register_jobs
from config import BOT_TOKEN

logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s", level=logging.INFO
)
logger = logging.getLogger(__name__)


def build_application() -> Application:
    db.init_db()
    application = ApplicationBuilder().token(BOT_TOKEN).build()

    application.add_handler(CommandHandler("start", h.start))
    application.add_handler(CommandHandler("help", h.help_command))
    application.add_handler(CallbackQueryHandler(h.role_chosen, pattern="^role_"))
    application.add_handler(CallbackQueryHandler(h.check_subscription_callback, pattern="^check_sub$"))

    reminder_conv = ConversationHandler(
        entry_points=[MessageHandler(filters.Regex(f"^{BTN_REMIND_ADD}$"), h.reminder_add_start)],
        states={
            h.ASK_REMINDER_TEXT: [MessageHandler(filters.TEXT & ~filters.COMMAND, h.reminder_add_text)],
            h.ASK_REMINDER_TIME: [MessageHandler(filters.TEXT & ~filters.COMMAND, h.reminder_add_time)],
        },
        fallbacks=[CommandHandler("cancel", h.cancel_conversation)],
    )
    application.add_handler(reminder_conv)

    link_conv = ConversationHandler(
        entry_points=[MessageHandler(filters.Regex(f"^{BTN_LINK}$"), h.link_start)],
        states={
            h.ASK_LINK_CODE: [MessageHandler(filters.TEXT & ~filters.COMMAND, h.link_code_entered)],
        },
        fallbacks=[CommandHandler("cancel", h.cancel_conversation)],
    )
    application.add_handler(link_conv)

    mood_conv = ConversationHandler(
        entry_points=[MessageHandler(filters.Regex(f"^{BTN_HOW_I_AM}$"), h.mood_start)],
        states={
            h.ASK_MOOD: [MessageHandler(filters.TEXT & ~filters.COMMAND, h.mood_received)],
        },
        fallbacks=[CommandHandler("cancel", h.cancel_conversation)],
    )
    application.add_handler(mood_conv)

    application.add_handler(MessageHandler(filters.Regex(f"^{BTN_REMIND_LIST}$"), h.reminder_list))
    application.add_handler(MessageHandler(filters.Regex(f"^{BTN_FAMILY_CALL}$"), h.family_call))
    application.add_handler(MessageHandler(filters.Regex(f"^{BTN_HELP}$"), h.help_command))
    application.add_handler(MessageHandler(filters.Regex(f"^{BTN_MY_SENIORS}$"), h.my_seniors))

    # Обычные сообщения — простое общение / удаление напоминаний по номеру
    application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, h.free_text))

    register_jobs(application)
    return application


def main():
    if not BOT_TOKEN:
        raise SystemExit(
            "Не задан токен бота. Установите переменную окружения BOT_TOKEN "
            "(получите токен у @BotFather в Telegram) или впишите его в config.py"
        )
    application = build_application()
    logger.info("Бот запущен")
    application.run_polling(allowed_updates=Update.ALL_TYPES)


if __name__ == "__main__":
    main()

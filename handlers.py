import re
import random
import logging
import functools

from telegram import Update, InlineKeyboardMarkup, InlineKeyboardButton
from telegram.error import TelegramError
from telegram.ext import ContextTypes, ConversationHandler

import database as db
from keyboards import (
    SENIOR_KEYBOARD, FAMILY_KEYBOARD,
    BTN_REMIND_ADD, BTN_REMIND_LIST, BTN_FAMILY_CALL, BTN_HOW_I_AM, BTN_HELP,
    BTN_LINK, BTN_MY_SENIORS,
)
from config import REQUIRED_CHANNEL_USERNAME, REQUIRED_CHANNEL_URL, AFTER_SUBSCRIBE_MESSAGE

logger = logging.getLogger(__name__)

# Состояния диалогов
ASK_REMINDER_TEXT, ASK_REMINDER_TIME = range(2)
ASK_LINK_CODE = 10
ASK_MOOD = 20

TIME_RE = re.compile(r"^\s*(\d{1,2})[:.\s](\d{2})\s*$")

CHAT_REPLIES = [
    "Понимаю вас! Расскажите ещё?",
    "Это интересно. Как ваше настроение сегодня?",
    "Хорошо вас слышу. Чем ещё могу помочь?",
    "Спасибо, что написали! Я всегда рад(а) пообщаться.",
    "Берегите себя. Не забывайте пить воду и отдыхать 🙂",
]


def _mark_active(update: Update):
    user = update.effective_user
    if user:
        db.touch_activity(user.id)


# ---------- Обязательная подписка на канал ----------

def _subscribe_gate_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        [
            [InlineKeyboardButton("📢 Подписаться на канал", url=REQUIRED_CHANNEL_URL)],
            [InlineKeyboardButton("✅ Я подписался", callback_data="check_sub")],
        ]
    )


async def is_subscribed(bot, user_id: int) -> bool:
    """Проверяет, состоит ли пользователь в обязательном канале."""
    try:
        member = await bot.get_chat_member(REQUIRED_CHANNEL_USERNAME, user_id)
        return member.status in ("member", "administrator", "creator")
    except TelegramError:
        logger.exception(
            "Не удалось проверить подписку (бот должен быть админом канала %s)",
            REQUIRED_CHANNEL_USERNAME,
        )
        # Если проверить не получилось (например, бот не админ канала) — не блокируем пользователя
        return True


async def send_subscribe_gate(update: Update):
    await update.effective_message.reply_text(
        "Чтобы пользоваться ботом, сначала подпишитесь на наш канал 👇",
        reply_markup=_subscribe_gate_keyboard(),
    )


def require_subscription(handler_func):
    """Декоратор: не пускает в обработчик, пока пользователь не подписан на канал."""

    @functools.wraps(handler_func)
    async def wrapper(update: Update, context: ContextTypes.DEFAULT_TYPE, *args, **kwargs):
        user = update.effective_user
        if user and not await is_subscribed(context.bot, user.id):
            await send_subscribe_gate(update)
            return ConversationHandler.END
        return await handler_func(update, context, *args, **kwargs)

    return wrapper


async def check_subscription_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    user = query.from_user

    if not await is_subscribed(context.bot, user.id):
        await query.answer("Пока не вижу подписку. Подпишитесь и нажмите кнопку ещё раз.", show_alert=True)
        return

    await query.edit_message_text(AFTER_SUBSCRIBE_MESSAGE)
    await start_after_subscription(update, context, user)


async def start_after_subscription(update: Update, context: ContextTypes.DEFAULT_TYPE, user):
    """Показывает выбор роли / главное меню — используется и в /start, и после подписки."""
    existing = db.get_user(user.id)
    if existing:
        kb = SENIOR_KEYBOARD if existing["is_senior"] else FAMILY_KEYBOARD
        await context.bot.send_message(
            chat_id=user.id,
            text=f"С возвращением, {existing['name']}! Выберите действие на клавиатуре ниже.",
            reply_markup=kb,
        )
        return

    keyboard = InlineKeyboardMarkup(
        [
            [InlineKeyboardButton("👴 Я бабушка/дедушка", callback_data="role_senior")],
            [InlineKeyboardButton("👨‍👩‍👧 Я родственник", callback_data="role_family")],
        ]
    )
    await context.bot.send_message(
        chat_id=user.id,
        text="Здравствуйте! Это бот-помощник для пожилых людей и их родных.\n\n"
        "Подскажите, пожалуйста, кто вы?",
        reply_markup=keyboard,
    )


# ---------- /start и выбор роли ----------

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    if not await is_subscribed(context.bot, user.id):
        await send_subscribe_gate(update)
        return
    await start_after_subscription(update, context, user)


async def role_chosen(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    user = query.from_user
    is_senior = query.data == "role_senior"
    db.upsert_user(user.id, user.first_name or "Друг", is_senior=is_senior)

    if is_senior:
        db.touch_activity(user.id)
        await query.edit_message_text(
            "Отлично! Я буду напоминать вам о важном и всегда на связи.\n\n"
            "Внизу экрана — большие кнопки. Нажимайте любую из них."
        )
        await context.bot.send_message(
            chat_id=user.id,
            text="Вот что я умею 👇",
            reply_markup=SENIOR_KEYBOARD,
        )
    else:
        await query.edit_message_text(
            "Хорошо! Чтобы подключиться к вашей бабушке или дедушке, "
            "попросите их отправить вам код через кнопку «Позвонить внукам», "
            "либо командой /код в их боте — и введите его здесь через "
            f"«{BTN_LINK}»."
        )
        await context.bot.send_message(
            chat_id=user.id,
            text="Вот что доступно вам 👇",
            reply_markup=FAMILY_KEYBOARD,
        )


# ---------- Напоминания ----------

@require_subscription
async def reminder_add_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    _mark_active(update)
    await update.message.reply_text(
        "О чём вам напомнить? Напишите текст напоминания.\n"
        "Например: «Выпить таблетку от давления»"
    )
    return ASK_REMINDER_TEXT


async def reminder_add_text(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data["new_reminder_text"] = update.message.text.strip()
    await update.message.reply_text(
        "В какое время каждый день напоминать? Напишите время в формате ЧЧ:ММ\n"
        "Например: 09:00"
    )
    return ASK_REMINDER_TIME


async def reminder_add_time(update: Update, context: ContextTypes.DEFAULT_TYPE):
    match = TIME_RE.match(update.message.text)
    if not match:
        await update.message.reply_text(
            "Не совсем поняла время. Пожалуйста, напишите так: 09:00"
        )
        return ASK_REMINDER_TIME

    hour, minute = int(match.group(1)), int(match.group(2))
    if not (0 <= hour <= 23 and 0 <= minute <= 59):
        await update.message.reply_text("Время должно быть от 00:00 до 23:59. Попробуйте ещё раз.")
        return ASK_REMINDER_TIME

    text = context.user_data.pop("new_reminder_text")
    user = update.effective_user
    db.add_reminder(user.id, text, hour, minute)
    await update.message.reply_text(
        f"Готово! Каждый день в {hour:02d}:{minute:02d} я напомню: «{text}»",
        reply_markup=SENIOR_KEYBOARD,
    )
    return ConversationHandler.END


async def cancel_conversation(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = db.get_user(update.effective_user.id)
    kb = SENIOR_KEYBOARD if (not user or user["is_senior"]) else FAMILY_KEYBOARD
    await update.message.reply_text("Хорошо, отменил(а).", reply_markup=kb)
    return ConversationHandler.END


@require_subscription
async def reminder_list(update: Update, context: ContextTypes.DEFAULT_TYPE):
    _mark_active(update)
    reminders = db.list_reminders(update.effective_user.id)
    if not reminders:
        await update.message.reply_text("У вас пока нет напоминаний.")
        return
    lines = [f"{r['hour']:02d}:{r['minute']:02d} — {r['text']} (номер {r['id']})" for r in reminders]
    await update.message.reply_text(
        "Ваши напоминания:\n" + "\n".join(lines) +
        "\n\nЧтобы удалить, напишите: удалить 12 (где 12 — номер напоминания)"
    )


async def reminder_delete_by_text(update: Update, context: ContextTypes.DEFAULT_TYPE):
    match = re.match(r"^удалить\s+(\d+)$", update.message.text.strip().lower())
    if not match:
        return False
    reminder_id = int(match.group(1))
    ok = db.delete_reminder(reminder_id, update.effective_user.id)
    if ok:
        await update.message.reply_text("Напоминание удалено.")
    else:
        await update.message.reply_text("Не нашла такое напоминание.")
    return True


# ---------- Связь с семьёй ----------

@require_subscription
async def family_call(update: Update, context: ContextTypes.DEFAULT_TYPE):
    _mark_active(update)
    user = update.effective_user
    family_ids = db.get_family_for_senior(user.id)
    senior = db.get_user(user.id)
    name = senior["name"] if senior else user.first_name

    if not family_ids:
        code = db.create_link_code(user.id)
        await update.message.reply_text(
            "Пока к вам не привязан ни один родственник.\n\n"
            f"Дайте им этот код, пусть введут его в своём боте: {code}"
        )
        return

    for fid in family_ids:
        try:
            await context.bot.send_message(
                chat_id=fid,
                text=f"📞 {name} хочет с вами связаться! Позвоните, когда сможете.",
            )
        except Exception:
            logger.exception("Не удалось отправить сообщение родственнику %s", fid)

    await update.message.reply_text("Я передал(а) родным, что вы хотите поговорить 🙂")


@require_subscription
async def link_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("Введите код, который вам дал(а) бабушка/дедушка:")
    return ASK_LINK_CODE


async def link_code_entered(update: Update, context: ContextTypes.DEFAULT_TYPE):
    code = update.message.text
    user = update.effective_user
    senior_id = db.use_link_code(code, user.id)
    if senior_id is None:
        await update.message.reply_text("Такой код не найден. Проверьте и попробуйте снова, либо /cancel.")
        return ASK_LINK_CODE

    senior = db.get_user(senior_id)
    senior_name = senior["name"] if senior else "ваш родственник"
    await update.message.reply_text(
        f"Готово! Вы привязаны к {senior_name}. Теперь я сообщу вам, если он(а) захочет "
        "поговорить или долго не будет на связи.",
        reply_markup=FAMILY_KEYBOARD,
    )
    try:
        await context.bot.send_message(
            chat_id=senior_id,
            text=f"👨‍👩‍👧 {update.effective_user.first_name} теперь на связи с вами через бота!",
        )
    except Exception:
        logger.exception("Не удалось уведомить дедушку/бабушку о привязке")
    return ConversationHandler.END


@require_subscription
async def my_seniors(update: Update, context: ContextTypes.DEFAULT_TYPE):
    seniors = db.get_seniors_for_family(update.effective_user.id)
    if not seniors:
        await update.message.reply_text(
            f"Пока никто не привязан. Нажмите «{BTN_LINK}», чтобы добавить."
        )
        return
    names = []
    for sid in seniors:
        u = db.get_user(sid)
        names.append(u["name"] if u else str(sid))
    await update.message.reply_text("Ваши подопечные:\n" + "\n".join(names))


# ---------- Самочувствие / чат ----------

@require_subscription
async def mood_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    _mark_active(update)
    await update.message.reply_text("Как вы себя чувствуете сегодня? Напишите пару слов.")
    return ASK_MOOD


async def mood_received(update: Update, context: ContextTypes.DEFAULT_TYPE):
    _mark_active(update)
    user = update.effective_user
    senior = db.get_user(user.id)
    name = senior["name"] if senior else user.first_name
    mood_text = update.message.text.strip()

    await update.message.reply_text("Спасибо, что поделились! Берегите себя 🙂", reply_markup=SENIOR_KEYBOARD)

    for fid in db.get_family_for_senior(user.id):
        try:
            await context.bot.send_message(
                chat_id=fid,
                text=f"🙂 {name} сообщил(а) о самочувствии: «{mood_text}»",
            )
        except Exception:
            logger.exception("Не удалось отправить самочувствие родственнику %s", fid)
    return ConversationHandler.END


@require_subscription
async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = db.get_user(update.effective_user.id)
    if user and not user["is_senior"]:
        await update.message.reply_text(
            "Я слежу за вашим родственником и сообщаю вам:\n"
            "— когда он(а) хочет поговорить,\n"
            "— как он(а) себя чувствует,\n"
            "— если долго не выходит на связь.",
            reply_markup=FAMILY_KEYBOARD,
        )
        return
    await update.message.reply_text(
        "Вот что я умею:\n"
        f"{BTN_REMIND_ADD} — поставлю напоминание на каждый день\n"
        f"{BTN_REMIND_LIST} — покажу все ваши напоминания\n"
        f"{BTN_FAMILY_CALL} — сообщу родным, что хотите поговорить\n"
        f"{BTN_HOW_I_AM} — расскажите, как себя чувствуете, я передам родным\n\n"
        "Также просто напишите мне что-нибудь — с удовольствием пообщаюсь!",
        reply_markup=SENIOR_KEYBOARD,
    )


# ---------- Обычный текст (простое общение) ----------

@require_subscription
async def free_text(update: Update, context: ContextTypes.DEFAULT_TYPE):
    _mark_active(update)
    text = update.message.text

    handled = await reminder_delete_by_text(update, context)
    if handled:
        return

    await update.message.reply_text(random.choice(CHAT_REPLIES))

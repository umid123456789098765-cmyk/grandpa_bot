import datetime
import logging

from telegram.ext import ContextTypes

import database as db
from config import SILENCE_ALERT_HOURS, DAILY_CHECKIN_HOUR, DAILY_CHECKIN_MINUTE

logger = logging.getLogger(__name__)


async def check_reminders(context: ContextTypes.DEFAULT_TYPE):
    """Запускается каждую минуту: рассылает напоминания, время которых наступило."""
    now = datetime.datetime.now()
    today_str = now.strftime("%Y-%m-%d")
    for r in db.all_active_reminders():
        if r["hour"] == now.hour and r["minute"] == now.minute and r["last_sent_date"] != today_str:
            try:
                await context.bot.send_message(
                    chat_id=r["senior_id"],
                    text=f"⏰ Напоминание: {r['text']}",
                )
                db.mark_reminder_sent_today(r["id"], today_str)
            except Exception:
                logger.exception("Не удалось отправить напоминание пользователю %s", r["senior_id"])


async def daily_checkin(context: ContextTypes.DEFAULT_TYPE):
    """Раз в день спрашивает у всех дедушек/бабушек, как дела — для проверки активности."""
    for senior_id in db.get_all_seniors():
        try:
            await context.bot.send_message(
                chat_id=senior_id,
                text="Доброе утро! 🙂 Просто напишите мне что-нибудь в ответ, чтобы я знал(а), что у вас всё хорошо.",
            )
            db.set_checkin_sent(senior_id)
        except Exception:
            logger.exception("Не удалось отправить ежедневный чек-ин пользователю %s", senior_id)


async def check_silence(context: ContextTypes.DEFAULT_TYPE):
    """Каждый час проверяет: если дедушка молчит слишком долго — уведомляет родных."""
    now_ts = int(datetime.datetime.now().timestamp())
    threshold = SILENCE_ALERT_HOURS * 3600
    for senior_id in db.get_all_seniors():
        activity = db.get_activity(senior_id)
        if not activity:
            continue
        if activity["alert_sent"]:
            continue
        silence = now_ts - activity["last_message_at"]
        if silence < threshold:
            continue

        senior = db.get_user(senior_id)
        name = senior["name"] if senior else str(senior_id)
        family_ids = db.get_family_for_senior(senior_id)
        for fid in family_ids:
            try:
                hours = silence // 3600
                await context.bot.send_message(
                    chat_id=fid,
                    text=(
                        f"⚠️ {name} не выходил(а) на связь в боте уже {hours} ч. "
                        "Возможно, стоит позвонить и проверить, всё ли в порядке."
                    ),
                )
            except Exception:
                logger.exception("Не удалось отправить тревогу родственнику %s", fid)
        db.set_alert_sent(senior_id)


def register_jobs(application):
    jq = application.job_queue
    jq.run_repeating(check_reminders, interval=60, first=5)
    jq.run_daily(
        daily_checkin,
        time=datetime.time(hour=DAILY_CHECKIN_HOUR, minute=DAILY_CHECKIN_MINUTE),
    )
    jq.run_repeating(check_silence, interval=3600, first=30)

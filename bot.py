#!/usr/bin/env python3
# bot.py - Telegram Video Bot (simple template)
# Requires: python-telegram-bot==20.8 and ffmpeg installed on the host

import asyncio
import logging
import os
import shlex
import subprocess
import tempfile
from pathlib import Path

from telegram import InlineKeyboardButton, InlineKeyboardMarkup, Update
from telegram.ext import (
    ApplicationBuilder,
    CallbackQueryHandler,
    CommandHandler,
    ContextTypes,
    MessageHandler,
    filters,
)

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Helper: run ffmpeg in threadpool (blocking) and return output path
async def run_ffmpeg(input_path: str, output_path: str) -> str:
    loop = asyncio.get_event_loop()

    def _run():
        # Example compression: scale to max 720p and use libx264 + aac
        cmd = [
            "ffmpeg",
            "-y",
            "-i",
            input_path,
            "-vf",
            "scale='min(1280,iw)':'min(720,ih)':force_original_aspect_ratio=decrease",
            "-c:v",
            "libx264",
            "-preset",
            "veryfast",
            "-crf",
            "28",
            "-c:a",
            "aac",
            "-b:a",
            "128k",
            output_path,
        ]
        # shell-escape for logging
        logger.info("Running ffmpeg: %s", " ".join(shlex.quote(p) for p in cmd))
        proc = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        if proc.returncode != 0:
            logger.error("ffmpeg failed: %s", proc.stderr.decode(errors="ignore"))
            raise RuntimeError("ffmpeg failed")
        return output_path

    return await loop.run_in_executor(None, _run)


async def start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    await update.message.reply_text(
        "مرحبًا — أرسل لي فيديو أو GIF وسأعطيك خيار إرسال الأصلي أو ضغطه.")


async def handle_media(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    message = update.message
    user = message.from_user

    # determine file and file_id
    file_obj = None
    filename = None
    mime = None

    if message.video:
        file_obj = message.video
        filename = getattr(file_obj, "file_name", "video.mp4")
        mime = "video"
    elif message.animation:  # GIF
        file_obj = message.animation
        filename = getattr(file_obj, "file_name", "animation.gif")
        mime = "animation"
    else:
        await message.reply_text("لم أجد فيديو أو GIF في الرسالة — أرسل ملف فيديو أو GIF.")
        return

    file_id = file_obj.file_id

    # download to a temp file
    tmp_in = tempfile.NamedTemporaryFile(delete=False, suffix=Path(filename).suffix)
    tmp_in_path = tmp_in.name
    tmp_in.close()

    file = await context.bot.get_file(file_id)
    await file.download_to_drive(tmp_in_path)

    # store path in user_data so callback can access it
    context.user_data["last_media_path"] = tmp_in_path
    context.user_data["last_media_mime"] = mime
    context.user_data["last_media_filename"] = filename

    keyboard = [
        [InlineKeyboardButton("أرسل الأصلي", callback_data="original")],
        [InlineKeyboardButton("ضغط وأرسل أصغر", callback_data="compress")],
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    await message.reply_text("اختر ماذا تريد أن أفعل بالملف:", reply_markup=reply_markup)


async def button_cb(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    query = update.callback_query
    await query.answer()
    data = query.data
    user_data = context.user_data

    media_path = user_data.get("last_media_path")
    mime = user_data.get("last_media_mime")
    filename = user_data.get("last_media_filename", "file")

    if not media_path or not os.path.exists(media_path):
        await query.edit_message_text("لا يوجد ملف محفوظ حالياً — أرسل ملفًا جديدًا.")
        return

    try:
        if data == "original":
            # send original as document to preserve original file and size
            await query.edit_message_text("جارٍ إرسال الملف الأصلي...")
            await context.bot.send_document(chat_id=query.message.chat_id, document=open(media_path, "rb"), filename=filename)
            await query.edit_message_text("تم إرسال الملف الأصلي.")

        elif data == "compress":
            await query.edit_message_text("جارٍ ضغط الملف — يرجى الانتظار...")
            # create output temp file
            suffix = ".mp4" if mime in ("video", "animation") else Path(filename).suffix
            tmp_out = tempfile.NamedTemporaryFile(delete=False, suffix=suffix)
            tmp_out_path = tmp_out.name
            tmp_out.close()

            # run ffmpeg
            try:
                out_path = await run_ffmpeg(media_path, tmp_out_path)
            except Exception as exc:
                logger.exception("Compression failed")
                await query.edit_message_text("فشل الضغط: %s" % str(exc))
                return

            await context.bot.send_document(chat_id=query.message.chat_id, document=open(out_path, "rb"), filename=Path(out_path).name)
            await query.edit_message_text("تم إرسال الملف المضغوط.")

            # cleanup output
            try:
                os.unlink(out_path)
            except Exception:
                pass

    finally:
        # cleanup input
        try:
            if media_path and os.path.exists(media_path):
                os.unlink(media_path)
        except Exception:
            pass
        # clear user_data
        user_data.pop("last_media_path", None)
        user_data.pop("last_media_mime", None)
        user_data.pop("last_media_filename", None)


async def help_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    await update.message.reply_text("أوامر: /start, /help — أرسل فيديو أو GIF للتعامل معه.")


def main() -> None:
    TOKEN = os.environ.get("BOT_TOKEN")
    if not TOKEN:
        raise RuntimeError("Please set BOT_TOKEN environment variable")

    app = ApplicationBuilder().token(TOKEN).build()

    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("help", help_cmd))
    app.add_handler(MessageHandler(filters.VIDEO | filters.ANIMATION, handle_media))
    app.add_handler(CallbackQueryHandler(button_cb))

    logger.info("Bot started")
    app.run_polling()


if __name__ == "__main__":
    main()

# Telegram Video Bot

بوت تلجرام يستقبل فيديو أو GIF → يعطيك خيار ضغط أصغر أو جودة أصلية → يرسل الملف.

## تشغيل على سيرفر (Railway/Heroku)

1. ثبت Python و FFmpeg.
2. أضف متغير بيئة:
   - BOT_TOKEN (توكن البوت)
3. شغّل:
```bash
pip install -r requirements.txt
python bot.py
```

4. افتح البوت في تلجرام → اكتب /start → ارسل فيديو أو GIF → اختار الضغط أو الجودة الأصلية.

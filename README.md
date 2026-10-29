# Nine Server

سایت مدیریت و پنل ساده Nine Server با Python + Flask.

## امکانات
- ثبت‌نام و ورود
- اتصال نام Minecraft به حساب سایت
- پروفایل قابل تنظیم
- سیستم تیکت پشتیبانی
- پنل ادمین
- مدیریت آیتم‌های شاپ
- افزودن و حذف ادمین
- ذخیره اطلاعات در SQLite
- هش‌شدن رمزهای عبور

## اجرای آنلاین در Render
Build Command:
`pip install -r requirements.txt`

Start Command:
`gunicorn app:app`

Environment Variables:
- `SECRET_KEY` = یک مقدار تصادفی طولانی
- `OWNER_USERNAME` = نام کاربری مالک سایت
- `OWNER_PASSWORD` = رمز اولیه مالک
- `OWNER_MINECRAFT` = Minecraft username مالک

نکته امنیتی: سایت نباید رمز حساب Minecraft بازیکنان را دریافت یا ذخیره کند. در این پروژه، نام Minecraft فقط برای شناسایی حساب استفاده می‌شود و رمز، فقط رمز حساب همین سایت است.

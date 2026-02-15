import os
import asyncio
from aiogram import Bot, Dispatcher
from aiogram.types import Message
from aiohttp import web

BOT_TOKEN = os.getenv("BOT_TOKEN")

bot = Bot(token=BOT_TOKEN)
dp = Dispatcher()

@dp.message()
async def start(message: Message):
    await message.answer(
        "✅ Бот работает\n\n"
        "Это тестовая версия.\n"
        "Дальше здесь будет анализ и PNG со стрелкой."
    )

# Web-сервер для Render (обязательно)
async def handle(request):
    return web.Response(text="Bot is alive")

async def main():
    app = web.Application()
    app.router.add_get("/", handle)
    runner = web.AppRunner(app)
    await runner.setup()
    site = web.TCPSite(
        runner,
        "0.0.0.0",
        int(os.environ.get("PORT", 10000))
    )
    await site.start()

    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())

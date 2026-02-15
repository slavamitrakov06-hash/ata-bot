import os
import asyncio
from io import BytesIO
from datetime import datetime

import pytz
from aiohttp import web
from PIL import Image, ImageDraw, ImageFont

from aiogram import Bot, Dispatcher, F
from aiogram.types import Message, CallbackQuery, BufferedInputFile
from aiogram.utils.keyboard import InlineKeyboardBuilder

BOT_TOKEN = os.getenv("BOT_TOKEN")

ASSETS = ["EURUSD", "GBPUSD", "USDJPY", "AUDUSD", "USDCAD", "USDCHF"]
TFS = ["5m", "15m"]

OSLO = pytz.timezone("Europe/Oslo")

bot = Bot(token=BOT_TOKEN)
dp = Dispatcher()

# простое хранение выбора пользователя (в памяти)
user_state = {}  # user_id -> {"asset": "...", "tf": "..."}

def get_state(user_id: int):
    if user_id not in user_state:
        user_state[user_id] = {"asset": ASSETS[0], "tf": TFS[0]}
    return user_state[user_id]

def menu_kb(user_id: int):
    st = get_state(user_id)
    kb = InlineKeyboardBuilder()
    kb.button(text=f"Актив: {st['asset']}", callback_data="pick_asset")
    kb.button(text=f"TF: {st['tf']}", callback_data="pick_tf")
    kb.button(text="Сгенерировать PNG", callback_data="gen_png")
    kb.adjust(1)
    return kb.as_markup()

def assets_kb():
    kb = InlineKeyboardBuilder()
    for a in ASSETS:
        kb.button(text=a, callback_data=f"asset:{a}")
    kb.button(text="⬅️ Назад", callback_data="back")
    kb.adjust(2)
    return kb.as_markup()

def tf_kb():
    kb = InlineKeyboardBuilder()
    for t in TFS:
        kb.button(text=t, callback_data=f"tf:{t}")
    kb.button(text="⬅️ Назад", callback_data="back")
    kb.adjust(2)
    return kb.as_markup()

def _load_font(size: int):
    # На Render обычно есть DejaVuSans
    try:
        return ImageFont.truetype("DejaVuSans.ttf", size=size)
    except Exception:
        return ImageFont.load_default()

def render_demo_png(asset: str, tf: str) -> BytesIO:
    """
    Демо PNG без реальных котировок.
    Сигнал делаем детерминированно по минуте, чтобы не был рандом.
    """
    now = datetime.now(OSLO)
    minute = now.minute

    # детерминированно:
    # 0-19 -> CALL, 20-39 -> PUT, 40-59 -> NONE
    if 0 <= minute <= 19:
        signal = "CALL"
        arrow = "↑"
        color = (30, 215, 96)
        reason = "DEMO: пример сигнала"
    elif 20 <= minute <= 39:
        signal = "PUT"
        arrow = "↓"
        color = (255, 69, 58)
        reason = "DEMO: пример сигнала"
    else:
        signal = "NONE"
        arrow = "•"
        color = (150, 150, 150)
        reason = "DEMO: нет сигнала"

    W, H = 1080, 1080
    img = Image.new("RGB", (W, H), (12, 14, 18))
    d = ImageDraw.Draw(img)

    title_f = _load_font(54)
    info_f = _load_font(34)
    small_f = _load_font(28)
    big_f = _load_font(160)
    label_f = _load_font(70)

    # заголовок
    d.text((W // 2, 70), "ATA • Анализ", font=title_f, fill=(235, 235, 235), anchor="mm")

    # инфо блок
    d.text((80, 160), f"Актив: {asset}", font=info_f, fill=(200, 200, 200))
    d.text((80, 210), f"TF: {tf}", font=info_f, fill=(200, 200, 200))

    ts = now.strftime("%d.%m.%Y %H:%M")
    d.text((80, 260), f"Время: {ts} (Oslo)", font=small_f, fill=(160, 160, 160))

    # центр
    d.text((W // 2, H // 2 - 80), arrow, font=big_f, fill=color, anchor="mm")
    if signal == "NONE":
        label = "НЕТ СИГНАЛА"
    else:
        label = signal
    d.text((W // 2, H // 2 + 120), label, font=label_f, fill=(235, 235, 235), anchor="mm")

    # причина
    d.text((W // 2, H - 140), f"Причина: {reason}", font=small_f, fill=(180, 180, 180), anchor="mm")

    out = BytesIO()
    img.save(out, format="PNG")
    out.seek(0)
    return out

# --- Web-сервер для Render (обязательно) ---
async def handle(request):
    return web.Response(text="Bot is alive")

@dp.message(F.text.in_({"/start", "/menu"}))
async def start(m: Message):
    get_state(m.from_user.id)
    await m.answer("Выбери актив и TF, затем нажми «Сгенерировать PNG».", reply_markup=menu_kb(m.from_user.id))

@dp.callback_query(F.data == "pick_asset")
async def pick_asset(c: CallbackQuery):
    await c.message.edit_text("Выбери актив:", reply_markup=assets_kb())
    await c.answer()

@dp.callback_query(F.data == "pick_tf")
async def pick_tf(c: CallbackQuery):
    await c.message.edit_text("Выбери таймфрейм:", reply_markup=tf_kb())
    await c.answer()

@dp.callback_query(F.data.startswith("asset:"))
async def set_asset(c: CallbackQuery):
    asset = c.data.split(":", 1)[1]
    st = get_state(c.from_user.id)
    st["asset"] = asset
    await c.message.edit_text("Меню:", reply_markup=menu_kb(c.from_user.id))
    await c.answer("Ок")

@dp.callback_query(F.data.startswith("tf:"))
async def set_tf(c: CallbackQuery):
    tf = c.data.split(":", 1)[1]
    st = get_state(c.from_user.id)
    st["tf"] = tf
    await c.message.edit_text("Меню:", reply_markup=menu_kb(c.from_user.id))
    await c.answer("Ок")

@dp.callback_query(F.data == "back")
async def back(c: CallbackQuery):
    await c.message.edit_text("Меню:", reply_markup=menu_kb(c.from_user.id))
    await c.answer()

@dp.callback_query(F.data == "gen_png")
async def gen_png(c: CallbackQuery):
    st = get_state(c.from_user.id)
    asset, tf = st["asset"], st["tf"]

    png = render_demo_png(asset, tf)
    file = BufferedInputFile(png.read(), filename="signal.png")
    await c.message.answer_photo(file, caption=f"{asset} • {tf}")

    await c.answer("Готово")
    # возвращаем меню
    await c.message.edit_text("Меню:", reply_markup=menu_kb(c.from_user.id))

async def main():
    # Web
    app = web.Application()
    app.router.add_get("/", handle)
    runner = web.AppRunner(app)
    await runner.setup()
    site = web.TCPSite(runner, "0.0.0.0", int(os.environ.get("PORT", 10000)))
    await site.start()

    # Bot
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())

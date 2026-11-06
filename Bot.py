import asyncio
import logging
import sqlite3
from datetime import datetime, timedelta

from aiogram import Bot, Dispatcher, F, Router
from aiogram.filters import CommandStart, Command
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.fsm.storage.memory import MemoryStorage
from aiogram.types import (
    CallbackQuery,
    InlineKeyboardButton,
    InlineKeyboardMarkup,
    Message,
)

# ================= КОНФИГУРАЦИЯ =================
BOT_TOKEN = "ВСТАВЬ_СЮДА_СВОЙ_ТОКЕН_БОТА"  # Получи у @BotFather
ADMIN_USERNAME = "@Lafraw"
ADMIN_IDS = [123456789]  # Вставь сюда свой числовой Telegram ID (можно узнать у @userinfobot)

# ================= БАЗА ДАННЫХ =================
conn = sqlite3.connect("rent_bot.db", check_same_thread=False)
cursor = conn.cursor()

# Создание таблиц
cursor.execute("""
CREATE TABLE IF NOT EXISTS accounts (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    category TEXT, -- 'premium' или 'budget'
    title TEXT,
    description TEXT,
    media_id TEXT, -- photo, video, animation, sticker
    media_type TEXT
)
""")

cursor.execute("""
CREATE TABLE IF NOT EXISTS bookings (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id INTEGER,
    username TEXT,
    account_id INTEGER,
    start_time TEXT,
    end_time TEXT,
    price TEXT,
    created_at TEXT
)
""")
conn.commit()

# По умолчанию добавим тестовые аккаунты, если база пустая
cursor.execute("SELECT COUNT(*) FROM accounts")
if cursor.fetchone()[0] == 0:
    cursor.execute("INSERT INTO accounts (category, title, description) VALUES (?, ?, ?)",
                   ("premium", "Аккаунт №1 (Премиум)", "Топ прокачка, редкие скины."))
    cursor.execute("INSERT INTO accounts (category, title, description) VALUES (?, ?, ?)",
                   ("budget", "Аккаунт №2 (Бюджет)", "Хороший старт для игры."))
    conn.commit()


# ================= FSM СОСТОЯНИЯ =================
class AddAccountState(StatesGroup):
    category = State()
    title = State()
    description = State()
    media = State()

class BookState(StatesGroup):
    select_account = State()
    select_duration = State()
    select_date = State()
    payment_method = State()

class EditAccountState(StatesGroup):
    account_id = State()
    new_desc = State()


# ================= ИНИЦИАЛИЗА =================
bot = Bot(token=BOT_TOKEN)
dp = Dispatcher(storage=MemoryStorage())
router = Router()
dp.include_router(router)

# ================= КЛАВИАТУРЫ =================

def get_start_keyboard():
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="📜 Правила аренды", url="https://t.me/telegram")], # Добавь ссылку потом
        [InlineKeyboardButton(text="Принимаю🔴", callback_data="accept_rules")]
    ])

def get_main_menu_keyboard():
    return InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(text="Premium аккаунты🟡", callback_data="cat_premium"),
            InlineKeyboardButton(text="Бюджетные аккаунты🟣", callback_data="cat_budget")
        ],
        [
            InlineKeyboardButton(text="Мои бронирования🔵", callback_data="my_bookings"),
            InlineKeyboardButton(text="Поддержка🟢", callback_data="support")
        ]
    ])

def get_tariffs_keyboard():
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="6 ЧАСОВ — 300₽ 🔴", callback_data="tariff_6_300")],
        [InlineKeyboardButton(text="8 ЧАСОВ — 450₽ 🔴", callback_data="tariff_8_450")],
        [InlineKeyboardButton(text="12 ЧАСОВ — 750₽ 🔴", callback_data="tariff_12_750")],
        [InlineKeyboardButton(text="24 ЧАСА — 1000₽ 🔴", callback_data="tariff_24_1000")],
        [InlineKeyboardButton(text="Ночной тариф (22:00-8:00) — 600₽ 🔴", callback_data="tariff_night_600")],
        [InlineKeyboardButton(text="Назад🔴", callback_data="main_menu")]
    ])

def get_payment_methods_keyboard():
    return InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(text="Кошелек тг🔴", callback_data="pay_wallet"),
            InlineKeyboardButton(text="Карта банк🔴", callback_data="pay_card")
        ],
        [
            InlineKeyboardButton(text="Назад🔴", callback_data="cat_select_back"),
            InlineKeyboardButton(text="Главное меню🔴", callback_data="main_menu")
        ]
    ])

def get_card_pay_keyboard():
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="Оплатить🔴", callback_data="confirm_pay")],
        [
            InlineKeyboardButton(text="Назад🔴", callback_data="pay_back"),
            InlineKeyboardButton(text="Главное меню🔴", callback_data="main_menu")
        ]
    ])

def get_admin_keyboard():
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="➕ Добавить аккаунт", callback_data="admin_add_acc")],
        [InlineKeyboardButton(text="✏️ Редактировать аккаунт/медиа", callback_data="admin_edit_acc")],
        [InlineKeyboardButton(text="📅 Занятость / Брони", callback_data="admin_view_bookings")],
        [InlineKeyboardButton(text="❌ Закрыть админку", callback_data="main_menu")]
    ])


# ================= ОБРАБОТЧИКИ (HANDLERS) =================

@router.message(CommandStart())
async def cmd_start(message: Message):
    welcome_text = (
        "Добро пожаловать в World Safe Rent!\n\n"
        "Здесь тебя ждёт удобный каталог и возможность выбрать подходящий вариант по своим предпочтениям.\n\n"
        "✨ **Почему WorldSafeRent?**\n"
        "• Удобный и понятный каталог.\n"
        "• Удобное расписание бронирований.\n"
        "• Поддержка, если возникнут вопросы."
    )
    # Если есть картинка/гиф/стикер при старте, можно отправить её отправкой фото
    await message.answer(welcome_text, reply_markup=get_start_keyboard(), parse_mode="Markdown")

@router.callback_query(F.data == "accept_rules")
@router.callback_query(F.data == "main_menu")
async def show_main_menu(call: CallbackQuery, state: FSMContext):
    await state.clear()
    text = (
        "Здесь ты можешь арендовать аккаунт по самым приятным ценам😜\n"
        "👇 Выбирай интересующий раздел и знакомься с предложениями!"
    )
    if call.message.text:
        await call.message.edit_text(text, reply_markup=get_main_menu_keyboard())
    else:
        await call.message.answer(text, reply_markup=get_main_menu_keyboard())

# --- ПРОСМОТР АККАУНТОВ ---
@router.callback_query(F.data.in_({"cat_premium", "cat_budget"}))
async def show_category(call: CallbackQuery, state: FSMContext):
    category = "premium" if call.data == "cat_premium" else "budget"
    cursor.execute("SELECT id, title, description, media_id, media_type FROM accounts WHERE category=?", (category,))
    accounts = cursor.fetchall()

    if not accounts:
        await call.answer("В этой категории пока нет аккаунтов.", show_alert=True)
        return

    for acc in accounts:
        acc_id, title, desc, media_id, media_type = acc

        # Проверка текущих броней аккаунта
        cursor.execute("SELECT start_time, end_time FROM bookings WHERE account_id=?", (acc_id,))
        bookings = cursor.fetchall()

        status_text = "\n\n<b>Занятые слоты:</b>\n"
        if bookings:
            for b in bookings:
                status_text += f"⏰ {b[0]} — {b[1]}\n"
        else:
            status_text += "🟢 Свободен на любые даты!\n"

        text = f"<b>{title}</b>\n\n{desc}{status_text}"
        kb = InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="Забронировать🔴", callback_data=f"book_acc_{acc_id}")],
            [InlineKeyboardButton(text="Главное меню🔴", callback_data="main_menu")]
        ])

        if media_id:
            if media_type == "photo":
                await call.message.answer_photo(photo=media_id, caption=text, reply_markup=kb, parse_mode="HTML")
            elif media_type == "video":
                await call.message.answer_video(video=media_id, caption=text, reply_markup=kb, parse_mode="HTML")
            elif media_type == "animation":
                await call.message.answer_animation(animation=media_id, caption=text, reply_markup=kb, parse_mode="HTML")
            elif media_type == "sticker":
                await call.message.answer_sticker(sticker=media_id)
                await call.message.answer(text, reply_markup=kb, parse_mode="HTML")
        else:
            await call.message.answer(text, reply_markup=kb, parse_mode="HTML")

# --- ПРОЦЕСС БРОНИРОВАНИЯ ---
@router.callback_query(F.data.startswith("book_acc_"))
async def start_booking(call: CallbackQuery, state: FSMContext):
    acc_id = int(call.data.split("_")[2])
    await state.update_data(account_id=acc_id)

    await call.message.answer(
        "Выберите продолжительность аренды:",
        reply_markup=get_tariffs_keyboard()
    )

@router.callback_query(F.data.startswith("tariff_"))
async def select_tariff(call: CallbackQuery, state: FSMContext):
    parts = call.data.split("_")
    duration_type = parts[1]
    price = parts[2] + "₽"

    await state.update_data(duration=duration_type, price=price)

    warning_text = (
        "<b>Внимание! Время аренды идет даже если вы не играете, просим позаботиться о времени заранее, спасибо!</b>"
    )
    await call.message.answer(warning_text, reply_markup=get_payment_methods_keyboard(), parse_mode="HTML")

@router.callback_query(F.data.in_({"pay_wallet", "pay_card"}))
async def select_payment(call: CallbackQuery):
    await call.message.answer("Оплата через выбранную систему:", reply_markup=get_card_pay_keyboard())

@router.callback_query(F.data == "confirm_pay")
async def confirm_payment(call: CallbackQuery, state: FSMContext):
    data = await state.get_data()
    acc_id = data.get("account_id", 1)
    price = data.get("price", "300₽")

    # Расчет времени
    now = datetime.now()
    start_str = now.strftime("%Y-%m-%d %H:%M")
    end_str = (now + timedelta(hours=6)).strftime("%Y-%m-%d %H:%M") # Авто-расчет 6ч для примера

    user_id = call.from_user.id
    username = f"@{call.from_user.username}" if call.from_user.username else f"ID: {user_id}"

    # Запись в БД
    cursor.execute(
        "INSERT INTO bookings (user_id, username, account_id, start_time, end_time, price, created_at) VALUES (?, ?, ?, ?, ?, ?, ?)",
        (user_id, username, acc_id, start_str, end_str, price, start_str)
    )
    conn.commit()

    # Уведомление покупателю
    await call.message.answer(f"Спасибо за покупку, с вами свяжется {ADMIN_USERNAME}")

    # Уведомление АДМИНУ
    admin_msg = (
        f"🚨 **НОВАЯ БРОНЬ!**\n\n"
        f"👤 Покупатель: {username}\n"
        f"🎮 Аккаунт ID: #{acc_id}\n"
        f"⏱ Время: {start_str} — {end_str}\n"
        f"💰 Оплачено: {price}"
    )
    for admin_id in ADMIN_IDS:
        try:
            await bot.send_message(admin_id, admin_msg, parse_mode="Markdown")
        except Exception:
            pass

    await state.clear()

# --- МОИ БРОНИРОВАНИЯ ---
@router.callback_query(F.data == "my_bookings")
async def show_my_bookings(call: CallbackQuery):
    user_id = call.from_user.id
    cursor.execute("SELECT account_id, start_time, end_time, price FROM bookings WHERE user_id=?", (user_id,))
    rows = cursor.fetchall()

    kb = InlineKeyboardMarkup(inline_keyboard=[[InlineKeyboardButton(text="Главное меню🔴", callback_data="main_menu")]])

    if not rows:
        await call.message.edit_text("Здесь будут ваши бронирования 🙂", reply_markup=kb)
        return

    text = "<b>История ваших бронирований:</b>\n\n"
    for r in rows:
        text += f"🎮 Аккаунт #{r[0]}\n📅 С: {r[1]} До: {r[2]}\n💰 Сумма: {r[3]}\n-------------------\n"

    await call.message.edit_text(text, reply_markup=kb, parse_mode="HTML")

# --- ПОДДЕРЖКА ---
@router.callback_query(F.data == "support")
async def show_support(call: CallbackQuery):
    text = (
        f"Если есть проблемы с ботом {ADMIN_USERNAME}\n"
        f"Если нужна помощь с арендой, либо хотите забронировать через админа: {ADMIN_USERNAME}"
    )
    kb = InlineKeyboardMarkup(inline_keyboard=[[InlineKeyboardButton(text="Главное меню🔴", callback_data="main_menu")]])
    await call.message.edit_text(text, reply_markup=kb)


# ================= АДМИН ПАНЕЛЬ =================

@router.message(Command("admin"))
async def cmd_admin(message: Message):
    if message.from_user.id not in ADMIN_IDS:
        return
    await message.answer("🛠 <b>Панель администратора WorldSafeRent</b>", reply_markup=get_admin_keyboard(), parse_mode="HTML")

@router.callback_query(F.data == "admin_add_acc")
async def admin_add_start(call: CallbackQuery, state: FSMContext):
    if call.from_user.id not in ADMIN_IDS: return
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="Премиум", callback_data="add_cat_premium")],
        [InlineKeyboardButton(text="Бюджет", callback_data="add_cat_budget")]
    ])
    await call.message.answer("Выберите категорию аккаунта:", reply_markup=kb)
    await state.set_state(AddAccountState.category)

@router.callback_query(F.data.startswith("add_cat_"), AddAccountState.category)
async def admin_add_cat(call: CallbackQuery, state: FSMContext):
    cat = "premium" if "premium" in call.data else "budget"
    await state.update_data(category=cat)
    await call.message.answer("Введите название аккаунта (например: Аккаунт №3):")
    await state.set_state(AddAccountState.title)

@router.message(AddAccountState.title)
async def admin_add_title(message: Message, state: FSMContext):
    await state.update_data(title=message.text)
    await call_msg = await message.answer("Введите описание аккаунта:")
    await state.set_state(AddAccountState.description)

@router.message(AddAccountState.description)
async def admin_add_desc(message: Message, state: FSMContext):
    await state.update_data(description=message.text)
    await message.answer("Прикрепите медиафайл (Фото, Видео, GIF или Анимированный Стикер). Если медиа не требуется, отправьте '-'")
    await state.set_state(AddAccountState.media)

@router.message(AddAccountState.media)
async def admin_add_media(message: Message, state: FSMContext):
    data = await state.get_data()
    media_id, media_type = None, None

    if message.photo:
        media_id = message.photo[-1].file_id
        media_type = "photo"
    elif message.video:
        media_id = message.video.file_id
        media_type = "video"
    elif message.animation:
        media_id = message.animation.file_id
        media_type = "animation"
    elif message.sticker:
        media_id = message.sticker.file_id
        media_type = "sticker"

    cursor.execute(
        "INSERT INTO accounts (category, title, description, media_id, media_type) VALUES (?, ?, ?, ?, ?)",
        (data['category'], data['title'], data['description'], media_id, media_type)
    )
    conn.commit()
    await message.answer("✅ Аккаунт успешно добавлен в каталог!", reply_markup=get_admin_keyboard())
    await state.clear()

@router.callback_query(F.data == "admin_view_bookings")
async def admin_view_bookings(call: CallbackQuery):
    if call.from_user.id not in ADMIN_IDS: return
    cursor.execute("SELECT id, username, account_id, start_time, end_time, price FROM bookings ORDER BY id DESC LIMIT 10")
    rows = cursor.fetchall()

    if not rows:
        await call.message.answer("Бронирований пока нет.")
        return

    msg = "<b>Все бронирования (Занятость):</b>\n\n"
    for r in rows:
        msg += f"Бронь #{r[0]} | {r[1]}\n🎮 Аккаунт #{r[2]}\n⏰ {r[3]} — {r[4]}\n💰 {r[5]}\n-------------------\n"
    await call.message.answer(msg, parse_mode="HTML")

# ================= ЗАПУСК БОТА =================
async def main():
    print("Бот успешно запущен!")
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())
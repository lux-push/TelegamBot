import asyncio
import logging
from pathlib import Path
from aiogram import Bot, Dispatcher, F, Router
from aiogram.filters import Command
from aiogram.types import Message, FSInputFile, ReplyKeyboardMarkup, KeyboardButton
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from config import BOT_A_TOKEN, BOT_B_TOKEN, ADMIN_CHAT_ID, ADMIN_IDS
from db import Database


logging.basicConfig(level=logging.INFO)
BASE_DIR = Path(__file__).resolve().parent
bot = Bot(token=BOT_A_TOKEN)
dp = Dispatcher()
router = Router()
db = Database()


# ✅ КЛАВИАТУРЫ
main_menu = ReplyKeyboardMarkup(
    keyboard=[
        [KeyboardButton(text="/start"), KeyboardButton(text="/apply")]
    ],
    resize_keyboard=True,
    is_persistent=True
)

yes_no_keyboard = ReplyKeyboardMarkup(
    keyboard=[
        [KeyboardButton(text="✅ Да"), KeyboardButton(text="❌ Нет")]
    ],
    resize_keyboard=True,
    one_time_keyboard=True
)

platform_keyboard = ReplyKeyboardMarkup(
    keyboard=[
        [KeyboardButton(text="🇷🇺 Авито"), KeyboardButton(text="🇧🇾 Куфар")]
    ],
    resize_keyboard=True,
    one_time_keyboard=True
)


class ApplicationForm(StatesGroup):
    platform = State()
    rf_or_by = State()
    age_14 = State()


def is_yes(text: str) -> bool:
    return "да" in text.lower()


def photo(name: str) -> FSInputFile:
    return FSInputFile(BASE_DIR / "images" / name)


async def delete_user_message(message: Message):
    try:
        await message.delete()
    except Exception:
        pass


async def delete_last_bot_message(state: FSMContext, chat_id: int):
    data = await state.get_data()
    last_bot_msg_id = data.get("last_bot_msg_id")
    if last_bot_msg_id:
        try:
            await bot.delete_message(chat_id=chat_id, message_id=last_bot_msg_id)
        except Exception:
            pass


async def restart_platform(message: Message, state: FSMContext):
    """🔄 Возврат к выбору платформы"""
    await delete_user_message(message)
    await delete_last_bot_message(state, message.chat.id)
    await send_step_photo(message, state, "apply_5.jpg", "❌ Выберите платформу заново:", platform_keyboard)
    await state.set_state(ApplicationForm.platform)


async def send_step_photo(message: Message, state: FSMContext, photo_name: str, caption: str, reply_markup=None):
    sent = await message.answer_photo(
        photo=photo(photo_name),
        caption=caption,
        reply_markup=reply_markup
    )
    await state.update_data(last_bot_msg_id=sent.message_id)


async def send_final_photo(message: Message, state: FSMContext):
    sent = await message.answer_photo(
        photo=photo("apply_1.jpg"),
        caption="✅ Заявка принята\n\n"
                "Номер заявки: #2791\n\n"
                "Ваш менеджер: @Kufar_Job\n"
                "Напишите ему '+' в ЛС.",
        reply_markup=main_menu
    )
    await state.update_data(last_bot_msg_id=sent.message_id)


async def send_stats_to_bot_b(platform: str, user_id: int, username: str, extra_info: str = ""):
    stats_bot = Bot(token=BOT_B_TOKEN)
    try:
        text = (
            f"📝 НОВАЯ ЗАЯВКА\n\n"
            f"1. Платформа: {platform}\n"
            f"2. {extra_info}\n"
            f"ID: {user_id}\n"
            f"Username: @{username or 'нет'}"
        )
        await stats_bot.send_message(ADMIN_CHAT_ID, text)
        print(f"✅ Заявка отправлена в Bot B: {platform} ID:{user_id}")
    except Exception as e:
        print(f"❌ Ошибка отправки в Bot B: {e}")
    finally:
        await stats_bot.session.close()


@router.message(Command("start"), F.text == "/start")
async def start_handler(message: Message):
    # ✅ Сохраняем ID сообщения start для удаления
    sent = await message.answer(
        "🚀 Bot Kufar запущен.\n\n"
        "/apply — подать заявку",
        reply_markup=main_menu
    )
    await message.answer("Нажми кнопку ниже 👇", reply_markup=main_menu)


@router.message(Command("apply"), F.text == "/apply")
async def apply_start(message: Message, state: FSMContext):
    await state.clear()
    
    # ✅ Удаляем сообщение /start (последнее сообщение бота)
    try:
        await bot.delete_message(chat_id=message.chat.id, message_id=message.chat.id + 1)  # Примерный ID
    except Exception:
        pass
    
    await send_step_photo(message, state, "apply_5.jpg", "1. Выбор Авито или Куфар", platform_keyboard)
    await state.set_state(ApplicationForm.platform)


@router.message(ApplicationForm.platform)
async def platform_handler(message: Message, state: FSMContext):
    await delete_user_message(message)
    await delete_last_bot_message(state, message.chat.id)

    platform_text = message.text.strip()
    
    if "авито" in platform_text.lower():
        platform = "Авито"
        await state.update_data(platform=platform)
        await send_step_photo(
            message,
            state,
            "apply_4.jpg",
            "2. Являетесь ли вы гражданином РФ?",
            yes_no_keyboard
        )
        await state.set_state(ApplicationForm.rf_or_by)
        return

    if "куфар" in platform_text.lower():
        platform = "Куфар"
        await state.update_data(platform=platform)
        await send_step_photo(
            message,
            state,
            "apply_4.jpg",
            "2. Являетесь ли вы гражданином Беларуси?",
            yes_no_keyboard
        )
        await state.set_state(ApplicationForm.rf_or_by)
        return

    await restart_platform(message, state)


@router.message(ApplicationForm.rf_or_by)
async def rf_or_by_handler(message: Message, state: FSMContext):
    await delete_user_message(message)
    await delete_last_bot_message(state, message.chat.id)

    data = await state.get_data()
    platform = data.get("platform")

    if is_yes(message.text):
        if platform == "Авито":
            await state.update_data(rf_citizen="Да")
            await send_step_photo(
                message,
                state,
                "apply_3.jpg",
                "3. Есть ли вам 14 лет?",
                yes_no_keyboard
            )
            await state.set_state(ApplicationForm.age_14)
            return

        # ✅ Куфар заявка принята
        db.add_application(message.from_user.id, platform, "Да", 1)
        await send_stats_to_bot_b(platform, message.from_user.id, message.from_user.username or 'нет', "Да")
        await send_final_photo(message, state)
        await state.clear()
        return

    await restart_platform(message, state)


@router.message(ApplicationForm.age_14)
async def age_14_handler(message: Message, state: FSMContext):
    await delete_user_message(message)
    await delete_last_bot_message(state, message.chat.id)

    if not is_yes(message.text):
        await message.answer_photo(
            photo=photo("apply_2.jpg"),
            caption=(
                "😔 К сожалению, мы не можем продолжить: необходим возраст 14+ лет.\n\n"
                "Но ты всё равно можешь заработать! 💰\n\n"
                "🔥 Приглашай людей по своей реф-ссылке и получай бонусы.\n"
                "📩 Свяжитесь с админом или найдите основного бота для работы."
            ),
            reply_markup=main_menu
        )
        await state.clear()
        return

    # ✅ Авито заявка принята
    data = await state.get_data()
    db.add_application(
        message.from_user.id,
        data.get('platform'),
        data.get('rf_citizen'),
        1
    )

    await send_stats_to_bot_b(
        data.get('platform'),
        message.from_user.id,
        message.from_user.username or 'нет',
        f"Гражданин РФ: {data.get('rf_citizen')} | 14+: Да"
    )

    await send_final_photo(message, state)
    await state.clear()


@router.message(Command("test"))
async def test_handler(message: Message):
    if message.from_user.id not in ADMIN_IDS:
        await message.answer("❌ Нет доступа")
        return

    await send_stats_to_bot_b("Куфар", 999999, "test_user", "Тестовая заявка")
    await message.answer("✅ Тестовая заявка отправлена в Bot B!", reply_markup=main_menu)


dp.include_router(router)


async def main():
    await bot.delete_webhook(drop_pending_updates=True)
    print("🚀 Bot A запущен!")
    try:
        await dp.start_polling(bot, allowed_updates=dp.resolve_used_update_types())
    finally:
        db.close()


if __name__ == "__main__":
    asyncio.run(main())
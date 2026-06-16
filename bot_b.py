import asyncio
import logging

from aiogram import Bot, Dispatcher, Router, F
from aiogram.filters import Command
from aiogram.types import Message, CallbackQuery, InlineKeyboardButton
from aiogram.utils.keyboard import InlineKeyboardBuilder
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup

from config import BOT_B_TOKEN, ADMIN_CHAT_ID, ADMIN_IDS
from db import Database

logging.basicConfig(level=logging.INFO)

bot = Bot(token=BOT_B_TOKEN)
dp = Dispatcher()
router = Router()
db = Database()


class ManagerStates(StatesGroup):
    waiting_manager_chat_id = State()
    waiting_delete_manager_chat_id = State()
    waiting_clear_applications = State()


def create_platform_keyboard():
    builder = InlineKeyboardBuilder()
    builder.row(InlineKeyboardButton(text="🇷🇺 Авито", callback_data="list_avito"))
    builder.row(InlineKeyboardButton(text="🇧🇾 Куфар", callback_data="list_kufar"))
    builder.row(InlineKeyboardButton(text="📊 Статистика", callback_data="stats"))
    builder.row(InlineKeyboardButton(text="👨‍💼 Менеджер", callback_data="manager"))
    return builder.as_markup()


def create_static_keyboard():
    builder = InlineKeyboardBuilder()
    builder.row(InlineKeyboardButton(text="🇷🇺 Авито", callback_data="list_avito"))
    builder.row(InlineKeyboardButton(text="🇧🇾 Куфар", callback_data="list_kufar"))
    builder.row(InlineKeyboardButton(text="🔙 Главное меню", callback_data="main_menu"))
    return builder.as_markup()


def create_manager_keyboard():
    builder = InlineKeyboardBuilder()
    builder.row(InlineKeyboardButton(text="➕ Добавить менеджера", callback_data="add_manager"))
    builder.row(InlineKeyboardButton(text="➖ Удалить менеджера", callback_data="delete_manager"))
    builder.row(InlineKeyboardButton(text="🗑 Очистить заявки", callback_data="clear_menu"))
    builder.row(InlineKeyboardButton(text="🔙 Главное меню", callback_data="main_menu"))
    return builder.as_markup()


def create_manager_back_keyboard():
    builder = InlineKeyboardBuilder()
    builder.row(InlineKeyboardButton(text="🔙 Назад", callback_data="manager"))
    builder.row(InlineKeyboardButton(text="🔙 Главное меню", callback_data="main_menu"))
    return builder.as_markup()


def create_clear_keyboard():
    builder = InlineKeyboardBuilder()
    builder.row(InlineKeyboardButton(text="🇷🇺 Авито", callback_data="clear_avito"))
    builder.row(InlineKeyboardButton(text="🇧🇾 Куфар", callback_data="clear_kufar"))
    builder.row(InlineKeyboardButton(text="🔸 Все заявки", callback_data="clear_all"))
    builder.row(InlineKeyboardButton(text="🔙 Назад", callback_data="manager"))
    builder.row(InlineKeyboardButton(text="🔙 Главное меню", callback_data="main_menu"))
    return builder.as_markup()


def create_clear_confirm_keyboard(action: str):
    builder = InlineKeyboardBuilder()
    builder.row(InlineKeyboardButton(text="✅ Да, очистить", callback_data=f"confirm_clear_{action}"))
    builder.row(
        InlineKeyboardButton(text="❌ Нет, отмена", callback_data="cancel_clear")
    )
    builder.row(InlineKeyboardButton(text="🔙 Назад", callback_data="clear_menu"))
    return builder.as_markup()


def create_pagination_keyboard(platform: str, page: int, total_pages: int):
    builder = InlineKeyboardBuilder()

    row = []
    if page > 1:
        row.append(InlineKeyboardButton(text="⬅️ Назад", callback_data=f"page_{platform}_{page-1}"))
    row.append(InlineKeyboardButton(text=f"{page}/{total_pages}", callback_data="none"))
    if page < total_pages:
        row.append(InlineKeyboardButton(text="Вперед ➡️", callback_data=f"page_{platform}_{page+1}"))

    builder.row(*row)
    builder.row(InlineKeyboardButton(text="🇷🇺 Авито", callback_data="list_avito"))
    builder.row(InlineKeyboardButton(text="🇧🇾 Куфар", callback_data="list_kufar"))
    builder.row(InlineKeyboardButton(text="📊 Статистика", callback_data="stats"))
    builder.row(InlineKeyboardButton(text="👨‍💼 Менеджер", callback_data="manager"))
    builder.row(InlineKeyboardButton(text="🔙 Главное меню", callback_data="main_menu"))
    return builder.as_markup()


async def get_applications(platform: str, page: int = 1, limit: int = 10):
    offset = (page - 1) * limit
    with db.connection:
        if platform == "avito":
            result = db.cursor.execute("""
                SELECT id, user_id, platform, citizen, age_ok, created_at 
                FROM applications 
                WHERE platform = 'Авито' 
                ORDER BY created_at DESC 
                LIMIT ? OFFSET ?
            """, (limit, offset)).fetchall()
        else:
            result = db.cursor.execute("""
                SELECT id, user_id, platform, citizen, age_ok, created_at 
                FROM applications 
                WHERE platform = 'Куфар' 
                ORDER BY created_at DESC 
                LIMIT ? OFFSET ?
            """, (limit, offset)).fetchall()

        total_count = db.cursor.execute(
            "SELECT COUNT(*) FROM applications WHERE platform = ?",
            ('Авито' if platform == "avito" else 'Куфар',)
        ).fetchone()[0]
        total_pages = (total_count + limit - 1) // limit if total_count else 1
        return result, total_pages


@router.message(Command("start"))
async def start_cmd(message: Message):
    if message.from_user.id not in ADMIN_IDS:
        await message.answer("❌ Доступ запрещён")
        return

    total = db.get_applications_count()
    today_stats = db.get_today_stats()

    await message.answer(
        f"🤖 Bot заявок\n\n"
        f"📊 Всего заявок: <b>{total}</b>\n"
        f"📅 Сегодня: <b>{today_stats['total']}</b>\n\n"
        f"👇 Выбери платформу для просмотра:",
        reply_markup=create_platform_keyboard(),
        parse_mode="HTML"
    )


@router.callback_query(F.data == "manager")
async def manager_callback(callback: CallbackQuery):
    if callback.from_user.id not in ADMIN_IDS:
        await callback.answer("❌ Доступ запрещён")
        return

    await callback.message.edit_text(
        "👨‍💼 <b>Менеджеры</b>\n\n"
        "Здесь можно:\n"
        "• Добавить менеджера по chat_id\n"
        "• Удалить менеджера по chat_id\n"
        "• Очистить все заявки",
        reply_markup=create_manager_keyboard(),
        parse_mode="HTML"
    )
    await callback.answer()


@router.callback_query(F.data == "add_manager")
async def add_manager_callback(callback: CallbackQuery, state: FSMContext):
    if callback.from_user.id not in ADMIN_IDS:
        await callback.answer("❌ Доступ запрещён")
        return

    await callback.message.edit_text(
        "Введите <b>chat_id</b> менеджера для добавления:\n\n"
        "Пример: <code>123456789</code>",
        reply_markup=create_manager_back_keyboard(),
        parse_mode="HTML"
    )
    await state.set_state(ManagerStates.waiting_manager_chat_id)
    await callback.answer()


@router.message(ManagerStates.waiting_manager_chat_id)
async def receive_manager_chat_id(message: Message, state: FSMContext):
    if message.from_user.id not in ADMIN_IDS:
        await message.answer("❌ Доступ запрещён")
        return

    text = (message.text or "").strip()

    if not text.lstrip("-").isdigit():
        await message.answer(
            "❌ Неверный chat_id.\n"
            "Отправьте только число, например: <code>123456789</code>",
            parse_mode="HTML",
            reply_markup=create_manager_back_keyboard()
        )
        return

    manager_chat_id = int(text)

    try:
        db.add_manager(manager_chat_id)
        await message.answer(
            f"✅ Менеджер добавлен.\n\nChat ID: <code>{manager_chat_id}</code>",
            parse_mode="HTML",
            reply_markup=create_manager_keyboard()
        )
    except Exception as e:
        await message.answer(
            f"❌ Не удалось добавить менеджера: {e}",
            parse_mode="HTML",
            reply_markup=create_manager_keyboard()
        )

    await state.clear()


@router.callback_query(F.data == "delete_manager")
async def delete_manager_callback(callback: CallbackQuery, state: FSMContext):
    if callback.from_user.id not in ADMIN_IDS:
        await callback.answer("❌ Доступ запрещён")
        return

    await callback.message.edit_text(
        "Введите <b>chat_id</b> менеджера для удаления:\n\n"
        "Пример: <code>123456789</code>",
        reply_markup=create_manager_back_keyboard(),
        parse_mode="HTML"
    )
    await state.set_state(ManagerStates.waiting_delete_manager_chat_id)
    await callback.answer()


@router.message(ManagerStates.waiting_delete_manager_chat_id)
async def receive_delete_manager_chat_id(message: Message, state: FSMContext):
    if message.from_user.id not in ADMIN_IDS:
        await message.answer("❌ Доступ запрещён")
        return

    text = (message.text or "").strip()

    if not text.lstrip("-").isdigit():
        await message.answer(
            "❌ Неверный chat_id.\n"
            "Отправьте только число, например: <code>123456789</code>",
            parse_mode="HTML",
            reply_markup=create_manager_back_keyboard()
        )
        return

    manager_chat_id = int(text)

    try:
        deleted = db.delete_manager(manager_chat_id)
        if deleted:
            await message.answer(
                f"✅ Менеджер удалён.\n\nChat ID: <code>{manager_chat_id}</code>",
                parse_mode="HTML",
                reply_markup=create_manager_keyboard()
            )
        else:
            await message.answer(
                f"⚠️ Менеджер не найден.\n\nChat ID: <code>{manager_chat_id}</code>",
                parse_mode="HTML",
                reply_markup=create_manager_keyboard()
            )
    except Exception as e:
        await message.answer(
            f"❌ Не удалось удалить менеджера: {e}",
            parse_mode="HTML",
            reply_markup=create_manager_keyboard()
        )

    await state.clear()


@router.callback_query(F.data == "clear_menu")
async def clear_menu_callback(callback: CallbackQuery):
    if callback.from_user.id not in ADMIN_IDS:
        await callback.answer("❌ Доступ запрещён")
        return

    await callback.message.edit_text(
        "🗑️ <b>Очистка заявок</b>\n\n"
        "Выберите, что нужно очистить:\n"
        "• 🇷🇺 Авито\n"
        "• 🇧🇾 Куфар\n"
        "• 🔸 Все заявки",
        reply_markup=create_clear_keyboard(),
        parse_mode="HTML"
    )
    await callback.answer()


@router.callback_query(F.data.in_(["clear_avito", "clear_kufar", "clear_all"]))
async def confirm_clear_callback(callback: CallbackQuery, state: FSMContext):
    if callback.from_user.id not in ADMIN_IDS:
        await callback.answer("❌ Доступ запрещён")
        return

    action = callback.data.replace("clear_", "")

    if action == "avito":
        text = "Очистить все заявки <b>Авито</b>?"
    elif action == "kufar":
        text = "Очистить все заявки <b>Куфар</b>?"
    else:
        text = "Очистить <b>ВСЕ заявки</b> (Авито + Куфар)?"

    await callback.message.edit_text(
        text,
        reply_markup=create_clear_confirm_keyboard(action),
        parse_mode="HTML"
    )
    await callback.answer()
    await state.set_state(ManagerStates.waiting_clear_applications)


@router.callback_query(F.data.startswith("confirm_clear_"))
async def execute_clear_callback(callback: CallbackQuery):
    if callback.from_user.id not in ADMIN_IDS:
        await callback.answer("❌ Доступ запрещён")
        return

    action = callback.data.replace("confirm_clear_", "")

    if action == "avito":
        count = db.clear_applications(platform="Авито")
        text = f"✅ Очистка завершена.\nУдалено заявок Авито: <b>{count}</b>"
    elif action == "kufar":
        count = db.clear_applications(platform="Куфар")
        text = f"✅ Очистка завершена.\nУдалено заявок Куфар: <b>{count}</b>"
    else:
        count = db.clear_applications(platform=None)
        text = f"✅ Очистка завершена.\nУдалено заявок всего: <b>{count}</b>"

    await callback.message.edit_text(
        text,
        reply_markup=create_manager_keyboard(),
        parse_mode="HTML"
    )
    await callback.answer()


@router.callback_query(F.data == "cancel_clear")
async def cancel_clear_callback(callback: CallbackQuery):
    if callback.from_user.id not in ADMIN_IDS:
        await callback.answer("❌ Доступ запрещён")
        return

    await callback.message.edit_text(
        "🗑️ <b>Очистка заявок</b>\n\n"
        "Выберите, что нужно очистить:\n"
        "• 🇷🇺 Авито\n"
        "• 🇧🇾 Куфар\n"
        "• 🔸 Все заявки",
        reply_markup=create_clear_keyboard(),
        parse_mode="HTML"
    )
    await callback.answer()


@router.callback_query(F.data == "main_menu")
async def main_menu_callback(callback: CallbackQuery):
    if callback.from_user.id not in ADMIN_IDS:
        await callback.answer("❌ Доступ запрещён")
        return

    total = db.get_applications_count()
    today_stats = db.get_today_stats()

    await callback.message.edit_text(
        f"🤖 Bot заявок\n\n"
        f"📊 Всего заявок: <b>{total}</b>\n"
        f"📅 Сегодня: <b>{today_stats['total']}</b>\n\n"
        f"👇 Выбери платформу для просмотра:",
        reply_markup=create_platform_keyboard(),
        parse_mode="HTML"
    )
    await callback.answer()


@router.callback_query(F.data.in_(["list_avito", "list_kufar"]))
async def list_applications(callback: CallbackQuery):
    if callback.from_user.id not in ADMIN_IDS:
        await callback.answer("❌ Доступ запрещён")
        return

    platform = "avito" if callback.data == "list_avito" else "kufar"
    platform_name = "🇷🇺 Авито" if platform == "avito" else "🇧🇾 Куфар"

    apps, total_pages = await get_applications(platform, page=1)

    if not apps:
        await callback.message.edit_text(
            f"{platform_name}: заявок пока нет",
            reply_markup=create_platform_keyboard()
        )
        await callback.answer()
        return

    text = f"{platform_name} — Последние заявки:\n\n"
    for app in apps:
        status = "✅" if app[4] else "❌"
        text += f"{status} #{app[0]} | ID: <code>{app[1]}</code>\n"
        text += f"Гражданство: {app[3]}\n"
        text += f"<i>{app[5][:16]}</i>\n\n"

    await callback.message.edit_text(
        text,
        reply_markup=create_pagination_keyboard(platform, 1, total_pages),
        parse_mode="HTML"
    )
    await callback.answer()


@router.callback_query(F.data.startswith("page_"))
async def pagination_handler(callback: CallbackQuery):
    if callback.from_user.id not in ADMIN_IDS:
        await callback.answer("❌ Доступ запрещён")
        return

    _, platform, page_str = callback.data.split("_")
    page = int(page_str)

    platform_name = "🇷🇺 Авито" if platform == "avito" else "🇧🇾 Куфар"
    apps, total_pages = await get_applications(platform, page)

    if not apps:
        await callback.answer("Заявки закончились")
        return

    text = f"{platform_name} — Страница {page}:\n\n"
    for app in apps:
        status = "✅" if app[4] else "❌"
        text += f"{status} #{app[0]} | ID: <code>{app[1]}</code>\n"
        text += f"Гражданство: {app[3]}\n"
        text += f"<i>{app[5][:16]}</i>\n\n"

    await callback.message.edit_text(
        text,
        reply_markup=create_pagination_keyboard(platform, page, total_pages),
        parse_mode="HTML"
    )
    await callback.answer()


@router.callback_query(F.data == "stats")
async def stats_callback(callback: CallbackQuery):
    if callback.from_user.id not in ADMIN_IDS:
        await callback.answer("❌ Доступ запрещён")
        return

    today_stats = db.get_today_stats()
    total = db.get_applications_count()

    text = (
        f"📊 <b>СТАТИСТИКА ЗАЯВОК</b>\n\n"
        f"📅 <b>Сегодня:</b>\n"
        f"🇷🇺 Авито: <code>{today_stats['avito']}</code>\n"
        f"🇧🇾 Куфар: <code>{today_stats['kufar']}</code>\n"
        f"📈 Всего сегодня: <code>{today_stats['total']}</code>\n\n"
        f"🔢 <b>Общий итог:</b> <code>{total}</code>"
    )

    await callback.message.edit_text(
        text,
        reply_markup=create_static_keyboard(),
        parse_mode="HTML"
    )
    await callback.answer()


@router.message()
async def echo(message: Message):
    pass


dp.include_router(router)


async def main():
    print(f"🤖 Bot B готов! Админы: {len(ADMIN_IDS)} чел.")
    try:
        await dp.start_polling(bot)
    finally:
        db.close()


if __name__ == "__main__":
    asyncio.run(main())
import asyncio
import logging
from aiogram import Bot, Dispatcher, Router, F
from aiogram.filters import Command
from aiogram.types import Message, CallbackQuery, InlineKeyboardMarkup, InlineKeyboardButton
from aiogram.fsm.context import FSMContext
from config import BOT_B_TOKEN, ADMIN_CHAT_ID, ADMIN_IDS
from db import Database
from aiogram.utils.keyboard import InlineKeyboardBuilder


logging.basicConfig(level=logging.INFO)

bot = Bot(token=BOT_B_TOKEN)
dp = Dispatcher()
router = Router()
db = Database()


def create_platform_keyboard():
    """Клавиатура выбора платформы"""
    builder = InlineKeyboardBuilder()
    builder.row(InlineKeyboardButton(text="🇷🇺 Авито", callback_data="list_avito"))
    builder.row(InlineKeyboardButton(text="🇧🇾 Куфар", callback_data="list_kufar"))
    builder.row(InlineKeyboardButton(text="📊 Статистика", callback_data="stats"))
    builder.row(InlineKeyboardButton(text="🔙 Главное меню", callback_data="main_menu"))
    return builder.as_markup()


def create_pagination_keyboard(platform: str, page: int, total_pages: int):
    """Пагинация для списка заявок"""
    builder = InlineKeyboardBuilder()
    
    # Кнопки навигации
    row = []
    if page > 1:
        row.append(InlineKeyboardButton(text="⬅️ Назад", callback_data=f"page_{platform}_{page-1}"))
    row.append(InlineKeyboardButton(text=f"{page}/{total_pages}", callback_data="none"))
    if page < total_pages:
        row.append(InlineKeyboardButton(text="Вперед ➡️", callback_data=f"page_{platform}_{page+1}"))
    builder.row(*row)
    
    # Кнопки платформы
    builder.row(InlineKeyboardButton(text="🇷🇺 Авито", callback_data="list_avito"))
    builder.row(InlineKeyboardButton(text="🇧🇾 Куфар", callback_data="list_kufar"))
    builder.row(InlineKeyboardButton(text="🔙 Главное меню", callback_data="main_menu"))
    
    return builder.as_markup()


async def get_applications(platform: str, page: int = 1, limit: int = 10):
    """Получить заявки с пагинацией"""
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
        
        # Общее количество страниц
        total_count = db.cursor.execute(
            "SELECT COUNT(*) FROM applications WHERE platform = ?", 
            ('Авито' if platform == "avito" else 'Куфар',)
        ).fetchone()[0]
        total_pages = (total_count + limit - 1) // limit
        
        return result, total_pages


@router.message(F.text.startswith("📝 НОВАЯ ЗАЯВКА"))
async def show_application(message: Message):
    print(f"🆕 НОВАЯ: {message.text[:50]}...")
    
    for admin_id in ADMIN_IDS:
        try:
            await message.forward(admin_id)
            platform = "🇷🇺 Авито" if "Авито" in message.text else "🇧🇾 Куфар"
            total = db.get_applications_count()
            await bot.send_message(
                admin_id,
                f"🆕 {platform} ЗАЯВКА #{total}\n\n"
                f"👤 ID: {message.text.split('ID: ')[1].split()[0]}\n"
                f"📱 @{message.text.split('@')[1].split()[0] if '@' in message.text else 'нет'}"
            )
        except Exception as e:
            print(f"❌ Не удалось отправить админу {admin_id}: {e}")


@router.message(Command("start"), F.text == "/start")
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
        reply_markup=create_platform_keyboard()
    )


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
        return
    
    # Формируем текст списка
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
        f"📈 Всего: <code>{today_stats['total']}</code>\n\n"
        f"🔢 <b>Общий итог:</code> {total}</b>"
    )
    
    await callback.message.edit_text(
        text,
        reply_markup=create_platform_keyboard(),
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


# Команды для удобства
@router.message(Command("stats"))
async def stats_cmd(message: Message):
    if message.from_user.id not in ADMIN_IDS:
        await message.answer("❌ Доступ запрещён")
        return
    
    today_stats = db.get_today_stats()
    total = db.get_applications_count()
    
    await message.answer(
        f"📊 <b>СТАТИСТИКА</b>\n\n"
        f"🇷🇺 Авито: {today_stats['avito']}\n"
        f"🇧🇾 Куфар: {today_stats['kufar']}\n"
        f"Всего сегодня: {today_stats['total']}\n"
        f"Общий итог: {total}",
        reply_markup=create_platform_keyboard(),
        parse_mode="HTML"
    )


@router.message(Command("avito"))
async def avito_cmd(message: Message):
    if message.from_user.id not in ADMIN_IDS:
        await message.answer("❌ Доступ запрещён")
        return
    await bot.send_message(message.chat.id, "Загрузка Авито...", reply_markup=create_platform_keyboard())
    # Симулируем callback
    fake_callback = type('obj', (object,), {'data': 'list_avito', 'from_user': message.from_user, 'message': type('msg', (object,), {'edit_text': lambda *a, **k: None})})()
    await list_applications(fake_callback)


@router.message(Command("kufar"))
async def kufar_cmd(message: Message):
    if message.from_user.id not in ADMIN_IDS:
        await message.answer("❌ Доступ запрещён")
        return
    await bot.send_message(message.chat.id, "Загрузка Куфар...", reply_markup=create_platform_keyboard())
    fake_callback = type('obj', (object,), {'data': 'list_kufar', 'from_user': message.from_user, 'message': type('msg', (object,), {'edit_text': lambda *a, **k: None})})()
    await list_applications(fake_callback)


# Игнорируем остальное
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
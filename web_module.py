#!/usr/bin/env python3
"""
Модуль веб-интеграции для WIRALIS бота.
Позволяет пользователям генерировать коды для входа на сайт.
"""

import logging
import os
import aiohttp
from datetime import datetime
from telegram import Update, InlineKeyboardMarkup, InlineKeyboardButton
from telegram.ext import CommandHandler, CallbackQueryHandler, ContextTypes
from sqlalchemy import select
from database import async_session_maker
from models import User

logger = logging.getLogger(__name__)

# Конфигурация из переменных окружения
WEBSITE_URL = os.getenv("WEBSITE_URL", "http://localhost:5000")
API_SECRET = os.getenv("TELEGRAM_BOT_API_SECRET")

if not API_SECRET:
    logger.error("TELEGRAM_BOT_API_SECRET environment variable is not set!")


async def generate_code_from_api(user_data: dict) -> dict:
    """
    Асинхронная функция для генерации кода через API сайта.
    
    Args:
        user_data: Словарь с данными пользователя
        
    Returns:
        dict: Ответ от API с кодом или ошибкой
    """
    try:
        async with aiohttp.ClientSession() as session:
            async with session.post(
                f'{WEBSITE_URL}/api/bot/generate-code',
                json=user_data,
                headers={
                    'X-API-Key': API_SECRET,
                    'Content-Type': 'application/json'
                },
                timeout=aiohttp.ClientTimeout(total=10)
            ) as response:
                if response.status == 200:
                    return await response.json()
                else:
                    error_data = await response.json()
                    error_msg = error_data.get('error', 'Неизвестная ошибка')
                    logger.error(f"API error: {response.status} - {error_msg}")
                    return {'error': error_msg, 'status': response.status}
                    
    except aiohttp.ClientTimeout:
        logger.error("API request timeout")
        return {'error': 'timeout'}
    except Exception as e:
        logger.error(f"API request error: {e}", exc_info=True)
        return {'error': 'connection_failed'}


async def web_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """
    Обработчик команды /web - генерирует код для входа на сайт.
    """
    user = update.effective_user
    
    if not user:
        await update.message.reply_text("❌ Не удалось определить пользователя.")
        return

    if not API_SECRET:
        await update.message.reply_text(
            "❌ Система временно недоступна. Обратитесь к администратору."
        )
        return

    try:
        # Получаем данные пользователя из базы данных
        async with async_session_maker() as session:
            stmt = select(User).where(User.telegram_id == user.id)
            result = await session.execute(stmt)
            db_user = result.scalar_one_or_none()

        if not db_user:
            await update.message.reply_text(
                "❌ <b>Вы не зарегистрированы в боте!</b>\n\n"
                "Используйте команду /start для регистрации.",
                parse_mode='HTML'
            )
            return

        # Формируем данные для отправки на сайт
        user_data = {
            'telegramId': db_user.telegram_id,
            'nickname': db_user.nickname,
            'username': db_user.username,
            'quote': db_user.quote,
            'botId': db_user.bot_id,
        }

        # Отправляем асинхронный запрос на сайт для генерации кода
        result = await generate_code_from_api(user_data)

        if 'error' in result:
            if result['error'] == 'timeout':
                await update.message.reply_text(
                    "⏱️ Превышено время ожидания ответа от сайта.\n"
                    "Попробуйте еще раз через несколько секунд."
                )
            elif result['error'] == 'connection_failed':
                await update.message.reply_text(
                    "❌ Не удалось связаться с сайтом.\n"
                    "Попробуйте позже или обратитесь к администратору."
                )
            else:
                await update.message.reply_text(
                    f"❌ Ошибка при генерации кода: {result['error']}\n\n"
                    "Попробуйте позже или обратитесь к администратору.",
                    parse_mode='HTML'
                )
            return

        code = result.get('code')
        expires_at = result.get('expiresAt')
        
        # Парсим время истечения
        try:
            expires = datetime.fromisoformat(expires_at.replace('Z', '+00:00'))
            expires_text = expires.strftime('%H:%M')
        except:
            expires_text = "10 минут"

        message = (
            f"🌐 <b>Код для входа на сайт WIRALIS</b>\n\n"
            f"🔑 Ваш код: <code>{code}</code>\n\n"
            f"⏰ Действителен до: {expires_text}\n\n"
            f"📝 Инструкция:\n"
            f"1. Перейдите на сайт WIRALIS\n"
            f"2. Нажмите кнопку 'Жду Сайт'\n"
            f"3. Введите код выше\n"
            f"4. Наслаждайтесь своим профилем!\n\n"
            f"💡 Код можно использовать только один раз."
        )

        keyboard = [
            [InlineKeyboardButton("🌐 Открыть сайт", url=WEBSITE_URL)],
            [InlineKeyboardButton("🔄 Новый код", callback_data="web_regenerate")]
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)

        await update.message.reply_text(
            message,
            parse_mode='HTML',
            reply_markup=reply_markup
        )

    except Exception as e:
        logger.error(f"Error in web_command: {e}", exc_info=True)
        await update.message.reply_text(
            "❌ Произошла ошибка при обработке команды.\n"
            "Попробуйте позже."
        )


async def web_regenerate_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """
    Обработчик кнопки "Новый код" - регенерирует код для пользователя.
    """
    query = update.callback_query
    await query.answer()

    user = update.effective_user
    
    if not user:
        await query.edit_message_text("❌ Не удалось определить пользователя.")
        return

    if not API_SECRET:
        await query.edit_message_text(
            "❌ Система временно недоступна. Обратитесь к администратору."
        )
        return

    try:
        # Получаем данные пользователя из базы данных
        async with async_session_maker() as session:
            stmt = select(User).where(User.telegram_id == user.id)
            result = await session.execute(stmt)
            db_user = result.scalar_one_or_none()

        if not db_user:
            await query.edit_message_text(
                "❌ <b>Вы не зарегистрированы в боте!</b>\n\n"
                "Используйте команду /start для регистрации.",
                parse_mode='HTML'
            )
            return

        # Формируем данные для отправки на сайт
        user_data = {
            'telegramId': db_user.telegram_id,
            'nickname': db_user.nickname,
            'username': db_user.username,
            'quote': db_user.quote,
            'botId': db_user.bot_id,
        }

        # Отправляем асинхронный запрос на сайт для генерации кода
        result = await generate_code_from_api(user_data)

        if 'error' in result:
            if result['error'] == 'timeout':
                await query.edit_message_text(
                    "⏱️ Превышено время ожидания ответа от сайта.\n"
                    "Попробуйте еще раз через несколько секунд."
                )
            elif result['error'] == 'connection_failed':
                await query.edit_message_text(
                    "❌ Не удалось связаться с сайтом.\n"
                    "Попробуйте позже или обратитесь к администратору."
                )
            else:
                await query.edit_message_text(
                    f"❌ Ошибка при генерации кода: {result['error']}\n\n"
                    "Попробуйте позже или обратитесь к администратору.",
                    parse_mode='HTML'
                )
            return

        code = result.get('code')
        expires_at = result.get('expiresAt')
        
        # Парсим время истечения
        try:
            expires = datetime.fromisoformat(expires_at.replace('Z', '+00:00'))
            expires_text = expires.strftime('%H:%M')
        except:
            expires_text = "10 минут"

        message = (
            f"🌐 <b>Новый код для входа на сайт WIRALIS</b>\n\n"
            f"🔑 Ваш код: <code>{code}</code>\n\n"
            f"⏰ Действителен до: {expires_text}\n\n"
            f"📝 Инструкция:\n"
            f"1. Перейдите на сайт WIRALIS\n"
            f"2. Нажмите кнопку 'Жду Сайт'\n"
            f"3. Введите код выше\n"
            f"4. Наслаждайтесь своим профилем!\n\n"
            f"💡 Код можно использовать только один раз."
        )

        keyboard = [
            [InlineKeyboardButton("🌐 Открыть сайт", url=WEBSITE_URL)],
            [InlineKeyboardButton("🔄 Новый код", callback_data="web_regenerate")]
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)

        await query.edit_message_text(
            message,
            parse_mode='HTML',
            reply_markup=reply_markup
        )

    except Exception as e:
        logger.error(f"Error in web_regenerate_callback: {e}", exc_info=True)
        await query.edit_message_text(
            "❌ Произошла ошибка при обработке запроса.\n"
            "Попробуйте позже."
        )


def setup(application):
    """
    Регистрирует обработчики модуля.
    Эта функция вызывается ядром бота при загрузке модуля.
    """
    # Регистрируем команду /web
    application.add_handler(CommandHandler("web", web_command))
    
    # Регистрируем обработчик кнопки регенерации кода
    application.add_handler(CallbackQueryHandler(web_regenerate_callback, pattern="^web_regenerate$"))
    
    logger.info("Модуль веб-интеграции загружен успешно")
    
    return [
        CommandHandler("web", web_command),
        CallbackQueryHandler(web_regenerate_callback, pattern="^web_regenerate$")
    ]


def cleanup():
    """
    Очистка ресурсов при выгрузке модуля (опционально).
    """
    logger.info("Модуль веб-интеграции выгружен")

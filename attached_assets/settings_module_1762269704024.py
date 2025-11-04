#!/usr/bin/env python3
"""
Модуль общих настроек.

Позволяет пользователям:
- Изменять свой никнейм.
- Изменять или генерировать новый ID.
- Удалять свой аккаунт с многоступенчатым подтверждением и капчей.
- Восстанавливать прогресс из старой базы данных.

Функциональность зависит от роли пользователя ('dev' или 'tester')
и наличия у него внутриигровой валюты.

Модуль адаптирован для работы в группах и защищен от основных ошибок API.
"""

import logging
import random
import string
import datetime
from typing import Dict, Any, Tuple, List

from sqlalchemy import select
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import (
    CommandHandler,
    CallbackQueryHandler,
    ConversationHandler,
    MessageHandler,
    filters,
    ContextTypes,
)
from telegram.error import BadRequest

# --- Локальные импорты ---
# Предполагается, что эти модули находятся в том же проекте
from database import async_session_maker
from models import User
from registration_module import is_user_registered, get_user_role, set_user_nickname, set_user_bot_id, regenerate_user_id as regenerate_user_bot_id, delete_account
from currency_module import currency_manager, subtract_currency
from recovery_module import db_manager as recovery_db_manager, search_and_display_profile, confirm_recovery as process_recovery_confirmation, cancel_recovery as process_recovery_cancellation


# --- Логгер ---
logger = logging.getLogger(__name__)

# --- Конфигурация ---
NICKNAME_CHANGE_COST = {'crystals': 1000, 'tokens': 100}
ID_REGEN_COST = {'crystals': 1000, 'tokens': 100}
MAX_CAPTCHA_ATTEMPTS = 3
# "Осведомленная" о часовом поясе дата для корректного сравнения
RECOVERY_CUTOFF_DATE = datetime.datetime(2024, 10, 1, tzinfo=datetime.timezone.utc)


# --- Состояния диалога ---
(
    MAIN_MENU,
    CONFIRM_NICK_CHANGE, AWAITING_NICKNAME,
    CONFIRM_ID_CHANGE, AWAITING_ID,
    CONFIRM_DELETE, FINAL_CONFIRM_DELETE, AWAITING_CAPTCHA,
    CONFIRMING_RECOVERY # Состояние из модуля восстановления
) = range(9)


# --- Вспомогательные функции ---

async def _is_initiator(update: Update, context: ContextTypes.DEFAULT_TYPE) -> bool:
    """Проверяет, является ли пользователь инициатором диалога в группе."""
    if update.effective_chat.type == 'private':
        return True

    initiator_id = context.chat_data.get('settings_initiator_id')
    user_id = update.effective_user.id

    if initiator_id is None:
        if update.callback_query:
            await update.callback_query.answer("[CMOS]: ОШИБКА: НЕ УДАЛОСЬ ОПРЕДЕЛИТЬ ИНИЦИАТОРА МЕНЮ.", show_alert=True)
            logger.warning("Settings initiator ID not found in chat_data for chat %s", update.effective_chat.id)
        return False

    if user_id != initiator_id:
        if update.callback_query:
            await update.callback_query.answer("[CMOS]: ЭТО МЕНЮ НАСТРОЕК НЕ ДЛЯ ВАС.", show_alert=True)
        return False

    return True


async def _safe_edit_message(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
    text: str,
    reply_markup: InlineKeyboardMarkup = None,
    **kwargs
) -> None:
    """
    Безопасно редактирует сообщение. Если редактирование невозможно, логирует ошибку.
    Эта функция вызывается только из обработчиков кнопок, поэтому query всегда должен быть.
    """
    query = update.callback_query
    if not query:
        logger.error("_safe_edit_message called without a CallbackQuery.")
        return

    try:
        await query.edit_message_text(text, reply_markup=reply_markup, **kwargs)
    except BadRequest as e:
        if "message is not modified" in e.message:
            # Игнорируем ошибку, если сообщение не изменилось
            pass
        else:
            logger.error("Unhandled BadRequest during message edit: %s", e)
            # В оригинальном коде была попытка пересоздания, но она может быть рискованной
            # и приводить к дублированию сообщений. Лучше просто залогировать.
    except Exception as e:
        logger.error("Failed to edit message: %s", e)


# --- Основная логика и меню ---

async def show_main_settings_menu(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """
    Центральная функция для отображения главного меню настроек.
    Вызывается как по команде /settings, так и по кнопкам "Назад".
    """
    query = update.callback_query
    user_id = update.effective_user.id

    # 1. Проверка регистрации при первом входе
    if not await is_user_registered(user_id):
        text = "<b>[CMOS]: ВЫ НЕ ЗАРЕГИСТРИРОВАНЫ. ИСПОЛЬЗУЙТЕ /START ДЛЯ НАЧАЛА.</b>"
        if query:
            await query.answer("[CMOS]: ВЫ НЕ ЗАРЕГИСТРИРОВАНЫ.", show_alert=True)
            # Попытаемся удалить старое меню, чтобы не было "мертвых" кнопок
            try:
                await query.delete_message()
            except BadRequest:
                pass
        else:
            await update.message.reply_text(text, parse_mode='HTML')
        return ConversationHandler.END

    # 2. Установка или проверка инициатора в группе
    if update.message:  # Если это команда /settings, устанавливаем инициатора
        context.chat_data['settings_initiator_id'] = user_id
    elif query:  # Если это нажатие кнопки, проверяем
        if not await _is_initiator(update, context):
            return MAIN_MENU

    # 3. Сборка текста и клавиатуры меню
    role = await get_user_role(user_id)
    currencies = await currency_manager.get_user_currencies(user_id)
    text = "<b>[CMOS]: ⚙️ ОБЩИЕ НАСТРОЙКИ</b>\n\nЗдесь вы можете управлять своим аккаунтом."
    keyboard = []

    # Кнопка изменения никнейма
    if role == 'dev':
        keyboard.append([InlineKeyboardButton("✍️ Изменить никнейм (бесплатно)", callback_data="nick_change")])
    elif currencies.get('crystals', 0) >= NICKNAME_CHANGE_COST['crystals'] or \
         currencies.get('tokens', 0) >= NICKNAME_CHANGE_COST['tokens']:
        keyboard.append([InlineKeyboardButton(f"✍️ Изменить никнейм ({NICKNAME_CHANGE_COST['crystals']}💎 / {NICKNAME_CHANGE_COST['tokens']}🪙)", callback_data="nick_change")])

    # Кнопка изменения/генерации ID
    if role == 'dev':
        keyboard.append([InlineKeyboardButton("🆔 Установить свой ID (бесплатно)", callback_data="id_change")])
    elif currencies.get('crystals', 0) >= ID_REGEN_COST['crystals'] or \
         currencies.get('tokens', 0) >= ID_REGEN_COST['tokens']:
        keyboard.append([InlineKeyboardButton(f"🔄 Сгенерировать новый ID ({ID_REGEN_COST['crystals']}💎 / {ID_REGEN_COST['tokens']}🪙)", callback_data="id_change")])

    # Кнопка восстановления прогресса
    if not await recovery_db_manager.check_if_recovered(user_id):
        async with async_session_maker() as session:
            user_creation_date = await session.scalar(select(User.created_at).where(User.telegram_id == user_id))
        
        if user_creation_date:
            user_creation_date_aware = user_creation_date.replace(tzinfo=datetime.timezone.utc)
            if user_creation_date_aware < RECOVERY_CUTOFF_DATE:
                 keyboard.append([InlineKeyboardButton("🔄 Восстановить прогресс", callback_data="start_recovery")])

    keyboard.append([InlineKeyboardButton("🔗 Внешние сервисы", callback_data="external_services")])
    keyboard.append([InlineKeyboardButton("🗑️ Удалить аккаунт", callback_data="delete_account")])
    keyboard.append([InlineKeyboardButton("❌ Закрыть", callback_data="settings_close")])
    reply_markup = InlineKeyboardMarkup(keyboard)

    # 4. Отправка или редактирование сообщения
    if query:
        await query.answer()
        await _safe_edit_message(update, context, text, reply_markup=reply_markup, parse_mode='HTML')
    else:
        await update.effective_message.reply_text(text, reply_markup=reply_markup, parse_mode='HTML')

    return MAIN_MENU


async def show_external_services_info(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Показывает информацию о внешних сервисах."""
    if not await _is_initiator(update, context):
        return MAIN_MENU

    query = update.callback_query
    await query.answer()

    text = (
        "<b>[CMOS]: 🔗 ВНЕШНИЕ СЕРВИСЫ</b>\n\n"
        "Этот раздел находится в разработке и в будущем позволит вам:\n\n"
        "🔹 <b>ПРИВЯЗАТЬ АККАУНТЫ:</b> Свяжите ваш профиль с аккаунтами в других сервисах, таких как VK или Discord, для кросс-платформенных возможностей.\n\n"
        "🔹 <b>ИНТЕГРАЦИЯ С ПОДДЕРЖКОЙ:</b> Привязка аккаунта упростит вашу идентификацию при обращении в службу поддержки, которая скоро появится.\n\n"
        "Следите за обновлениями!"
    )
    keyboard = [[InlineKeyboardButton("⬅️ Назад", callback_data="settings_back")]]
    reply_markup = InlineKeyboardMarkup(keyboard)

    await _safe_edit_message(update, context, text, reply_markup=reply_markup, parse_mode='HTML')

    return MAIN_MENU


def _create_payment_keyboard(currencies: Dict[str, int], cost: Dict[str, int], prefix: str) -> InlineKeyboardMarkup:
    """Вспомогательная функция для создания клавиатуры выбора валюты."""
    payment_options = []
    if currencies.get('crystals', 0) >= cost['crystals']:
        payment_options.append(InlineKeyboardButton(f"Оплатить {cost['crystals']} 💎", callback_data=f"{prefix}_pay_crystals"))
    if currencies.get('tokens', 0) >= cost['tokens']:
        payment_options.append(InlineKeyboardButton(f"Оплатить {cost['tokens']} 🪙", callback_data=f"{prefix}_pay_tokens"))

    keyboard = [payment_options, [InlineKeyboardButton("⬅️ Назад", callback_data="settings_back")]]
    return InlineKeyboardMarkup(keyboard)


# --- Флоу: Смена никнейма ---

async def confirm_nick_change(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Запрашивает подтверждение и способ оплаты для смены никнейма."""
    if not await _is_initiator(update, context):
        return CONFIRM_NICK_CHANGE

    query = update.callback_query
    await query.answer()
    user_id = query.from_user.id
    role = await get_user_role(user_id)

    if role == 'dev':
        text = "<b>[CMOS]: ВВЕДИТЕ ВАШ НОВЫЙ НИКНЕЙМ</b>\n\n(от 1 до 50 символов)"
        await _safe_edit_message(update, context, text, parse_mode='HTML')
        return AWAITING_NICKNAME

    currencies = await currency_manager.get_user_currencies(user_id)
    keyboard = _create_payment_keyboard(currencies, NICKNAME_CHANGE_COST, "nick")
    text = "<b>[CMOS]: ВЫБЕРИТЕ ВАЛЮТУ ДЛЯ ОПЛАТЫ СМЕНЫ НИКНЕЙМА</b>"
    await _safe_edit_message(update, context, text, reply_markup=keyboard, parse_mode='HTML')
    return CONFIRM_NICK_CHANGE


async def process_nick_payment(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Обрабатывает оплату и, в случае успеха, запрашивает новый никнейм."""
    if not await _is_initiator(update, context):
        return CONFIRM_NICK_CHANGE

    query = update.callback_query
    await query.answer()
    user_id = query.from_user.id

    currency_to_use = query.data.split('_')[2]
    cost = NICKNAME_CHANGE_COST[currency_to_use]

    if await subtract_currency(user_id, currency_to_use, cost):
        text = "<b>[CMOS]: ✅ ОПЛАТА ПРОШЛА УСПЕШНО.</b>\n\nВведите ваш новый никнейм (от 1 до 50 символов):"
        await _safe_edit_message(update, context, text, parse_mode='HTML')
        return AWAITING_NICKNAME

    text = "<b>[CMOS]: ❌ ОШИБКА ОПЛАТЫ. НЕДОСТАТОЧНО СРЕДСТВ.</b>"
    keyboard = [[InlineKeyboardButton("⬅️ Назад", callback_data="settings_back")]]
    await _safe_edit_message(update, context, text, reply_markup=InlineKeyboardMarkup(keyboard), parse_mode='HTML')
    return MAIN_MENU


async def process_new_nickname(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Получает и сохраняет новый никнейм."""
    user_id = update.effective_user.id
    new_nickname = update.message.text.strip()

    if not (1 <= len(new_nickname) <= 50):
        await update.message.reply_text("<b>[CMOS]: ОШИБКА. ВВЕДИТЕ КОРРЕКТНОЕ ИМЯ (ОТ 1 ДО 50 СИМВОЛОВ).</b>", parse_mode='HTML')
        return AWAITING_NICKNAME

    if await set_user_nickname(user_id, new_nickname):
        await update.message.reply_text(f"<b>[CMOS]: ✅ ВАШ НИКНЕЙМ УСПЕШНО ИЗМЕНЕН НА:</b>\n\n<b>{new_nickname}</b>", parse_mode='HTML')
    else:
        await update.message.reply_text("<b>[CMOS]: ❌ ПРОИЗОШЛА ОШИБКА ПРИ СМЕНЕ НИКНЕЙМА.</b>", parse_mode='HTML')

    return ConversationHandler.END


# --- Флоу: Смена ID ---

async def confirm_id_change(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Запрашивает подтверждение и способ оплаты для смены ID."""
    if not await _is_initiator(update, context):
        return CONFIRM_ID_CHANGE

    query = update.callback_query
    await query.answer()
    user_id = query.from_user.id
    role = await get_user_role(user_id)

    if role == 'dev':
        text = "<b>[CMOS]: ВВЕДИТЕ ВАШ НОВЫЙ ID</b>\n\n(4 латинские буквы или цифры)"
        await _safe_edit_message(update, context, text, parse_mode='HTML')
        return AWAITING_ID

    currencies = await currency_manager.get_user_currencies(user_id)
    keyboard = _create_payment_keyboard(currencies, ID_REGEN_COST, "id")
    text = "<b>[CMOS]: ВЫБЕРИТЕ ВАЛЮТУ ДЛЯ ОПЛАТЫ ГЕНЕРАЦИИ НОВОГО ID</b>"
    await _safe_edit_message(update, context, text, reply_markup=keyboard, parse_mode='HTML')
    return CONFIRM_ID_CHANGE


async def process_id_payment_and_regen(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Обрабатывает оплату и генерирует новый ID для игрока."""
    if not await _is_initiator(update, context):
        return CONFIRM_ID_CHANGE

    query = update.callback_query
    await query.answer()
    user_id = query.from_user.id
    currency_to_use = query.data.split('_')[2]
    cost = ID_REGEN_COST[currency_to_use]

    if not await subtract_currency(user_id, currency_to_use, cost):
        text = "<b>[CMOS]: ❌ ОШИБКА ОПЛАТЫ. НЕДОСТАТОЧНО СРЕДСТВ.</b>"
        keyboard = [[InlineKeyboardButton("⬅️ Назад", callback_data="settings_back")]]
        await _safe_edit_message(update, context, text, reply_markup=InlineKeyboardMarkup(keyboard), parse_mode='HTML')
        return MAIN_MENU

    new_id = await regenerate_user_bot_id(user_id)
    if new_id:
        text = f"<b>[CMOS]: ✅ ОПЛАТА ПРОШЛА УСПЕШНО.</b>\n\nВАШ НОВЫЙ ID: <b>{new_id}</b>"
        await _safe_edit_message(update, context, text, parse_mode='HTML')
    else:
        text = "<b>[CMOS]: ❌ ПРОИЗОШЛА ОШИБКА ПРИ ГЕНЕРАЦИИ НОВОГО ID.</b>"
        await _safe_edit_message(update, context, text, parse_mode='HTML')

    # Завершаем диалог после генерации ID
    return ConversationHandler.END


async def process_new_id(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Получает и устанавливает новый ID от разработчика."""
    user_id = update.effective_user.id
    new_id = update.message.text.strip().upper()

    success, message = await set_user_bot_id(user_id, new_id)
    styled_message = f"<b>[CMOS]: {message.upper()}</b>"
    await update.message.reply_text(styled_message, parse_mode='HTML')

    return ConversationHandler.END if success else AWAITING_ID


# --- Флоу: Удаление аккаунта ---

async def confirm_delete_account(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Первое подтверждение удаления аккаунта."""
    if not await _is_initiator(update, context):
        return CONFIRM_DELETE

    query = update.callback_query
    await query.answer()
    text = "<b>[CMOS]: ВЫ УВЕРЕНЫ, ЧТО ХОТИТЕ УДАЛИТЬ АККАУНТ?</b>\n\nЭто действие необратимо."
    keyboard = [
        [InlineKeyboardButton("Да, я уверен", callback_data="delete_confirm_1")],
        [InlineKeyboardButton("⬅️ Назад", callback_data="settings_back")]
    ]
    await _safe_edit_message(update, context, text, reply_markup=InlineKeyboardMarkup(keyboard), parse_mode='HTML')
    return CONFIRM_DELETE


async def final_confirm_delete(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Второе и последнее подтверждение удаления."""
    if not await _is_initiator(update, context):
        return FINAL_CONFIRM_DELETE

    query = update.callback_query
    await query.answer()
    text = "<b>[CMOS]: ‼️ ПОСЛЕДНЕЕ ПРЕДУПРЕЖДЕНИЕ</b> ‼️\n\nВсе ваши данные будут стерты навсегда. Подтвердить удаление?"
    keyboard = [
        [InlineKeyboardButton("🔴 ПОДТВЕРДИТЬ УДАЛЕНИЕ 🔴", callback_data="delete_confirm_2")],
        [InlineKeyboardButton("⬅️ Назад", callback_data="settings_back")]
    ]
    await _safe_edit_message(update, context, text, reply_markup=InlineKeyboardMarkup(keyboard), parse_mode='HTML')
    return FINAL_CONFIRM_DELETE


async def ask_for_captcha(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Запрашивает ввод капчи перед удалением."""
    if not await _is_initiator(update, context):
        return AWAITING_CAPTCHA

    query = update.callback_query
    await query.answer()
    captcha_word = ''.join(random.choices(string.ascii_uppercase + string.digits, k=5))
    context.user_data['captcha_word'] = captcha_word
    context.user_data['captcha_attempts'] = 0

    text = (f"<b>[CMOS]: ДЛЯ ПОДТВЕРЖДЕНИЯ ОКОНЧАТЕЛЬНОГО УДАЛЕНИЯ,</b>\n\n"
            f"пожалуйста, введите слово: <code>{captcha_word}</code>")

    await _safe_edit_message(update, context, text, parse_mode='HTML')
    return AWAITING_CAPTCHA


async def process_captcha(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Проверяет введенную капчу."""
    user_input = update.message.text.strip()
    correct_word = context.user_data.get('captcha_word')

    if user_input.upper() == correct_word:
        return await process_delete_account(update, context)

    context.user_data['captcha_attempts'] += 1
    if context.user_data['captcha_attempts'] >= MAX_CAPTCHA_ATTEMPTS:
        text = "<b>[CMOS]: СЛИШКОМ МНОГО НЕВЕРНЫХ ПОПЫТОК.</b>\n\nПроцесс удаления аккаунта отменен в целях безопасности."
        await update.message.reply_text(text, parse_mode='HTML')
        return ConversationHandler.END

    remaining_attempts = MAX_CAPTCHA_ATTEMPTS - context.user_data['captcha_attempts']
    await update.message.reply_text(
        f"<b>[CMOS]: НЕВЕРНОЕ СЛОВО.</b>\n\n"
        f"Пожалуйста, попробуйте еще раз. Осталось попыток: {remaining_attempts}",
        parse_mode='HTML'
    )
    return AWAITING_CAPTCHA


async def process_delete_account(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Выполняет удаление аккаунта из базы данных."""
    user_id = update.effective_user.id
    if await delete_account(user_id):
        text = "<b>[CMOS]: ВАШ АККАУНТ БЫЛ БЕЗВОЗВРАТНО УДАЛЕН.</b>\n\nДля продолжения используйте /start для новой регистрации."
    else:
        text = "<b>[CMOS]: ПРОИЗОШЛА ОШИБКА ПРИ УДАЛЕНИИ АККАУНТА.</b>\n\nПожалуйста, свяжитесь с поддержкой."

    # Сообщение с капчей было в чате, а не в виде inline-клавиатуры. Отвечаем на него.
    await update.message.reply_text(text, parse_mode='HTML')

    return ConversationHandler.END


# --- Флоу: Восстановление прогресса ---

async def start_recovery_from_settings(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Начинает процесс восстановления из меню настроек."""
    if not await _is_initiator(update, context):
        return MAIN_MENU

    query = update.callback_query
    await query.answer()

    user = update.effective_user
    chat_id = update.effective_chat.id

    # Удаляем текущее меню, чтобы не было конфликтов
    try:
        await query.delete_message()
    except BadRequest:
        pass
    
    await context.bot.send_message(
        chat_id=chat_id,
        text="<b>[CMOS]: ИНИЦИАЛИЗАЦИЯ ПРОЦЕССА ВОССТАНОВЛЕНИЯ...</b>\n\nПОДКЛЮЧАЮСЬ К АРХИВАМ...",
        parse_mode='HTML'
    )
    
    context.job_queue.run_once(
        search_and_display_profile,
        when=1,
        data={'chat_id': chat_id, 'user_id': user.id},
        name=f"recovery_{user.id}"
    )

    return CONFIRMING_RECOVERY

# --- Общие обработчики диалога ---

async def close_settings(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Закрывает (удаляет) сообщение с настройками."""
    if not await _is_initiator(update, context):
        return ConversationHandler.END

    query = update.callback_query
    await query.answer()
    try:
        await query.delete_message()
    except BadRequest as e:
        logger.warning(f"Could not delete settings message: {e}")

    if 'settings_initiator_id' in context.chat_data:
        del context.chat_data['settings_initiator_id']

    return ConversationHandler.END


async def cancel(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Отменяет текущее действие и завершает диалог (для /cancel)."""
    await update.message.reply_text("<b>[CMOS]: ДЕЙСТВИЕ ОТМЕНЕНО.</b>", parse_mode='HTML')
    if 'settings_initiator_id' in context.chat_data:
        del context.chat_data['settings_initiator_id']
    return ConversationHandler.END


# --- Инициализация модуля ---

def setup(config: Any) -> Tuple[List[Any], List[str]]:
    """Инициализирует модуль настроек, регистрирует обработчики."""
    conv_handler = ConversationHandler(
        entry_points=[
            CommandHandler("settings", show_main_settings_menu),
            CallbackQueryHandler(show_main_settings_menu, pattern="^settings_open$")
        ],
        states={
            MAIN_MENU: [
                CallbackQueryHandler(confirm_nick_change, pattern="^nick_change$"),
                CallbackQueryHandler(confirm_id_change, pattern="^id_change$"),
                CallbackQueryHandler(show_external_services_info, pattern="^external_services$"),
                CallbackQueryHandler(confirm_delete_account, pattern="^delete_account$"),
                CallbackQueryHandler(start_recovery_from_settings, pattern="^start_recovery$"),
                CallbackQueryHandler(show_main_settings_menu, pattern="^settings_back$")
            ],
            CONFIRM_NICK_CHANGE: [
                CallbackQueryHandler(process_nick_payment, pattern="^nick_pay_(crystals|tokens)$"),
                CallbackQueryHandler(show_main_settings_menu, pattern="^settings_back$")
            ],
            AWAITING_NICKNAME: [MessageHandler(filters.TEXT & ~filters.COMMAND, process_new_nickname)],
            CONFIRM_ID_CHANGE: [
                CallbackQueryHandler(process_id_payment_and_regen, pattern="^id_pay_(crystals|tokens)$"),
                CallbackQueryHandler(show_main_settings_menu, pattern="^settings_back$")
            ],
            AWAITING_ID: [MessageHandler(filters.TEXT & ~filters.COMMAND, process_new_id)],
            CONFIRM_DELETE: [
                CallbackQueryHandler(final_confirm_delete, pattern="^delete_confirm_1$"),
                CallbackQueryHandler(show_main_settings_menu, pattern="^settings_back$")
            ],
            FINAL_CONFIRM_DELETE: [
                CallbackQueryHandler(ask_for_captcha, pattern="^delete_confirm_2$"),
                CallbackQueryHandler(show_main_settings_menu, pattern="^settings_back$")
            ],
            AWAITING_CAPTCHA: [MessageHandler(filters.TEXT & ~filters.COMMAND, process_captcha)],
            CONFIRMING_RECOVERY: [
                CallbackQueryHandler(process_recovery_confirmation, pattern=r"^recovery_confirm$"),
                CallbackQueryHandler(process_recovery_cancellation, pattern=r"^recovery_cancel$"),
            ],
        },
        fallbacks=[
            CommandHandler("cancel", cancel),
            CallbackQueryHandler(close_settings, pattern="^settings_close$")
        ],
        per_message=False,
        allow_reentry=True
    )

    logger.info("Модуль настроек инициализирован.")
    return [conv_handler], ["settings", "cancel"]


def cleanup():
    """Очищает ресурсы модуля при выгрузке."""
    logger.info("Модуль настроек выгружен.")
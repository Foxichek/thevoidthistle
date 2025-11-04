#!/usr/bin/env python3
"""
Модульное ядро Telegram бота
Версия: 2.5.0 (расширение Core-панели, защита SQL, шаблоны запросов)
Автор: Claude AI & Gemini & Human
Лучшая дата: 26.08.2025
"""

import os
import sys
import logging
import importlib
import inspect
import traceback
import asyncio
import time
import gc
import html
from pathlib import Path
from typing import Dict, List, Optional, Any
from dataclasses import dataclass
from datetime import datetime

import psutil
import telegram
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup, User as TelegramUser, CallbackQuery
from telegram.constants import ParseMode
from telegram.ext import (
    Application,
    CommandHandler,
    CallbackQueryHandler,
    MessageHandler,
    ContextTypes,
    ConversationHandler,
    filters,
    ApplicationHandlerStop,
    ApplicationBuilder,
    JobQueue
)
from telegram.error import BadRequest, TimedOut, NetworkError, Forbidden, RetryAfter

# --- Интеграция с PostgreSQL ---
from sqlalchemy import select, func, text, inspect as sa_inspect
import asyncpg
from database import async_session_maker
from models import User as DBUser # Переименовываем, чтобы избежать конфликта с telegram.User

# Состояния для ConversationHandler
(
    WAITING_SQL_PASSWORD,
    WAITING_SQL_QUERY,
    WAITING_USER_ID_FOR_SEARCH
) = range(3)


# Конфигурация
@dataclass
class Config:
    """Конфигурация бота"""
    BOT_TOKEN: str = "8356657882:AAEpaidp5ci6nN1d-bXElFN9OzggoAgbPD4" # Токен бота
    OWNER_IDS: List[int] = None # Айди овнеров
    MODULES_DIR: str = "modules" # Директория с модулями
    LOG_LEVEL: str = "INFO" # Уровень логирования
    DB_EXEC_PASSWORD: str = "_1337_Crystal-Madness_404_Asteron#_banana[labats]brc" # Пароль для выполнения RAW SQL запросов

    def __post_init__(self):
        if self.OWNER_IDS is None:
            self.OWNER_IDS = [7992966340, 1971071274]


# Система модулей
class ModuleInfo:
    """Информация о модуле"""
    def __init__(self, name: str, module_obj: Any):
        self.name = name
        self.module_obj = module_obj
        self.handlers: List = []
        self.commands: List[str] = []
        self.loaded_at = datetime.now()
        self.enabled = True
        self.error_count = 0
        self.last_error = None


class ModuleManager:
    """Менеджер модулей"""

    def __init__(self, modules_dir: str = "modules"):
        self.modules_dir = Path(modules_dir)
        self.modules: Dict[str, ModuleInfo] = {}
        self.logger = logging.getLogger(f"{__name__}.ModuleManager")

        # Создаем директорию модулей если её нет
        self.modules_dir.mkdir(exist_ok=True)
        # Добавляем путь к модулям в sys.path если его там нет
        modules_path = str(self.modules_dir.absolute())
        if modules_path not in sys.path:
            sys.path.insert(0, modules_path)

    def discover_modules(self) -> List[str]:
        """Поиск модулей в директории"""
        modules = []

        if not self.modules_dir.exists():
            return modules

        for file_path in self.modules_dir.glob("*.py"):
            if file_path.name.startswith("_"):
                continue
            module_name = file_path.stem
            modules.append(module_name)

        return modules

    def load_module(self, module_name: str) -> Optional[ModuleInfo]:
        """Загрузка модуля (только импорт)"""
        try:
            if module_name in sys.modules:
                module = importlib.reload(sys.modules[module_name])
            else:
                module = importlib.import_module(module_name)

            if not hasattr(module, 'setup'):
                self.logger.error(f"Модуль {module_name} не имеет функции setup()")
                return None

            module_info = ModuleInfo(name=module_name, module_obj=module)
            self.modules[module_name] = module_info

            self.logger.info(f"Модуль {module_name} успешно импортирован.")
            return module_info

        except Exception as e:
            self.logger.error(f"Ошибка загрузки (импорта) модуля {module_name}: {e}")
            self.logger.debug(traceback.format_exc())
            return None

    def unload_module(self, module_name: str) -> bool:
        """Выгрузка модуля"""
        if module_name not in self.modules:
            return False

        try:
            module_info = self.modules[module_name]
            if hasattr(module_info.module_obj, 'cleanup'):
                try:
                    # Передаем ядро в cleanup, если он это поддерживает
                    cleanup_args = inspect.signature(module_info.module_obj.cleanup).parameters
                    if 'core' in cleanup_args:
                         module_info.module_obj.cleanup(core=self)
                    else:
                         module_info.module_obj.cleanup()
                except Exception as e:
                    self.logger.warning(f"Ошибка cleanup модуля {module_name}: {e}")

            del self.modules[module_name]

            if module_name in sys.modules:
                del sys.modules[module_name]

            self.logger.info(f"Модуль {module_name} выгружен")
            return True

        except Exception as e:
            self.logger.error(f"Ошибка выгрузки модуля {module_name}: {e}")
            return False

    def get_module_status(self) -> List[Dict]:
        """Получить статус всех модулей в виде списка словарей"""
        status_list = []
        for name, info in self.modules.items():
            try:
                # Получаем функции модуля
                functions = [f_name for f_name, _ in inspect.getmembers(info.module_obj, inspect.isfunction)]
                # Получаем путь к файлу
                file_path = inspect.getsourcefile(info.module_obj)
            except (TypeError, OSError):
                functions = ["не удалось получить"]
                file_path = "не удалось получить"

            status_list.append({
                'name': name,
                'enabled': info.enabled,
                'loaded_at': info.loaded_at.strftime('%Y-%m-%d %H:%M:%S'),
                'commands': info.commands,
                'handlers_count': len(info.handlers),
                'error_count': info.error_count,
                'last_error': str(info.last_error) if info.last_error else "Нет",
                'functions': functions,
                'file_path': file_path,
            })
        return sorted(status_list, key=lambda x: x['name'])


class BotCore:
    """Основное ядро бота"""

    def __init__(self, config: Config = None):
        self.config = config or Config()
        self.application: Optional[Application] = None
        self.module_manager = ModuleManager(self.config.MODULES_DIR)

        self.setup_logging()
        self.logger = logging.getLogger(__name__)

        self.start_time = datetime.now()
        self.maintenance_mode = False
        self.sql_password_verified = False # Флаг для сессионного пароля SQL

        # Новая система логирования ядра
        self.kernel_logs: List[Dict] = []

        # --- LEGACY SUPPORT v1.3.5 ---
        # Этот словарь используется для поддержки старых модулей, которые обращаются к core.users.
        # Он заполняется данными из БД при запуске. Новые модули должны работать напрямую с БД.
        self.users: Dict[int, TelegramUser] = {}
        # -----------------------------

        self.stats = {
            'messages_processed': 0,
            'commands_executed': 0,
            'errors': 0,
            'module_reloads': 0,
            'uptime_seconds': 0
        }
        self._log_kernel_event("KERNEL STABLE", "Инициализация ядра", "Успешно")

    def setup_logging(self):
        """Настройка логирования в файл и консоль"""
        logging.basicConfig(
            format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
            level=getattr(logging, self.config.LOG_LEVEL),
            handlers=[
                logging.StreamHandler(sys.stdout),
                logging.FileHandler('bot.log', encoding='utf-8')
            ]
        )

    # --- Новая система логирования ядра ---
    def _log_kernel_event(self, level: str, action: str, outcome: str):
        """Записывает событие в сессионный лог ядра."""
        log_entry = {
            "timestamp": datetime.now(),
            "level": level,
            "action": action,
            "outcome": outcome
        }
        self.kernel_logs.append(log_entry)

        if level == "KERNEL PANIC":
            # Неблокирующая отправка уведомления владельцам
            asyncio.create_task(self._panic_notify(log_entry))

    async def _panic_notify(self, log_entry: Dict):
        """Отправляет уведомление о панике владельцам."""
        self.logger.critical(f"KERNEL PANIC: {log_entry['action']} -> {log_entry['outcome']}")
        text = (
            f"‼️ <b>KERNEL PANIC</b> ‼️\n\n"
            f"<b>Действие:</b> {self.escape_html(log_entry['action'])}\n"
            f"<b>Исход:</b> {self.escape_html(log_entry['outcome'])}\n"
            f"<b>Время:</b> {log_entry['timestamp'].strftime('%Y-%m-%d %H:%M:%S')}"
        )
        for owner_id in self.config.OWNER_IDS:
            await self.safe_send_message(owner_id, text, parse_mode=ParseMode.HTML)
    # ------------------------------------

    # --- LEGACY SUPPORT v1.3.5 ---
    async def track_user(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """
        Обработчик для обратной совместимости. Наполняет старый словарь self.users.
        Новые модули не должны на него полагаться.
        """
        user = update.effective_user
        if user and user.id not in self.users:
            self.users[user.id] = user
            self.logger.info(f"[LEGACY] Обнаружен новый пользователь: {user.full_name} ({user.id})")
            # Примечание: современная логика должна записывать пользователя в БД в своих обработчиках.
            # Этот метод лишь обеспечивает наполнение старого словаря для совместимости.

    async def _load_users_from_db_to_legacy_dict(self):
        """При старте загружает пользователей из БД (PostgreSQL) в legacy-словарь self.users."""
        self._log_kernel_event("KERNEL STABLE", "Загрузка пользователей в legacy-словарь", "Начало")
        try:
            async with async_session_maker() as session:
                stmt = select(DBUser.telegram_id, DBUser.nickname)
                result = await session.execute(stmt)
                for telegram_id, nickname in result.all():
                    if telegram_id not in self.users:
                        self.users[telegram_id] = TelegramUser(id=telegram_id, first_name=nickname or "Unknown", is_bot=False)
            self._log_kernel_event("KERNEL STABLE", "Загрузка пользователей в legacy-словарь", f"Успешно, загружено {len(self.users)} пользователей")
        except Exception as e:
            self.logger.error(f"Не удалось загрузить пользователей в legacy-словарь: {e}")
            self._log_kernel_event("KERNEL ERROR", "Загрузка пользователей в legacy-словарь", str(e))
    # -----------------------------

    def is_owner(self, user_id: int) -> bool:
        """Проверка является ли пользователь овнером"""
        return user_id in self.config.OWNER_IDS

    def escape_html(self, text: str) -> str:
        """Экранирование символов для HTML."""
        return html.escape(str(text))

    async def safe_send_message(self, chat_id: int, text: str, parse_mode=None, reply_markup=None):
        """Безопасная отправка сообщения с обработкой ошибок"""
        try:
            if self.application and self.application.bot:
                return await self.application.bot.send_message(
                    chat_id=chat_id,
                    text=text,
                    parse_mode=parse_mode,
                    reply_markup=reply_markup
                )
        except (BadRequest, Forbidden) as e:
            self.logger.warning(f"Ошибка (BadRequest/Forbidden) при отправке сообщения в чат {chat_id}: {e}")
            if parse_mode:
                try:
                    return await self.application.bot.send_message(
                        chat_id=chat_id,
                        text=text,
                        reply_markup=reply_markup
                    )
                except Exception as e2:
                    self.logger.error(f"Не удалось отправить сообщение в чат {chat_id} даже без форматирования: {e2}")
        except Exception as e:
            self.logger.error(f"Неизвестная ошибка отправки сообщения в чат {chat_id}: {e}")
        return None

    async def core_menu(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Core меню"""
        try:
            if not self.is_owner(update.effective_user.id):
                await update.message.reply_text("❌ У вас нет прав для выполнения этой команды")
                return

            reply_markup = self.get_main_core_keyboard()
            await update.message.reply_text(
                "🎛 <b>Панель управления ядром</b>",
                reply_markup=reply_markup,
                parse_mode=ParseMode.HTML
            )
        except Exception as e:
            self.logger.error(f"Ошибка в core_menu: {e}")
            self.stats['errors'] += 1
            await update.message.reply_text("❌ Ошибка при отображении меню")

    async def core_callback(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Обработка кнопок core меню"""
        query = update.callback_query
        data = ""
        try:
            await query.answer()

            if not self.is_owner(query.from_user.id):
                await query.edit_message_text("❌ У вас нет прав")
                return

            data = query.data

            if data == "core_stats":
                await self.show_stats(query)
            elif data.startswith("core_modules_page_"):
                page = int(data.split("_")[-1])
                await self.show_modules(query, page)
            elif data.startswith("core_users_page_"):
                page = int(data.split("_")[-1])
                await self.show_users(query, page)
            elif data == "core_toggle_maintenance":
                await self.toggle_maintenance_mode(query)
            elif data == "core_restart_menu":
                await self.show_restart_menu(query)
            elif data == "core_reload_all_modules":
                await self.reload_all_modules(query)
            elif data == "core_restart_bot":
                await self.restart_bot(query)
            elif data == "core_gc":
                await self.run_garbage_collection(query)
            elif data == "core_logs":
                await self.show_logs(query)
            elif data.startswith("core_kernel_logs_page_"):
                page = int(data.split("_")[-1])
                await self.show_kernel_logs(query, page)
            elif data == "core_db_menu":
                await self.show_db_menu(query)
            elif data == "core_db_info":
                await self.show_db_info(query)
            elif data == "core_db_template_last5users":
                await self.handle_template_last5users(query)
            elif data == "core_close":
                await query.message.delete()
            elif data == "core_back_to_main":
                 await query.message.edit_text("🎛 <b>Панель управления ядром</b>", reply_markup=self.get_main_core_keyboard(), parse_mode=ParseMode.HTML)

        except Exception as e:
            self.logger.error(f"Ошибка в core_callback: {e} | Data: {data}")
            self.logger.debug(traceback.format_exc())
            self.stats['errors'] += 1
            try:
                await query.edit_message_text("❌ Произошла ошибка. Смотрите логи.")
            except:
                pass

    def get_main_core_keyboard(self) -> InlineKeyboardMarkup:
        """Возвращает клавиатуру главного core-меню"""
        maintenance_button_text = "🔴 Выключить тех. режим" if self.maintenance_mode else "🟢 Включить тех. режим"
        keyboard = [
            [InlineKeyboardButton("📊 Статистика", callback_data="core_stats")],
            [InlineKeyboardButton("🔌 Модули", callback_data="core_modules_page_0")],
            [InlineKeyboardButton("👥 Пользователи", callback_data="core_users_page_0")],
            [InlineKeyboardButton("🗄️ База данных", callback_data="core_db_menu")],
            [InlineKeyboardButton(maintenance_button_text, callback_data="core_toggle_maintenance")],
            [InlineKeyboardButton("⚙️ Перезагрузка", callback_data="core_restart_menu")],
            [InlineKeyboardButton("🧹 Очистка памяти", callback_data="core_gc")],
            [InlineKeyboardButton("📝 Логи (Файл)", callback_data="core_logs")],
            [InlineKeyboardButton("📓 Логи (Ядро)", callback_data="core_kernel_logs_page_0")],
            [InlineKeyboardButton("❌ Закрыть", callback_data="core_close")],
        ]
        return InlineKeyboardMarkup(keyboard)

    def _create_progress_bar(self, progress: float) -> str:
        """Создает текстовый прогресс-бар."""
        bar_length = 10
        filled_length = int(bar_length * progress)
        bar = '█' * filled_length + '░' * (bar_length - filled_length)
        return f"<code>[{bar}]</code> <b>{progress:.0%}</b>"

    async def show_restart_menu(self, query: CallbackQuery):
        """Показывает меню выбора перезагрузки."""
        keyboard = [
            [InlineKeyboardButton("🔄 Перезагрузить модули", callback_data="core_reload_all_modules")],
            [InlineKeyboardButton("💥 Перезагрузить ядро", callback_data="core_restart_bot")],
            [InlineKeyboardButton("⬅️ Назад", callback_data="core_back_to_main")]
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)
        text = (
            "⚙️ <b>Меню перезагрузки</b>\n\n"
            "Выберите тип перезагрузки:\n"
            "  • <i>Модули</i> - быстрая перезагрузка кода модулей без остановки бота.\n"
            "  • <i>Ядро</i> - полная перезагрузка всего процесса бота."
        )
        await query.edit_message_text(
            text,
            reply_markup=reply_markup,
            parse_mode=ParseMode.HTML
        )

    def format_bytes(self, size_bytes):
        """Конвертирует байты в читаемый формат"""
        if size_bytes == 0:
            return "0B"
        power = 1024
        n = 0
        power_labels = {0: '', 1: 'K', 2: 'M', 3: 'G', 4: 'T'}
        while size_bytes >= power and n < len(power_labels):
            size_bytes /= power
            n += 1
        return f"{size_bytes:.2f} {power_labels[n]}B"

    async def show_stats(self, query):
        """Показать расширенную статистику"""
        try:
            uptime = datetime.now() - self.start_time
            self.stats['uptime_seconds'] = uptime.total_seconds()

            process = psutil.Process()
            cpu_percent = psutil.cpu_percent(interval=0.1)
            cpu_cores = psutil.cpu_count(logical=False)
            cpu_threads = psutil.cpu_count(logical=True)
            cpu_freq = psutil.cpu_freq()
            bot_memory_mb = process.memory_info().rss / 1024 / 1024
            virt_mem = psutil.virtual_memory()
            disk = psutil.disk_usage('/')

            user_count = "..."
            try:
                async with async_session_maker() as session:
                    stmt = select(func.count()).select_from(DBUser)
                    count_res = await session.execute(stmt)
                    user_count = count_res.scalar_one()
            except Exception as e:
                self.logger.error(f"Ошибка подсчета пользователей в БД: {e}")
                self._log_kernel_event("KERNEL_ERROR", "Статистика БД", str(e))
                user_count = f"Ошибка: {self.escape_html(str(e))}"

            parts = [
                "📊 <b>Расширенная статистика</b>",
                "",
                "<b>Бот:</b>",
                f"  <code>Время работы      :</code> {str(uptime).split('.')[0]}",
                f"  <code>Сообщений         :</code> {self.stats['messages_processed']}",
                f"  <code>Команд            :</code> {self.stats['commands_executed']}",
                f"  <code>Ошибок            :</code> {self.stats['errors']}",
                f"  <code>Модулей загружено :</code> {len(self.module_manager.modules)}",
                f"  <code>Пользователей (БД):</code> {user_count}",
                f"  <code>Пользователей (Legacy):</code> {len(self.users)}",
                "",
                "<b>Система:</b>",
                f"  <code>CPU Нагрузка      :</code> {cpu_percent}%",
                f"  <code>CPU Ядер/Потоков  :</code> {cpu_cores}/{cpu_threads}",
                f"  <code>CPU Частота       :</code> {cpu_freq.current:.0f} MHz",
                f"  <code>Память (Бот)      :</code> {bot_memory_mb:.2f} МБ",
                f"  <code>Память (Система)  :</code> {self.format_bytes(virt_mem.used)} / {self.format_bytes(virt_mem.total)} ({virt_mem.percent}%)",
                f"  <code>Диск              :</code> {self.format_bytes(disk.used)} / {self.format_bytes(disk.total)} ({disk.percent}%)",
                "",
                "<b>Окружение:</b>",
                f"  <code>Python            :</code> {self.escape_html(sys.version.split(' ')[0])}",
                f"  <code>python-telegram-bot:</code> {self.escape_html(telegram.__version__)}",
            ]
            text = "\n".join(parts)

            await query.edit_message_text(
                text,
                parse_mode=ParseMode.HTML,
                reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("⬅️ Назад", callback_data="core_back_to_main")]])
            )
        except Exception as e:
            self.logger.error(f"Неизвестная ошибка в show_stats: {e}")
            self._log_kernel_event("KERNEL_WARNING", "Отображение статистики", str(e))
            await query.edit_message_text("Не удалось получить статистику.", reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("⬅️ Назад", callback_data="core_back_to_main")]]))

    async def show_modules(self, query, page=0, page_size=5):
        """Показать информацию о модулях с пагинацией"""
        all_modules_status = self.module_manager.get_module_status()

        if not all_modules_status:
            await query.edit_message_text("🔌 Модули не загружены", reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("⬅️ Назад", callback_data="core_back_to_main")]]))
            return

        total_modules = len(all_modules_status)
        total_pages = (total_modules + page_size - 1) // page_size

        start_index = page * page_size
        end_index = start_index + page_size
        modules_on_page = all_modules_status[start_index:end_index]

        text_parts = [f"🔌 <b>Состояние модулей (Страница {page + 1}/{total_pages})</b>\n"]

        for info in modules_on_page:
            safe_name = self.escape_html(info['name'])
            status_icon = "✅" if info['enabled'] else "❌"
            error_info = f" ({info['error_count']} ошибок)" if info['error_count'] > 0 else ""

            functions_list = f"<code>{self.escape_html(', '.join(info['functions'][:3]))}{', ...' if len(info['functions']) > 3 else ''}</code>"

            module_text = (
                f"{status_icon} <b>{safe_name}</b>{error_info}\n"
                f"  ├ <i>Загружен:</i> <code>{self.escape_html(info['loaded_at'])}</code>\n"
                f"  ├ <i>Команды:</i> <code>{self.escape_html(str(info['commands']))}</code>\n"
                f"  ├ <i>Обработчики:</i> <code>{info['handlers_count']}</code>\n"
                f"  ├ <i>Функции:</i> {functions_list}\n"
                f"  └ <i>Ошибка:</i> <code>{self.escape_html(info['last_error'])}</code>"
            )
            text_parts.append(module_text)

        text = "\n\n".join(text_parts)

        keyboard = []
        row = []
        if page > 0:
            row.append(InlineKeyboardButton("⬅️", callback_data=f"core_modules_page_{page-1}"))
        if page < total_pages - 1:
            row.append(InlineKeyboardButton("➡️", callback_data=f"core_modules_page_{page+1}"))
        keyboard.append(row)
        keyboard.append([InlineKeyboardButton("⬅️ Назад в меню", callback_data="core_back_to_main")])

        await query.edit_message_text(text, parse_mode=ParseMode.HTML, reply_markup=InlineKeyboardMarkup(keyboard))

    async def show_users(self, query, page=0, page_size=10):
        """Показать список пользователей из БД с пагинацией"""
        user_list = []
        total_users = 0
        try:
            async with async_session_maker() as session:
                # Получаем общее количество
                count_stmt = select(func.count()).select_from(DBUser)
                total_users = (await session.execute(count_stmt)).scalar_one()

                # Получаем пользователей для текущей страницы
                stmt = select(DBUser).order_by(DBUser.id.desc()).limit(page_size).offset(page * page_size)
                result = await session.execute(stmt)
                user_list = result.scalars().all()

        except Exception as e:
            self.logger.error(f"Ошибка получения пользователей из БД: {e}")
            self._log_kernel_event("KERNEL_ERROR", "Отображение пользователей", str(e))
            await query.edit_message_text(f"❌ Ошибка доступа к базе данных пользователей: {self.escape_html(str(e))}", reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("⬅️ Назад", callback_data="core_back_to_main")]]))
            return

        total_pages = (total_users + page_size - 1) // page_size or 1

        text = f"👥 <b>Список пользователей ({page * page_size + 1}-{min((page + 1) * page_size, total_users)} из {total_users})</b>\n\n"

        if not user_list:
            text += "<i>Пользователи не найдены.</i>"
        else:
            for user in user_list:
                nickname = self.escape_html(user.nickname or "N/A")
                reg_date_obj = user.created_at.strftime('%Y-%m-%d')
                text += f"<code>{user.telegram_id}</code> - {nickname} (рег.: {reg_date_obj})\n"

        keyboard = []
        row = []
        if page > 0:
            row.append(InlineKeyboardButton("⬅️", callback_data=f"core_users_page_{page-1}"))
        if page < total_pages - 1:
            row.append(InlineKeyboardButton("➡️", callback_data=f"core_users_page_{page+1}"))
        keyboard.append(row)
        keyboard.append([InlineKeyboardButton("⬅️ Назад в меню", callback_data="core_back_to_main")])

        await query.edit_message_text(text, parse_mode=ParseMode.HTML, reply_markup=InlineKeyboardMarkup(keyboard))

    async def toggle_maintenance_mode(self, query):
        """Включение/выключение режима обслуживания"""
        self.maintenance_mode = not self.maintenance_mode
        status = "ВКЛЮЧЕН" if self.maintenance_mode else "ВЫКЛЮЧЕН"
        self._log_kernel_event("KERNEL STABLE", "Режим тех. обслуживания", status)

        if self.maintenance_mode:
            await query.answer("⚙️ Включаю режим технического обслуживания...")
            status_text = "🔴 Режим технического обслуживания <b>ВКЛЮЧЕН</b>."
        else:
            await query.answer("✅ Выключаю режим технического обслуживания...")
            status_text = "🟢 Режим технического обслуживания <b>ВЫКЛЮЧЕН</b>."

        await query.edit_message_text(status_text, parse_mode=ParseMode.HTML, reply_markup=self.get_main_core_keyboard())

    async def run_garbage_collection(self, query):
        """Запустить сборку мусора"""
        await query.edit_message_text("🧹 Очищаю память...")

        process = psutil.Process()
        memory_before = process.memory_info().rss / 1024 / 1024
        collected = gc.collect()
        memory_after = process.memory_info().rss / 1024 / 1024
        freed = memory_before - memory_after

        self._log_kernel_event("KERNEL STABLE", "Сборка мусора", f"Освобождено {freed:.2f} МБ")

        text = (
            f"🧹 <b>Очистка памяти завершена</b>\n\n"
            f"Собрано объектов: <code>{collected}</code>\n"
            f"Освобождено: <code>{freed:.2f}</code> МБ\n"
            f"Память сейчас: <code>{memory_after:.2f}</code> МБ"
        )
        await query.edit_message_text(text, parse_mode=ParseMode.HTML, reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("⬅️ Назад", callback_data="core_back_to_main")]])
        )

    async def show_logs(self, query):
        """Показать последние записи из файла лога"""
        try:
            with open('bot.log', 'r', encoding='utf-8') as f:
                lines = f.readlines()
                last_lines = lines[-15:] if len(lines) >= 15 else lines

            log_text = "".join(last_lines)
            if not log_text:
                log_text = "Лог-файл пуст."

            escaped_log = self.escape_html(log_text.strip())
            text = f"📝 <b>Последние 15 записей лога (bot.log):</b>\n\n<pre><code>{escaped_log}</code></pre>"

            if len(text) > 4000:
                text = text[:4000] + "...</code></pre>"

            await query.edit_message_text(text, parse_mode=ParseMode.HTML, reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("⬅️ Назад", callback_data="core_back_to_main")]]))
        except Exception as e:
            await query.edit_message_text(f"❌ Ошибка чтения лога: {self.escape_html(str(e))}", reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("⬅️ Назад", callback_data="core_back_to_main")]]))

    async def show_kernel_logs(self, query, page=0, page_size=5):
        """Показать сессионные логи ядра с пагинацией."""
        if not self.kernel_logs:
            await query.edit_message_text("📓 <b>Логи ядра пусты в этой сессии.</b>", parse_mode=ParseMode.HTML, reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("⬅️ Назад", callback_data="core_back_to_main")]]))
            return

        # Показываем самые новые логи сначала
        logs_to_show = list(reversed(self.kernel_logs))

        total_logs = len(logs_to_show)
        total_pages = (total_logs + page_size - 1) // page_size

        start_index = page * page_size
        end_index = start_index + page_size
        logs_on_page = logs_to_show[start_index:end_index]

        text = f"📓 <b>Логи ядра (Страница {page + 1}/{total_pages})</b>\n\n"

        level_icons = {
            "KERNEL STABLE": "✅",
            "KERNEL WARNING": "⚠️",
            "KERNEL ERROR": "❌",
            "KERNEL PANIC": "‼️"
        }

        for log in logs_on_page:
            icon = level_icons.get(log['level'], "❓")
            time_str = log['timestamp'].strftime('%H:%M:%S')
            text += (
                f"{icon} [<code>{time_str}</code>] <b>{self.escape_html(log['action'])}</b>\n"
                f"   └ <i>{self.escape_html(log['outcome'])}</i>\n"
            )

        keyboard = []
        row = []
        if page > 0:
            row.append(InlineKeyboardButton("⬅️", callback_data=f"core_kernel_logs_page_{page-1}"))
        if page < total_pages - 1:
            row.append(InlineKeyboardButton("➡️", callback_data=f"core_kernel_logs_page_{page+1}"))
        keyboard.append(row)
        keyboard.append([InlineKeyboardButton("⬅️ Назад в меню", callback_data="core_back_to_main")])

        await query.edit_message_text(text, parse_mode=ParseMode.HTML, reply_markup=InlineKeyboardMarkup(keyboard))

    async def reload_all_modules(self, query: CallbackQuery) -> bool:
        """Перезагрузка всех модулей с отображением прогресса"""
        success = True
        chat_id = query.message.chat_id
        message_id = query.message.message_id
        last_update_time = time.time()

        self._log_kernel_event("KERNEL STABLE", "Перезагрузка всех модулей", "Начало")

        async def update_progress(current, total, stage_text):
            nonlocal last_update_time
            if time.time() - last_update_time < 1.0 and current != total: return
            progress = current / total if total > 0 else 1
            bar = self._create_progress_bar(progress)
            text = f"⚙️ <b>Перезагрузка модулей</b>\n\n{bar}\n\n<i>Этап:</i> {self.escape_html(stage_text)}"
            try:
                await self.application.bot.edit_message_text(text, chat_id=chat_id, message_id=message_id, parse_mode=ParseMode.HTML)
                last_update_time = time.time()
            except RetryAfter as e: await asyncio.sleep(e.retry_after)
            except BadRequest: pass
            except Exception as e: self.logger.warning(f"Не удалось обновить прогресс перезагрузки: {e}")

        try:
            modules_to_unload = list(self.module_manager.modules.keys())

            # --- Определение общего количества шагов для прогресс-бара ---
            discovered_modules = self.module_manager.discover_modules()
            # Шаги: выгрузка + импорт + регистрация ресурсов + настройка
            total_steps = len(modules_to_unload) + len(discovered_modules) * 3
            current_step = 0

            await update_progress(0, total_steps, "Начало выгрузки модулей...")

            # Шаг 1: Выгрузка
            if self.application:
                for module_name in modules_to_unload:
                    current_step += 1
                    await update_progress(current_step, total_steps, f"Выгрузка: {module_name}")
                    module_info = self.module_manager.modules.get(module_name)
                    if module_info and module_info.handlers:
                        for handler in module_info.handlers: self.application.remove_handler(handler)
                    self.module_manager.unload_module(module_name)
                    await asyncio.sleep(0.1)

            self.module_manager.modules.clear()

            # Удаляем старые менеджеры из ядра
            # Это важно, чтобы при перезагрузке не остались ссылки на старые объекты
            attrs_to_delete = [attr for attr in dir(self) if attr.endswith("_manager") and attr != 'module_manager']
            for attr in attrs_to_delete:
                delattr(self, attr)

            progress_data = {'chat_id': chat_id, 'message_id': message_id, 'current_step': current_step, 'total_steps': total_steps}
            await self.load_and_register_modules(progress_data=progress_data)

            await self.application.bot.edit_message_text(
                "✅ <b>Все модули успешно перезагружены!</b>",
                chat_id=chat_id, message_id=message_id, parse_mode=ParseMode.HTML,
                reply_markup=self.get_main_core_keyboard()
            )
            self.stats['module_reloads'] += 1
            self._log_kernel_event("KERNEL STABLE", "Перезагрузка всех модулей", "Успешно")

        except Exception as e:
            self.logger.error(f"Критическая ошибка при перезагрузке модулей: {e}")
            self.logger.debug(traceback.format_exc())
            self._log_kernel_event("KERNEL ERROR", "Перезагрузка всех модулей", str(e))
            success = False
            error_message = self.escape_html(str(e))
            await self.application.bot.edit_message_text(
                f"⚠️ <b>Перезагрузка завершена с ошибками:</b>\n<code>{error_message}</code>",
                chat_id=chat_id, message_id=message_id, parse_mode=ParseMode.HTML,
                reply_markup=self.get_main_core_keyboard()
            )
        return success

    async def restart_bot(self, query: CallbackQuery):
        """Перезапускает ядро бота."""
        try:
            await query.answer("Перезагрузка ядра...")
            self._log_kernel_event("KERNEL STABLE", "Перезапуск ядра", f"Инициирован {query.from_user.id}")
            await query.edit_message_text("🤖 <b>Ядро бота перезагружается...</b>", parse_mode=ParseMode.HTML)
            os.execv(sys.executable, ['python'] + sys.argv)

        except Exception as e:
            self.logger.critical(f"Критическая ошибка при перезапуске ядра: {e}")
            self._log_kernel_event("KERNEL PANIC", "Перезапуск ядра", str(e))
            error_message = self.escape_html(str(e))
            await query.edit_message_text(f"❌ <b>Не удалось перезапустить ядро:</b>\n<code>{error_message}</code>", parse_mode=ParseMode.HTML)

    async def load_and_register_modules(self, progress_data: Optional[Dict] = None):
        """
        Обнаруживает, загружает и регистрирует все модули, используя трёхэтапную систему
        для безопасного разрешения зависимостей.
        """
        last_update_time = time.time()

        async def update_progress(current, total, stage_text):
            nonlocal last_update_time
            if not progress_data: return
            if time.time() - last_update_time < 1.0 and current != total: return

            base_progress = progress_data.get('current_step', 0)
            total_steps = progress_data.get('total_steps', total)

            progress = (base_progress + current) / total_steps if total_steps > 0 else 1
            bar = self._create_progress_bar(progress)
            text = f"⚙️ <b>Загрузка модулей</b>\n\n{bar}\n\n<i>Этап:</i> {self.escape_html(stage_text)}"
            try:
                await self.application.bot.edit_message_text(
                    text, chat_id=progress_data['chat_id'], message_id=progress_data['message_id'],
                    parse_mode=ParseMode.HTML)
                last_update_time = time.time()
            except RetryAfter as e: await asyncio.sleep(e.retry_after)
            except BadRequest: pass
            except Exception as e: self.logger.warning(f"Не удалось обновить прогресс загрузки: {e}")

        self.logger.info("--- Начало загрузки модулей (3 этапа) ---")
        self._log_kernel_event("KERNEL STABLE", "Загрузка модулей", "Начало")
        discovered_modules = self.module_manager.discover_modules()

        # Если total_steps не задан, вычисляем его для 3 этапов
        if progress_data and 'total_steps' not in progress_data:
             progress_data['total_steps'] = len(discovered_modules) * 3

        total_modules_count = len(discovered_modules)
        current_step = 0

        # --- ЭТАП 1: ИМПОРТ МОДУЛЕЙ ---
        self.logger.info("--- [Этап 1/3] Импорт всех модулей ---")
        for module_name in discovered_modules:
            current_step += 1
            await update_progress(current_step, total_modules_count * 3, f"Импорт: {module_name}")
            module_info = self.module_manager.load_module(module_name)
            if not module_info or not module_info.module_obj:
                self._log_kernel_event("KERNEL WARNING", f"Импорт модуля {module_name}", "Неудачно")
            await asyncio.sleep(0.05)

        # --- ЭТАП 2: РЕГИСТРАЦИЯ ОБЩИХ РЕСУРСОВ ---
        self.logger.info("--- [Этап 2/3] Регистрация общих ресурсов (менеджеров) ---")
        for module_name, module_info in self.module_manager.modules.items():
            current_step += 1
            await update_progress(current_step, total_modules_count * 3, f"Поиск ресурсов в {module_name}")
            for attr_name in dir(module_info.module_obj):
                if attr_name.endswith("_manager"):
                    manager_instance = getattr(module_info.module_obj, attr_name)
                    if not hasattr(self, attr_name):
                        setattr(self, attr_name, manager_instance)
                        self.logger.info(f"Обнаружен и зарегистрирован менеджер: '{attr_name}' из модуля '{module_name}'")
                        self._log_kernel_event("KERNEL STABLE", "Регистрация ресурса", f"{attr_name} из {module_name}")
                    else:
                        self.logger.warning(f"Менеджер с именем '{attr_name}' уже существует. Пропускаем экземпляр из '{module_name}'.")
            await asyncio.sleep(0.05)

        # --- ЭТАП 3: НАСТРОЙКА МОДУЛЕЙ И РЕГИСТРАЦИЯ ОБРАБОТЧИКОВ ---
        self.logger.info("--- [Этап 3/3] Настройка модулей и регистрация обработчиков ---")
        for module_name, module_info in self.module_manager.modules.items():
            current_step += 1
            await update_progress(current_step, total_modules_count * 3, f"Настройка: {module_name}")
            try:
                # Передаем self (ядро) со всеми зарегистрированными менеджерами
                handlers, commands = module_info.module_obj.setup(self)
                module_info.handlers, module_info.commands = handlers or [], commands or []
                if self.application:
                    for handler in module_info.handlers:
                        if handler: self.application.add_handler(handler)
                self.logger.info(f"Модуль {module_name} настроен. {len(module_info.handlers)} обработчиков.")
                self._log_kernel_event("KERNEL STABLE", f"Настройка модуля {module_name}", "Успешно")
            except Exception as e:
                self.logger.error(f"Ошибка setup модуля {module_name}: {e}")
                self.logger.debug(traceback.format_exc())
                self._log_kernel_event("KERNEL ERROR", f"Настройка модуля {module_name}", str(e))
                module_info.error_count += 1
                module_info.last_error = str(e)
            await asyncio.sleep(0.05)

        self.logger.info("--- Загрузка модулей завершена ---")
        self._log_kernel_event("KERNEL STABLE", "Загрузка модулей", f"Завершено, {len(self.module_manager.modules)} модулей")

    async def maintenance_check_handler(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Обработчик, блокирующий пользователей в режиме обслуживания"""
        if not self.maintenance_mode or (update.effective_user and self.is_owner(update.effective_user.id)):
            return
        if update.message and update.message.text.startswith('/core'): return
        raise ApplicationHandlerStop

    # --- Новые и улучшенные методы для работы с БД ---

    def _format_sql_result(self, headers: List[str], rows: List[Any], limit: int = 20) -> str:
        """Вспомогательная функция для форматирования результатов SQL-запроса в текст."""
        if not rows:
            return "✅ Запрос выполнен успешно, но не вернул строк."

        def truncate(s, max_len=30):
            s_str = str(s)
            return (s_str[:max_len-3] + '...') if len(s_str) > max_len else s_str

        # Форматируем таблицу
        table = [f"<code>{', '.join(map(truncate, headers))}</code>"]
        for row in rows:
            table.append(f"<code>{', '.join(map(truncate, row))}</code>")

        response_text = f"✅ <b>Результат (первые {len(rows)} из {len(rows)} строк):</b>\n\n" + "\n".join(table)
        if len(rows) >= limit:
            response_text += f"\n\n<i>(Вывод ограничен {limit} строками)</i>"
        return response_text

    async def show_db_menu(self, query: CallbackQuery):
        """Показывает расширенное меню управления базой данных."""
        keyboard = [
            [InlineKeyboardButton("ℹ️ Информация о БД", callback_data="core_db_info")],
            [InlineKeyboardButton("USERS: 5 последних", callback_data="core_db_template_last5users")],
            [InlineKeyboardButton("USERS: Найти по ID", callback_data="core_db_template_find_user")],
            [InlineKeyboardButton("✏️ Выполнить RAW SQL", callback_data="core_db_execute_sql")],
            [InlineKeyboardButton("⬅️ Назад", callback_data="core_back_to_main")]
        ]
        text = "🗄️ <b>Меню управления базой данных</b>\n\nВыберите действие:"
        await query.edit_message_text(text, reply_markup=InlineKeyboardMarkup(keyboard), parse_mode=ParseMode.HTML)

    async def show_db_info(self, query: CallbackQuery):
        """Показывает информацию о базе данных и таблицах."""
        await query.edit_message_text("🔄 Получаю информацию о БД...", parse_mode=ParseMode.HTML)
        response_text = ""  # Переименовали переменную
        try:
            async with async_session_maker() as session:
                # Получаем версию PostgreSQL
                version_result = await session.execute(text("SELECT version()"))
                pg_version = version_result.scalar_one().split(',')[0]

                # Получаем список таблиц и количество строк
                async_conn = await session.connection()
                inspector = sa_inspect(async_conn)
                table_names = await inspector.get_table_names()

                table_info = []
                for table in sorted(table_names):
                    count_res = await session.execute(text(f'SELECT COUNT(*) FROM "{table}"'))
                    count = count_res.scalar_one()
                    table_info.append(f"  • <code>{table}</code>: {count} строк")

            text_parts = [
                "🗄️ <b>Информация о базе данных</b>",
                "",
                f"<b>Тип:</b> <code>PostgreSQL</code>",
                f"<b>Версия:</b> <code>{self.escape_html(pg_version)}</code>",
                "",
                "<b>Таблицы:</b>",
                "\n".join(table_info) if table_info else "<i>Таблицы не найдены.</i>"
            ]
            response_text = "\n".join(text_parts)
            self._log_kernel_event("KERNEL STABLE", "Просмотр информации о БД", "Успешно")

        except Exception as e:
            self.logger.error(f"Ошибка получения информации о БД: {e}")
            self._log_kernel_event("KERNEL_ERROR", "Просмотр информации о БД", str(e))
            response_text = f"❌ <b>Ошибка получения информации о БД:</b>\n<code>{self.escape_html(str(e))}</code>"

        keyboard = [[InlineKeyboardButton("⬅️ Назад", callback_data="core_db_menu")]]
        await query.edit_message_text(response_text, reply_markup=InlineKeyboardMarkup(keyboard), parse_mode=ParseMode.HTML)

    async def start_sql_execution(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
        """Начало диалога для выполнения SQL-запроса с проверкой пароля."""
        query = update.callback_query
        
        if self.sql_password_verified:
            keyboard = [[InlineKeyboardButton("❌ Отмена", callback_data="core_sql_cancel")]]
            await query.edit_message_text(
                "️✏️ Отправьте SQL-запрос для выполнения.\n\n"
                "<b>Внимание:</b> этот инструмент может повредить или удалить данные.",
                reply_markup=InlineKeyboardMarkup(keyboard),
                parse_mode=ParseMode.HTML
            )
            return WAITING_SQL_QUERY
        else:
            keyboard = [[InlineKeyboardButton("❌ Отмена", callback_data="core_sql_cancel")]]
            await query.edit_message_text(
                "🔐 <b>Требуется аутентификация</b>\n\n"
                "Для выполнения RAW SQL-запросов, пожалуйста, введите пароль, указанный в `DB_EXEC_PASSWORD` конфигурации ядра.",
                reply_markup=InlineKeyboardMarkup(keyboard),
                parse_mode=ParseMode.HTML
            )
            return WAITING_SQL_PASSWORD

    async def check_sql_password(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
        """Проверяет введенный пароль для доступа к SQL."""
        password = update.message.text
        if password == self.config.DB_EXEC_PASSWORD:
            self.sql_password_verified = True
            self._log_kernel_event("KERNEL STABLE", "Доступ к SQL", f"Пароль принят от {update.effective_user.id}")
            await update.message.reply_text(
                "✅ Пароль принят. Теперь отправьте SQL-запрос для выполнения."
            )
            return WAITING_SQL_QUERY
        else:
            self._log_kernel_event("KERNEL WARNING", "Доступ к SQL", f"Неверный пароль от {update.effective_user.id}")
            await update.message.reply_text("❌ Неверный пароль. Диалог завершен.")
            await self.core_menu(update, context) # Возвращаем главное меню
            return ConversationHandler.END

    async def execute_sql_query(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
        """Выполняет полученный SQL-запрос."""
        sql_query = update.message.text
        await update.message.reply_text("🔄 Выполняю запрос...", parse_mode=ParseMode.HTML)

        try:
            async with async_session_maker() as session:
                async with session.begin(): # Начинаем транзакцию
                    result = await session.execute(text(sql_query))

                    if result.returns_rows:
                        rows = result.fetchmany(20) # Ограничиваем вывод
                        headers = result.keys()
                        response_text = self._format_sql_result(headers, rows, limit=20)
                    else:
                        response_text = f"✅ Запрос выполнен успешно. Затронуто строк: <b>{result.rowcount}</b>"
                
                self._log_kernel_event("KERNEL WARNING", "Выполнение SQL", f"Успешно: {sql_query[:50]}...")
        except Exception as e:
            self.logger.error(f"Ошибка выполнения SQL-запроса: {e}")
            self._log_kernel_event("KERNEL ERROR", "Выполнение SQL", str(e))
            response_text = f"❌ <b>Ошибка выполнения запроса:</b>\n\n<pre><code>{self.escape_html(str(e))}</code></pre>"

        keyboard = [[InlineKeyboardButton("⬅️ Назад в меню БД", callback_data="core_db_menu")]]
        if len(response_text) > 4096:
            response_text = response_text[:4090] + "..."
        await update.message.reply_text(response_text, parse_mode=ParseMode.HTML, reply_markup=InlineKeyboardMarkup(keyboard))
        return ConversationHandler.END

    async def cancel_sql_execution(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
        """Отменяет выполнение SQL-запроса."""
        if update.callback_query:
            query = update.callback_query
            await query.answer()
            await self.show_db_menu(query)
        else:
            await update.message.reply_text("❌ Выполнение SQL-запроса отменено.")
            await self.core_menu(update, context)

        return ConversationHandler.END

    async def handle_template_last5users(self, query: CallbackQuery):
        """Выполняет шаблонный запрос для показа 5 последних пользователей."""
        await query.edit_message_text("🔄 Получаю 5 последних пользователей...", parse_mode=ParseMode.HTML)
        try:
            async with async_session_maker() as session:
                stmt = select(DBUser).order_by(DBUser.id.desc()).limit(5)
                result = await session.execute(stmt)
                users = result.scalars().all()
                
                if not users:
                    response_text = "<i>В базе данных нет пользователей.</i>"
                else:
                    headers = ["id", "telegram_id", "nickname", "username", "created_at"]
                    rows = [[u.id, u.telegram_id, u.nickname, u.username, u.created_at.strftime('%Y-%m-%d')] for u in users]
                    response_text = self._format_sql_result(headers, rows, limit=5)

        except Exception as e:
            self.logger.error(f"Ошибка выполнения шаблона (last5users): {e}")
            self._log_kernel_event("KERNEL ERROR", "Шаблон last5users", str(e))
            response_text = f"❌ <b>Ошибка выполнения запроса:</b>\n<code>{self.escape_html(str(e))}</code>"
        
        keyboard = [[InlineKeyboardButton("⬅️ Назад", callback_data="core_db_menu")]]
        await query.edit_message_text(response_text, parse_mode=ParseMode.HTML, reply_markup=InlineKeyboardMarkup(keyboard))
    
    async def start_find_user_by_id(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
        """Начинает диалог для поиска пользователя по ID."""
        query = update.callback_query
        keyboard = [[InlineKeyboardButton("❌ Отмена", callback_data="core_find_user_cancel")]]
        await query.edit_message_text(
            "🆔 Введите Telegram ID пользователя, которого хотите найти.",
            reply_markup=InlineKeyboardMarkup(keyboard)
        )
        return WAITING_USER_ID_FOR_SEARCH

    async def find_user_by_id(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
        """Ищет пользователя по ID и выводит результат."""
        user_id_str = update.message.text
        if not user_id_str.isdigit():
            await update.message.reply_text("❌ Telegram ID должен быть числом. Попробуйте снова.")
            return WAITING_USER_ID_FOR_SEARCH

        user_id = int(user_id_str)
        await update.message.reply_text(f"🔄 Ищу пользователя с ID <code>{user_id}</code>...", parse_mode=ParseMode.HTML)

        try:
            async with async_session_maker() as session:
                stmt = select(DBUser).where(DBUser.telegram_id == user_id)
                result = await session.execute(stmt)
                user = result.scalar_one_or_none()

                if not user:
                    response_text = f"🤷‍♂️ Пользователь с Telegram ID <code>{user_id}</code> не найден."
                else:
                    headers = ["Атрибут", "Значение"]
                    rows = [
                        ["id", user.id],
                        ["telegram_id", user.telegram_id],
                        ["nickname", user.nickname],
                        ["username", user.username or "N/A"],
                        ["bot_id", user.bot_id],
                        ["role", user.role],
                        ["quote", user.quote or "N/A"],
                        ["created_at", user.created_at.strftime('%Y-%m-%d %H:%M:%S')]
                    ]
                    response_text = self._format_sql_result(headers, rows, limit=20)
        
        except Exception as e:
            self.logger.error(f"Ошибка выполнения шаблона (find_user): {e}")
            self._log_kernel_event("KERNEL ERROR", "Шаблон find_user", str(e))
            response_text = f"❌ <b>Ошибка выполнения запроса:</b>\n<code>{self.escape_html(str(e))}</code>"

        keyboard = [[InlineKeyboardButton("⬅️ Назад в меню БД", callback_data="core_db_menu")]]
        await update.message.reply_text(response_text, parse_mode=ParseMode.HTML, reply_markup=InlineKeyboardMarkup(keyboard))
        return ConversationHandler.END

    async def cancel_find_user(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
        """Отменяет диалог поиска пользователя."""
        query = update.callback_query
        await query.answer()
        await self.show_db_menu(query)
        return ConversationHandler.END


    async def setup_handlers(self):
        """Настройка базовых обработчиков"""
        self._log_kernel_event("KERNEL STABLE", "Настройка обработчиков", "Начало")
        # Группа -10: самая первая проверка на тех. режим
        self.application.add_handler(MessageHandler(filters.ALL, self.maintenance_check_handler), group=-10)
        # Группа -1: обработчик для legacy-совместимости
        self.application.add_handler(MessageHandler(filters.ALL, self.track_user), group=-1)

        # Диалог для выполнения RAW SQL
        sql_conv_handler = ConversationHandler(
            entry_points=[CallbackQueryHandler(self.start_sql_execution, pattern="^core_db_execute_sql$")],
            states={
                WAITING_SQL_PASSWORD: [MessageHandler(filters.TEXT & ~filters.COMMAND, self.check_sql_password)],
                WAITING_SQL_QUERY: [MessageHandler(filters.TEXT & ~filters.COMMAND, self.execute_sql_query)],
            },
            fallbacks=[
                CommandHandler("cancel", self.cancel_sql_execution),
                CallbackQueryHandler(self.cancel_sql_execution, pattern="^core_sql_cancel$")
            ],
            per_message=False,
            conversation_timeout=120
        )
        self.application.add_handler(sql_conv_handler)

        # Диалог для поиска пользователя по ID
        find_user_conv_handler = ConversationHandler(
            entry_points=[CallbackQueryHandler(self.start_find_user_by_id, pattern="^core_db_template_find_user$")],
            states={
                WAITING_USER_ID_FOR_SEARCH: [MessageHandler(filters.TEXT & ~filters.COMMAND, self.find_user_by_id)],
            },
            fallbacks=[
                CallbackQueryHandler(self.cancel_find_user, pattern="^core_find_user_cancel$"),
            ],
            per_message=False,
            conversation_timeout=60
        )
        self.application.add_handler(find_user_conv_handler)

        self.application.add_handler(CommandHandler("core", self.core_menu))
        self.application.add_handler(CallbackQueryHandler(self.core_callback, pattern="^core_"))
        self._log_kernel_event("KERNEL STABLE", "Настройка обработчиков", "Успешно")

    async def post_init(self, application: Application):
        """Инициализация после создания приложения"""
        self._log_kernel_event("KERNEL STABLE", "post_init", "Начало")
        try:
            self.logger.info("Бот инициализируется...")
            await self.setup_handlers()
            await self._load_users_from_db_to_legacy_dict() # Загружаем пользователей для legacy

            progress_messages = {}
            for owner_id in self.config.OWNER_IDS:
                msg = await self.safe_send_message(owner_id, "🚀 <b>Запуск ядра...</b>", parse_mode=ParseMode.HTML)
                if msg: progress_messages[owner_id] = msg.message_id

            if progress_messages:
                main_owner_id = next(iter(progress_messages))
                main_message_id = progress_messages[main_owner_id]
                await self.load_and_register_modules(progress_data={'chat_id': main_owner_id, 'message_id': main_message_id})

                for owner_id, message_id in progress_messages.items():
                    try:
                        await self.application.bot.edit_message_text(
                            "🚀 <b>Бот полностью запущен и готов к работе!</b>",
                            chat_id=owner_id, message_id=message_id, parse_mode=ParseMode.HTML)
                    except Exception: pass
            else:
                 await self.load_and_register_modules()

            self._log_kernel_event("KERNEL STABLE", "post_init", "Завершено успешно")
        except Exception as e:
            self.logger.critical(f"Ошибка в post_init: {e}")
            self._log_kernel_event("KERNEL PANIC", "post_init", str(e))
            raise

    def run(self):
        """Запуск бота"""
        try:
            # --- ИСПРАВЛЕНИЕ ---
            # Явно создаем JobQueue и передаем его в ApplicationBuilder
            job_queue = JobQueue()
            self.application = (Application.builder()
                              .token(self.config.BOT_TOKEN)
                              .post_init(self.post_init)
                              .job_queue(job_queue)
                              .build())

            self._log_kernel_event("KERNEL STABLE", "Запуск polling", "Начало")
            self.application.run_polling(allowed_updates=Update.ALL_TYPES)
        except KeyboardInterrupt:
            self.logger.info("Получен сигнал остановки")
            self._log_kernel_event("KERNEL STABLE", "Остановка бота", "Пользователь прервал выполнение")
        except Exception as e:
            self.logger.critical(f"Критическая ошибка при запуске: {e}")
            self._log_kernel_event("KERNEL PANIC", "Критическая ошибка запуска", str(e))
            self.logger.debug(traceback.format_exc())
        finally:
            self.logger.info("Бот остановлен.")

def main():
    """Точка входа"""
    try:
        config = Config()
        bot = BotCore(config)
        bot.run()
    except Exception as e:
        logging.critical(f"Критическая ошибка в main: {e}")
        logging.debug(traceback.format_exc())

if __name__ == "__main__":
    main()
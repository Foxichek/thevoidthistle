# WIRALIS - Web Portal

## Обзор проекта

WIRALIS - это веб-портал для интеграции с Telegram ботом. Пользователи могут входить на сайт используя коды, генерируемые ботом, и просматривать свои профили.

## Последние изменения (05.11.2025)

- ✅ Удален Neon database driver, добавлена поддержка стандартного PostgreSQL
- ✅ Настроены переменные окружения для production VPS
- ✅ Создана полная документация по deployment на Nginx
- ✅ Протестирован API bot integration (генерация и верификация кодов)
- ✅ Добавлены конфигурационные файлы для PM2 и Nginx

## Архитектура проекта

### База данных
- **Тип**: PostgreSQL (на внешнем VPS сервере)
- **Хост**: 147.45.224.10:5432
- **База**: crystalmadness
- **ORM**: Drizzle ORM
- **Драйвер**: node-postgres (pg)

### Backend
- **Фреймворк**: Express.js
- **TypeScript**: tsx для development, esbuild для production
- **Порт**: 5000 (проксируется через Nginx)

### Frontend
- **Фреймворк**: React + Vite
- **Routing**: wouter
- **UI**: shadcn/ui + Tailwind CSS
- **Состояние**: TanStack Query (React Query)

## API Endpoints

### Bot Integration

#### POST /api/bot/generate-code
Генерирует код для входа на сайт (вызывается Telegram ботом).

**Аутентификация**: Требуется заголовок `X-API-Key` с секретом бота

**Request:**
```json
{
  "telegramId": 123456789,
  "nickname": "Username",
  "username": "telegram_username",
  "quote": "User quote",
  "botId": "XXXX"
}
```

**Response:**
```json
{
  "code": "ABCD12",
  "expiresAt": "2025-11-05T13:00:00.000Z",
  "message": "Код успешно сгенерирован"
}
```

#### POST /api/verify-code
Проверяет код и возвращает данные пользователя (вызывается сайтом).

**Request:**
```json
{
  "code": "ABCD12"
}
```

**Response:**
```json
{
  "success": true,
  "user": {
    "id": "uuid",
    "telegramId": 123456789,
    "nickname": "Username",
    "username": "telegram_username",
    "quote": "User quote",
    "botId": "XXXX"
  }
}
```

#### GET /api/profile/:userId
Получает профиль пользователя по ID.

## Схема базы данных

### registration_codes
- `code` (varchar, PK) - 6-значный код
- `telegram_id` (bigint) - ID пользователя в Telegram
- `created_at` (timestamp) - Время создания
- `expires_at` (timestamp) - Время истечения (10 минут)
- `is_used` (boolean) - Использован ли код
- `used_at` (timestamp) - Время использования

### wiralis_users
- `id` (varchar, PK) - UUID
- `telegram_id` (bigint, unique) - ID пользователя в Telegram
- `nickname` (text) - Имя пользователя
- `username` (text) - Username в Telegram
- `quote` (text) - Цитата пользователя
- `bot_id` (varchar) - 4-значный ID из бота
- `registered_at` (timestamp) - Время регистрации

## Переменные окружения

### Требуемые секреты (через Replit Secrets)
- `DATABASE_URL` - URL подключения к PostgreSQL
- `TELEGRAM_BOT_API_SECRET` - Секрет для API бота

### Автоматические
- `NODE_ENV` - Режим окружения (development/production)
- `PORT` - Порт сервера (по умолчанию 5000)

## Развертывание на VPS

См. файл `DEPLOYMENT.md` для полной инструкции по развертыванию на VPS с Nginx.

### Краткая инструкция

1. Скопируйте файлы в `/var/www/wiralis.ru/`
2. Создайте `.env` файл с переменными окружения
3. Установите зависимости: `npm install`
4. Соберите проект: `npm run build`
5. Примените миграции: `npm run db:push`
6. Запустите через PM2: `pm2 start ecosystem.config.js`
7. Настройте Nginx (конфиг в `nginx.conf`)

## Интеграция с Telegram ботом

Бот находится отдельно от веб-приложения и связан только через общую базу данных PostgreSQL.

### Процесс аутентификации:
1. Пользователь вводит `/web` в боте
2. Бот отправляет POST запрос на `/api/bot/generate-code`
3. Сервер генерирует 6-значный код и сохраняет в БД
4. Бот показывает код пользователю
5. Пользователь вводит код на сайте
6. Сайт отправляет POST запрос на `/api/verify-code`
7. Сервер проверяет код и возвращает данные пользователя
8. Сайт создает сессию для пользователя

### Файл бота: web_module.py
- Отправляет данные пользователя на `/api/bot/generate-code`
- Использует `X-API-Key` для аутентификации
- Timeout: 10 секунд

## Структура проекта

```
/var/www/wiralis.ru/
├── client/              # Frontend React приложение
│   └── src/
│       ├── pages/       # Страницы приложения
│       ├── components/  # React компоненты
│       └── lib/         # Утилиты и хелперы
├── server/              # Backend Express приложение
│   ├── index.ts         # Точка входа сервера
│   ├── routes.ts        # API маршруты
│   ├── db.ts            # Подключение к БД
│   ├── storage.ts       # Интерфейс хранилища
│   └── vite.ts          # Vite middleware
├── shared/              # Общие типы и схемы
│   └── schema.ts        # Drizzle схема БД
├── dist/                # Скомпилированный код (production)
├── logs/                # Логи PM2
├── .env                 # Переменные окружения (не в git)
├── .env.example         # Пример переменных окружения
├── ecosystem.config.js  # Конфигурация PM2
├── nginx.conf           # Конфигурация Nginx
├── package.json         # Зависимости и скрипты
├── drizzle.config.ts    # Конфигурация Drizzle ORM
└── DEPLOYMENT.md        # Инструкция по развертыванию

Бот (отдельно):
/path/to/bot/
├── main.py              # Основной файл бота
├── web_module.py        # Модуль интеграции с сайтом
├── database.py          # Подключение к БД (SQLAlchemy)
└── models.py            # Модели БД (SQLAlchemy)
```

## Команды

### Development
```bash
npm run dev          # Запуск в режиме разработки
npm run check        # Проверка TypeScript
npm run db:push      # Применить схему к БД
```

### Production
```bash
npm run build        # Сборка проекта
npm run start        # Запуск production сервера
```

### PM2
```bash
pm2 start ecosystem.config.js   # Запустить приложение
pm2 restart wiralis-web        # Перезапустить
pm2 logs wiralis-web           # Просмотр логов
pm2 stop wiralis-web           # Остановить
```

## Безопасность

- ✅ Секреты хранятся в переменных окружения
- ✅ API бота защищен секретным ключом
- ✅ Пароль БД URL-encoded в DATABASE_URL
- ✅ Коды истекают через 10 минут
- ✅ Коды одноразовые (помечаются как использованные)

## Предпочтения пользователя

- Использовать PostgreSQL вместо Neon
- Развертывание на VPS с Nginx
- PM2 для управления процессами
- Бот и сайт связаны только через БД

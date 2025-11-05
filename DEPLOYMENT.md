# Инструкция по развертыванию WIRALIS на VPS с Nginx

## Предварительные требования

1. VPS с установленным Ubuntu/Debian
2. Node.js v20+ установлен
3. PostgreSQL установлен и настроен
4. Nginx установлен
5. PM2 для управления процессами Node.js

## Шаг 1: Подготовка окружения

### 1.1 Установите зависимости на сервере

```bash
# Обновите систему
sudo apt update && sudo apt upgrade -y

# Установите Node.js 20
curl -fsSL https://deb.nodesource.com/setup_20.x | sudo -E bash -
sudo apt install -y nodejs

# Установите PM2 глобально
sudo npm install -g pm2

# Установите Nginx (если еще не установлен)
sudo apt install -y nginx
```

### 1.2 Настройте PostgreSQL

База данных уже настроена согласно вашим данным:
- Host: 147.45.224.10
- Port: 5432
- Database: crystalmadness
- User: asteron
- Password: (указан в переменных окружения)

## Шаг 2: Развертывание приложения

### 2.1 Загрузите код на сервер

```bash
# Перейдите в директорию
cd /var/www/wiralis.ru/

# Скопируйте все файлы проекта в эту директорию
```

### 2.2 Создайте файл .env

Создайте файл `/var/www/wiralis.ru/.env` со следующим содержимым:

```bash
# Используйте DATABASE_URL из .env.example, убедитесь что пароль URL-encoded
DATABASE_URL=postgresql://asteron:_1337_Crystal-Madness_404_Asteron%23_banana%5Blabats%5Dbrc@147.45.224.10:5432/crystalmadness

# API секрет для Telegram бота
TELEGRAM_BOT_API_SECRET=US42982557

# Режим production
NODE_ENV=production

# Порт для приложения (nginx будет проксировать на этот порт)
PORT=5000
```

### 2.3 Установите зависимости и соберите проект

```bash
cd /var/www/wiralis.ru/

# Установите зависимости
npm install

# Соберите frontend
npm run build
```

### 2.4 Примените миграции базы данных

```bash
# Примените схему к базе данных
npm run db:push
```

## Шаг 3: Настройка PM2

### 3.1 Создайте конфигурационный файл PM2

Создайте файл `/var/www/wiralis.ru/ecosystem.config.js`:

```javascript
module.exports = {
  apps: [{
    name: 'wiralis-web',
    script: 'npm',
    args: 'run start',
    cwd: '/var/www/wiralis.ru/',
    instances: 1,
    autorestart: true,
    watch: false,
    max_memory_restart: '1G',
    env: {
      NODE_ENV: 'production',
      PORT: 5000
    },
    error_file: '/var/www/wiralis.ru/logs/pm2-error.log',
    out_file: '/var/www/wiralis.ru/logs/pm2-out.log',
    log_file: '/var/www/wiralis.ru/logs/pm2-combined.log',
    time: true
  }]
};
```

### 3.2 Создайте директорию для логов

```bash
mkdir -p /var/www/wiralis.ru/logs
```

### 3.3 Запустите приложение через PM2

```bash
cd /var/www/wiralis.ru/

# Запустите приложение
pm2 start ecosystem.config.js

# Сохраните конфигурацию PM2
pm2 save

# Настройте автозапуск PM2 при старте системы
pm2 startup
# Выполните команду, которую покажет PM2
```

## Шаг 4: Настройка Nginx

### 4.1 Создайте конфигурационный файл Nginx

Создайте файл `/etc/nginx/sites-available/wiralis.ru`:

```nginx
server {
    listen 80;
    listen [::]:80;
    server_name wiralis.ru www.wiralis.ru;

    # Лимиты
    client_max_body_size 10M;

    # Логи
    access_log /var/log/nginx/wiralis.ru-access.log;
    error_log /var/log/nginx/wiralis.ru-error.log;

    # Проксирование к Node.js приложению
    location / {
        proxy_pass http://localhost:5000;
        proxy_http_version 1.1;
        proxy_set_header Upgrade $http_upgrade;
        proxy_set_header Connection 'upgrade';
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
        proxy_cache_bypass $http_upgrade;
        
        # Таймауты
        proxy_connect_timeout 60s;
        proxy_send_timeout 60s;
        proxy_read_timeout 60s;
    }

    # Статические файлы (если нужно кэширование)
    location ~* \.(js|css|png|jpg|jpeg|gif|ico|svg|woff|woff2|ttf|eot)$ {
        proxy_pass http://localhost:5000;
        expires 1y;
        add_header Cache-Control "public, immutable";
    }
}
```

### 4.2 Активируйте конфигурацию

```bash
# Создайте символическую ссылку
sudo ln -s /etc/nginx/sites-available/wiralis.ru /etc/nginx/sites-enabled/

# Проверьте конфигурацию
sudo nginx -t

# Перезапустите Nginx
sudo systemctl restart nginx
```

### 4.3 Настройте SSL (опционально, но рекомендуется)

```bash
# Установите Certbot
sudo apt install -y certbot python3-certbot-nginx

# Получите SSL сертификат
sudo certbot --nginx -d wiralis.ru -d www.wiralis.ru

# Certbot автоматически обновит конфигурацию Nginx
```

## Шаг 5: Проверка работоспособности

### 5.1 Проверьте статус приложения

```bash
# Проверьте статус PM2
pm2 status

# Проверьте логи
pm2 logs wiralis-web --lines 50

# Проверьте статус Nginx
sudo systemctl status nginx
```

### 5.2 Протестируйте API

```bash
# Тест генерации кода (от имени бота)
curl -X POST https://wiralis.ru/api/bot/generate-code \
  -H "Content-Type: application/json" \
  -H "X-API-Key: US42982557" \
  -d '{"telegramId": 123456789, "nickname": "TestUser", "username": "testuser", "quote": "Test", "botId": "TEST"}'

# Тест верификации кода (используйте код из предыдущего ответа)
curl -X POST https://wiralis.ru/api/verify-code \
  -H "Content-Type: application/json" \
  -d '{"code": "XXXXXX"}'
```

### 5.3 Откройте сайт в браузере

Перейдите на `https://wiralis.ru` и проверьте, что сайт загружается.

## Шаг 6: Интеграция с Telegram ботом

В вашем Telegram боте (файл `web_module.py`) убедитесь, что:

1. `WEBSITE_URL` установлен на `"https://wiralis.ru"`
2. `API_SECRET` соответствует `TELEGRAM_BOT_API_SECRET` из `.env`

Эти переменные уже правильно настроены в вашем боте.

## Управление приложением

### Перезапуск приложения

```bash
pm2 restart wiralis-web
```

### Просмотр логов

```bash
# Все логи
pm2 logs wiralis-web

# Только ошибки
pm2 logs wiralis-web --err

# Последние 100 строк
pm2 logs wiralis-web --lines 100
```

### Обновление кода

```bash
cd /var/www/wiralis.ru/

# Получите новый код (git pull или скопируйте файлы)

# Установите зависимости (если package.json изменился)
npm install

# Соберите проект
npm run build

# Примените миграции (если схема изменилась)
npm run db:push

# Перезапустите приложение
pm2 restart wiralis-web
```

### Остановка приложения

```bash
pm2 stop wiralis-web
```

### Удаление приложения из PM2

```bash
pm2 delete wiralis-web
```

## Устранение неполадок

### Приложение не запускается

1. Проверьте логи PM2: `pm2 logs wiralis-web`
2. Проверьте переменные окружения в `.env`
3. Проверьте подключение к базе данных
4. Убедитесь, что порт 5000 свободен: `lsof -i :5000`

### Nginx показывает 502 Bad Gateway

1. Проверьте, что приложение запущено: `pm2 status`
2. Проверьте, что приложение слушает порт 5000: `curl http://localhost:5000`
3. Проверьте логи Nginx: `sudo tail -f /var/log/nginx/wiralis.ru-error.log`

### База данных недоступна

1. Проверьте подключение к PostgreSQL: 
   ```bash
   psql -h 147.45.224.10 -p 5432 -U asteron -d crystalmadness
   ```
2. Проверьте правильность DATABASE_URL в `.env`
3. Убедитесь, что пароль правильно закодирован в URL

## Безопасность

1. **Файрвол**: Убедитесь, что открыты только порты 80 (HTTP), 443 (HTTPS) и 22 (SSH)
2. **Права доступа**: 
   ```bash
   chmod 600 /var/www/wiralis.ru/.env
   chown www-data:www-data /var/www/wiralis.ru -R
   ```
3. **Регулярные обновления**: Обновляйте зависимости и систему регулярно
4. **Мониторинг**: Настройте мониторинг через PM2 Plus или другие инструменты

## Дополнительная информация

- Node.js работает на порту 5000 (только локально)
- Nginx проксирует запросы с 80/443 портов на 5000
- PM2 автоматически перезапускает приложение при сбое
- Логи приложения: `/var/www/wiralis.ru/logs/`
- Логи Nginx: `/var/log/nginx/`

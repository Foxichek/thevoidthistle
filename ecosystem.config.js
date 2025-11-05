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

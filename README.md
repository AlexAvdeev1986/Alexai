# Alexai
 Alexai site
 
 Я помогу вам настроить запуск сайта через Docker локально на Fedora 42, а затем на сервере Ubuntu 22 с HTTPS и без отображения порта.

## Шаг 1: Подготовка структуры проекта

Создайте следующую структуру директорий:

```
project/
├── docker-compose.yml
├── nginx/
│   └── your-site.conf
└── site/
    ├── index.html (переименуйте NikitaAI.html)
    └── photo_2025-10-14_18-20-51.jpg
```

## Шаг 2: Локальный запуск на Fedora 42

### Установка Docker (если не установлен)

```bash
# Установка Docker
sudo dnf install docker docker-compose -y

# Запуск и автозагрузка Docker
sudo systemctl start docker
sudo systemctl enable docker

# Добавление пользователя в группу docker
sudo usermod -aG docker $USER
newgrp docker
```

### Изменения в файлах

**1. Переименуйте файл:**
```bash
mv NikitaAI.html index.html
```

**2. Обновите `nginx/your-site.conf`:**

```nginx
server {
    listen 80;
    server_name localhost;
    root /usr/share/nginx/html;
    index index.html;

    location / {
        try_files $uri $uri/ =404;
    }
}
```

**3. Запустите контейнер:**

```bash
# Перейдите в директорию проекта
cd /path/to/project

# Запустите контейнер
docker-compose up -d

# Проверьте статус
docker-compose ps

# Просмотрите логи
docker-compose logs -f
```

Теперь сайт доступен по адресу: `http://localhost`

## Шаг 3: Развертывание на Ubuntu 22 с HTTPS

### 3.1 Установка необходимых компонентов на сервере

```bash
# Обновление системы
sudo apt update && sudo apt upgrade -y

# Установка Docker
sudo apt install docker.io docker-compose -y

# Установка Nginx (для проксирования)
sudo apt install nginx certbot python3-certbot-nginx -y

# Запуск Docker
sudo systemctl start docker
sudo systemctl enable docker
```

### 3.2 Загрузите проект на сервер

```bash
# Создайте директорию
mkdir -p /opt/nikitaai
cd /opt/nikitaai

# Загрузите файлы (используйте scp, git или другой метод)
```

### 3.3 Обновите конфигурацию Nginx для контейнера

**Файл `nginx/your-site.conf`:**

```nginx
server {
    listen 80;
    server_name nikitaai5151.serveminecraft.net;
    root /usr/share/nginx/html;
    index index.html;

    location / {
        try_files $uri $uri/ =404;
    }
}
```

### 3.4 Обновите `docker-compose.yml`

```yaml
services:
  nginx:
    image: nginx:alpine
    container_name: NikitaAI
    ports:
      - "127.0.0.1:8080:80"  # Слушаем только на localhost
    volumes:
      - ./nginx:/etc/nginx/conf.d/:ro
      - ./site:/usr/share/nginx/html:ro
    restart: unless-stopped
```

### 3.5 Настройка Nginx как reverse proxy

Создайте конфигурацию Nginx на хосте:

```bash
sudo nano /etc/nginx/sites-available/nikitaai
```

**Содержимое файла `/etc/nginx/sites-available/nikitaai`:**

```nginx
server {
    listen 80;
    server_name nikitaai5151.serveminecraft.net;

    location / {
        proxy_pass http://127.0.0.1:8080;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
    }
}
```

**Активируйте конфигурацию:**

```bash
# Создайте символическую ссылку
sudo ln -s /etc/nginx/sites-available/nikitaai /etc/nginx/sites-enabled/

# Удалите дефолтную конфигурацию
sudo rm /etc/nginx/sites-enabled/default

# Проверьте конфигурацию
sudo nginx -t

# Перезапустите Nginx
sudo systemctl restart nginx
```

### 3.6 Настройка SSL с помощью Let's Encrypt

```bash
# Получите SSL-сертификат
sudo certbot --nginx -d nikitaai5151.serveminecraft.net

# Следуйте инструкциям certbot
# Выберите опцию редиректа HTTP -> HTTPS
```

Certbot автоматически обновит конфигурацию Nginx, добавив SSL и редирект.

### 3.7 Запустите Docker контейнер

```bash
cd /opt/nikitaai
docker-compose up -d

# Проверьте статус
docker-compose ps

# Просмотрите логи
docker-compose logs -f
```

### 3.8 Настройка автообновления сертификата

```bash
# Проверьте автообновление
sudo certbot renew --dry-run

# Certbot автоматически создаст cron/systemd timer для обновления
```

## Шаг 4: Проверка работы

1. Откройте браузер и перейдите по адресу: `https://nikitaai5151.serveminecraft.net`
2. Убедитесь, что:
   - Сайт загружается
   - Используется HTTPS
   - Порт не отображается в URL
   - SSL-сертификат валидный

## Дополнительные команды для управления

```bash
# Остановка контейнера
docker-compose down

# Перезапуск
docker-compose restart

# Просмотр логов
docker-compose logs -f

# Обновление контейнера
docker-compose pull
docker-compose up -d

# Проверка статуса Nginx
sudo systemctl status nginx

# Перезагрузка Nginx
sudo systemctl reload nginx
```

## Настройка firewall (если включен)

```bash
# Ubuntu (ufw)
sudo ufw allow 80/tcp
sudo ufw allow 443/tcp
sudo ufw enable

# Fedora (firewalld)
sudo firewall-cmd --permanent --add-service=http
sudo firewall-cmd --permanent --add-service=https
sudo firewall-cmd --reload
```

## Итоговая схема

```
Пользователь → HTTPS (443) → Nginx (хост) → HTTP (127.0.0.1:8080) → Docker контейнер (Nginx)
```

Теперь ваш сайт будет доступен по адресу `https://nikitaai5151.serveminecraft.net` без отображения порта!

# Просмотр логов контейнера
sudo docker logs Alexai

# Просмотр логов в реальном времени
sudo docker logs -f Alexai

# Остановить контейнер
sudo docker stop Alexai

# Запустить остановленный контейнер
sudo docker start Alexai

# Перезапустить контейнер
sudo docker restart Alexai

# Удалить контейнер
sudo docker rm Alexai

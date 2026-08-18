# Plesk Production Deploy

## 1. Clone and configure

```bash
git clone https://github.com/Atothegod/BRI.git
cd BRI
cp .env.example .env
```

Edit `.env` on the server. For a real domain, use values like:

```env
DJANGO_DEBUG=0
DJANGO_ALLOWED_HOSTS=bri.example.com
DJANGO_CSRF_TRUSTED_ORIGINS=https://bri.example.com
DJANGO_SECURE_SSL_REDIRECT=0
DJANGO_SESSION_COOKIE_SECURE=1
DJANGO_CSRF_COOKIE_SECURE=1
WEB_PORT=8080
LINE_LIFF_ALLOW_UNVERIFIED_PROFILE=0
```

Keep `.env` only on the server. Do not commit it.

## 2. Start production containers

```bash
docker compose -f docker-compose.prod.yml up -d --build
docker compose -f docker-compose.prod.yml exec backend python manage.py migrate
docker compose -f docker-compose.prod.yml exec backend python manage.py createsuperuser
```

The production stack exposes Nginx on `WEB_PORT` and keeps Gunicorn internal.

## 3. Plesk reverse proxy

Point the Plesk domain or subdomain to:

```text
http://127.0.0.1:8080
```

Use the same port as `WEB_PORT`. Enable SSL for the Plesk domain, then update the LINE LIFF Endpoint URL to the HTTPS domain.

# Plesk Production Deploy

For the Cloud VPS flow that does not use Plesk as the public web server, use `DEPLOY_VPS_NGINX.md`.

## 1. Clone and configure

```bash
git clone https://github.com/Atothegod/BRI.git
cd BRI
cp .env.example .env
```

Edit `.env` on the server. For a real domain, use values like:

```env
DJANGO_DEBUG=0
DJANGO_ALLOWED_HOSTS=bri.brightromancechurch.org
DJANGO_CSRF_TRUSTED_ORIGINS=https://bri.brightromancechurch.org
DJANGO_SECURE_SSL_REDIRECT=0
DJANGO_SESSION_COOKIE_SECURE=1
DJANGO_CSRF_COOKIE_SECURE=1
WEB_BIND=127.0.0.1
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

The production stack exposes Nginx on `WEB_BIND:WEB_PORT` and keeps Gunicorn internal.
Use `WEB_BIND=127.0.0.1` when another reverse proxy on the server is responsible for public HTTP/HTTPS traffic.

## 3. Reverse proxy

Point the Plesk domain, Nginx, Caddy, or Apache reverse proxy to:

```text
http://127.0.0.1:8080
```

Use the same port as `WEB_PORT`. Enable SSL for the public domain at the reverse proxy, then update the LINE LIFF Endpoint URL to the HTTPS domain.

If Cloudflare is enabled, create the DNS record inside the `brightromancechurch.org` zone like this:

```text
Type: A
Name: bri
IPv4 address: 147.50.231.124
Proxy status: Proxied
```

The public hostname should be:

```text
bri.brightromancechurch.org
```

Do not create a nested hostname such as `bri.brightromancechruch.org.brightromancechurch.org`.

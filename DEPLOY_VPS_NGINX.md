# VPS Nginx Production Deploy

This setup runs the Django app inside Docker and uses host Nginx on the VPS for public HTTP/HTTPS.

```text
Cloudflare -> VPS Nginx :80/:443 -> Docker Nginx 127.0.0.1:8080 -> Gunicorn backend:8000
```

## 1. DNS

In Cloudflare, create this record inside the `brightromancechurch.org` zone:

```text
Type: A
Name: bri
IPv4 address: 147.50.231.124
Proxy status: Proxied
```

The hostname should be:

```text
bri.brightromancechurch.org
```

## 2. Server `.env`

Copy the example on the VPS and edit secrets:

```bash
cp .env.example .env
nano .env
```

Minimum production values:

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

## 3. Start Docker

```bash
docker compose -f docker-compose.prod.yml up -d --build
docker compose -f docker-compose.prod.yml exec backend python manage.py migrate
docker compose -f docker-compose.prod.yml exec backend python manage.py createsuperuser
```

Check the internal app:

```bash
curl -I http://127.0.0.1:8080/
```

It should return `HTTP/1.1 200 OK` or a normal redirect.

## 4. Host Nginx

Install Nginx and Certbot:

```bash
sudo apt update
sudo apt install -y nginx certbot python3-certbot-nginx
```

Install the site config:

```bash
sh deploy/install-host-nginx.sh
```

Open firewall ports if UFW is enabled:

```bash
sudo ufw allow 80/tcp
sudo ufw allow 443/tcp
sudo ufw status
```

Check public listeners:

```bash
sudo ss -tlnp | grep -E ':80|:443|:8080'
```

You should see Nginx listening on `:80`, and Docker listening on `127.0.0.1:8080`.

## 5. SSL

Issue a certificate:

```bash
sudo certbot --nginx -d bri.brightromancechurch.org
```

After Certbot succeeds, set Cloudflare SSL/TLS mode to `Full (strict)` if the origin certificate is valid.
Use `Full` while troubleshooting certificate chain issues.

Final checks:

```bash
curl -I http://bri.brightromancechurch.org/
curl -I https://bri.brightromancechurch.org/
docker compose -f docker-compose.prod.yml ps
```

## Troubleshooting 521

Cloudflare 521 usually means Cloudflare cannot connect to the origin.

Check these on the VPS:

```bash
curl -I http://127.0.0.1:8080/
sudo ss -tlnp | grep -E ':80|:443|:8080'
sudo nginx -t
sudo systemctl status nginx
```

If Docker returns `200` on `127.0.0.1:8080` but Cloudflare still shows 521, host Nginx is not reachable on public `80/443` or the VPS firewall/security group is blocking traffic.

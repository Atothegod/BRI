import json
from urllib import error, parse, request

from django.conf import settings
from django.core.management.base import BaseCommand, CommandError


class Command(BaseCommand):
    help = "Check runtime LINE Messaging API credentials without sending messages."
    requires_system_checks = []

    def handle(self, *args, **options):
        token = settings.LINE_MESSAGING_CHANNEL_ACCESS_TOKEN
        self.stdout.write(f"Token configured: {bool(token)}")
        if not token:
            raise CommandError("Missing token. Recreate the backend after updating .env.")
        if any(char.isspace() for char in token) or "..." in token:
            raise CommandError("Invalid token format. Use the full access token on its own .env line.")

        base_url = parse.urlsplit(settings.PUBLIC_BASE_URL)
        if base_url.scheme != "https" or not base_url.hostname or base_url.username or base_url.password:
            raise CommandError("PUBLIC_BASE_URL must be a plain HTTPS URL without credentials.")
        self.stdout.write(f"Public host: {base_url.hostname}")
        api_request = request.Request(
            "https://api.line.me/v2/bot/info",
            headers={"Authorization": f"Bearer {token}"},
            method="GET",
        )
        try:
            with request.urlopen(api_request, timeout=8) as response:
                bot = json.loads(response.read().decode("utf-8"))
        except error.HTTPError as exc:
            hints = {
                401: "Token rejected. Check the Messaging API channel access token, not Channel secret.",
                403: "Access denied. Check the Messaging API channel permissions.",
                429: "LINE rate limit reached. Retry later.",
            }
            raise CommandError(f"LINE HTTP {exc.code}: {hints.get(exc.code, 'LINE request failed. Retry or check LINE service status.')}") from None
        except (error.URLError, TimeoutError, OSError):
            raise CommandError("Cannot reach LINE. Check production DNS, outbound HTTPS and connectivity.") from None
        except (ValueError, UnicodeError):
            raise CommandError("LINE returned an invalid response.") from None

        self.stdout.write(self.style.SUCCESS("LINE authentication: OK"))
        self.stdout.write(f"Official Account: {bot.get('displayName', '(unknown)')} ({bot.get('basicId', '(unknown)')})")
        self.stdout.write("No message sent. This verifies credentials, not recipient delivery or message quota.")
        self.stdout.write("For existing passed applicants, use admin action: Send LINE interview-passed notification.")

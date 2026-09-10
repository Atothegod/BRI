from io import BytesIO, StringIO
from unittest.mock import patch
from urllib.error import HTTPError, URLError

from django.core.management import call_command
from django.core.management.base import CommandError
from django.test import SimpleTestCase, override_settings


@override_settings(
    LINE_MESSAGING_CHANNEL_ACCESS_TOKEN="test-private-token",
    PUBLIC_BASE_URL="https://bri.brightromancechurch.org",
)
class LineMessagingDiagnosticsTests(SimpleTestCase):
    @patch("school.management.commands.check_line_messaging.request.urlopen")
    def test_checks_bot_without_sending_or_printing_token(self, urlopen):
        urlopen.return_value.__enter__.return_value.read.return_value = b'{"displayName":"BRI","basicId":"@bri"}'
        output = StringIO()
        call_command("check_line_messaging", stdout=output)
        api_request = urlopen.call_args.args[0]
        self.assertEqual(api_request.full_url, "https://api.line.me/v2/bot/info")
        self.assertEqual(api_request.get_method(), "GET")
        self.assertIn("LINE authentication: OK", output.getvalue())
        self.assertNotIn("test-private-token", output.getvalue())

    @patch("school.management.commands.check_line_messaging.request.urlopen")
    def test_missing_and_malformed_token_do_not_call_line(self, urlopen):
        for token in ("", "short...", "token PUBLIC_BASE_URL=https://example.com"):
            with self.subTest(token=token), override_settings(LINE_MESSAGING_CHANNEL_ACCESS_TOKEN=token):
                with self.assertRaises(CommandError):
                    call_command("check_line_messaging", stdout=StringIO())
        urlopen.assert_not_called()

    @patch("school.management.commands.check_line_messaging.request.urlopen")
    def test_authentication_and_network_errors_are_safe(self, urlopen):
        failures = [
            (HTTPError("https://api.line.me", 401, "unauthorized", {}, BytesIO(b"test-private-token")), "LINE HTTP 401"),
            (URLError("test-private-token"), "Cannot reach LINE"),
        ]
        for failure, expected in failures:
            with self.subTest(expected=expected):
                urlopen.side_effect = failure
                with self.assertRaises(CommandError) as caught:
                    call_command("check_line_messaging", stdout=StringIO())
                self.assertIn(expected, str(caught.exception))
                self.assertNotIn("test-private-token", str(caught.exception))

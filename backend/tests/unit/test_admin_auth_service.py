import unittest
from dataclasses import replace
from unittest.mock import patch

from app.core.config import settings
from app.services.admin_auth_service import AdminAuthService


class AdminAuthServiceTests(unittest.TestCase):
    def setUp(self) -> None:
        test_settings = replace(
            settings,
            admin_api_key="unit-test-admin-key",
            admin_session_ttl_minutes=5,
        )
        self.settings_patch = patch(
            "app.services.admin_auth_service.settings",
            test_settings,
        )
        self.settings_patch.start()
        self.addCleanup(self.settings_patch.stop)
        self.service = AdminAuthService()

    def test_created_session_validates_as_bearer(self) -> None:
        token, _, ttl = self.service.create_session()

        self.assertEqual(ttl, 300)
        self.assertTrue(self.service.validate_bearer(f"Bearer {token}"))

    def test_tampered_token_is_rejected(self) -> None:
        token, _, _ = self.service.create_session()
        tampered = token[:-1] + ("a" if token[-1] != "a" else "b")

        self.assertFalse(self.service.validate_token(tampered))
        self.assertFalse(self.service.validate_bearer("Basic not-a-token"))

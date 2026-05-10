from __future__ import annotations

import base64
import unittest
from unittest.mock import Mock, patch

from app.services import espocrm_service


def mock_json_response(payload: dict, *, status_code: int = 200) -> Mock:
    response = Mock()
    response.status_code = status_code
    response.json.return_value = payload
    response.text = ""
    return response


class EspoCRMServiceTest(unittest.TestCase):
    def test_create_lead_uses_espo_authorization_token_flow(self) -> None:
        original_base_url = espocrm_service.settings.espocrm_base_url
        original_api_key = espocrm_service.settings.espocrm_api_key
        original_username = espocrm_service.settings.espocrm_username
        original_password = espocrm_service.settings.espocrm_password
        espocrm_service.settings.espocrm_base_url = "https://crm.example.test"
        espocrm_service.settings.espocrm_api_key = ""
        espocrm_service.settings.espocrm_username = "admin"
        espocrm_service.settings.espocrm_password = "password"
        try:
            with patch("app.services.espocrm_service.requests.get", return_value=mock_json_response({"token": "token-123"})) as mock_get:
                with patch("app.services.espocrm_service.requests.post", return_value=mock_json_response({"id": "lead-1"})) as mock_post:
                    response = espocrm_service.create_lead({"name": "Test Lead"})
        finally:
            espocrm_service.settings.espocrm_base_url = original_base_url
            espocrm_service.settings.espocrm_api_key = original_api_key
            espocrm_service.settings.espocrm_username = original_username
            espocrm_service.settings.espocrm_password = original_password

        self.assertEqual({"id": "lead-1"}, response)
        auth_request_headers = mock_get.call_args.kwargs["headers"]
        lead_request_headers = mock_post.call_args.kwargs["headers"]
        self.assertEqual(
            base64.b64encode(b"admin:password").decode("ascii"),
            auth_request_headers["Espo-Authorization"],
        )
        self.assertEqual(
            base64.b64encode(b"admin:token-123").decode("ascii"),
            lead_request_headers["Espo-Authorization"],
        )


if __name__ == "__main__":
    unittest.main()

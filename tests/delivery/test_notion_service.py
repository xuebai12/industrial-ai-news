import pytest
from unittest.mock import MagicMock
from notion_client.errors import APIResponseError
from src.delivery.notion_service import NotionDeliveryService

class TestNotionDeliveryService:
    def test_classify_error_auth(self):
        # 401
        error_401 = APIResponseError(response=MagicMock(), message="Unauthorized", code=401)
        error_401.status = 401
        assert NotionDeliveryService.classify_error(error_401) == "AUTH"

        # 403
        error_403 = APIResponseError(response=MagicMock(), message="Forbidden", code=403)
        error_403.status = 403
        assert NotionDeliveryService.classify_error(error_403) == "AUTH"

        # Message check
        error_msg = APIResponseError(response=MagicMock(), message="Some unauthorized access", code=500)
        error_msg.status = 500
        assert NotionDeliveryService.classify_error(error_msg) == "AUTH"

    def test_classify_error_rate_limit(self):
        # 429
        error_429 = APIResponseError(response=MagicMock(), message="Rate limit exceeded", code=429)
        error_429.status = 429
        assert NotionDeliveryService.classify_error(error_429) == "RATE_LIMIT"

        # "rate" in code
        error_code = APIResponseError(response=MagicMock(), message="Error", code="rate_limit_exceeded")
        error_code.status = 500
        assert NotionDeliveryService.classify_error(error_code) == "RATE_LIMIT"

        # "rate" in message
        error_msg = APIResponseError(response=MagicMock(), message="You have hit the rate limit", code=500)
        error_msg.status = 500
        assert NotionDeliveryService.classify_error(error_msg) == "RATE_LIMIT"

    def test_classify_error_schema(self):
        # 400 + validation
        error_val = APIResponseError(response=MagicMock(), message="Validation error", code=400)
        error_val.status = 400
        assert NotionDeliveryService.classify_error(error_val) == "SCHEMA"

        # 400 + property
        error_prop = APIResponseError(response=MagicMock(), message="Invalid property", code=400)
        error_prop.status = 400
        assert NotionDeliveryService.classify_error(error_prop) == "SCHEMA"

    def test_classify_error_api(self):
        # Generic API error
        error_api = APIResponseError(response=MagicMock(), message="Server error", code=500)
        error_api.status = 500
        assert NotionDeliveryService.classify_error(error_api) == "API"

    def test_classify_error_unknown(self):
        # Non-APIResponseError
        error_unknown = Exception("Something went wrong")
        assert NotionDeliveryService.classify_error(error_unknown) == "UNKNOWN"

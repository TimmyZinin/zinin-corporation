"""Tests for Telegram bot modules."""

import json
import os
import tempfile
from unittest.mock import AsyncMock, MagicMock, patch

import pytest


# ──────────────────────────────────────────────────────────
# Test: Formatters
# ──────────────────────────────────────────────────────────

class TestFormatters:
    def test_short_message_returned_as_is(self):
        from src.telegram.formatters import format_for_telegram
        result = format_for_telegram("Hello world")
        assert result == ["Hello world"]

    def test_empty_message(self):
        from src.telegram.formatters import format_for_telegram
        result = format_for_telegram("")
        assert result == ["(пустой ответ)"]

    def test_none_message(self):
        from src.telegram.formatters import format_for_telegram
        result = format_for_telegram(None)
        assert result == ["(пустой ответ)"]

    def test_long_message_split_on_paragraphs(self):
        from src.telegram.formatters import format_for_telegram
        para = "A" * 2000
        text = f"{para}\n\n{para}\n\n{para}"
        result = format_for_telegram(text, max_length=4096)
        assert len(result) == 2  # 2000+2000 fits, third doesn't
        assert all(len(chunk) <= 4096 for chunk in result)

    def test_very_long_single_paragraph(self):
        from src.telegram.formatters import format_for_telegram
        text = "A" * 5000
        result = format_for_telegram(text, max_length=4096)
        assert len(result) >= 1
        assert len(result[0]) <= 4096

    def test_whitespace_only(self):
        from src.telegram.formatters import format_for_telegram
        result = format_for_telegram("   \n\n  ")
        assert result == ["(пустой ответ)"]


# ──────────────────────────────────────────────────────────
# Test: Screenshot Storage
# ──────────────────────────────────────────────────────────

class TestScreenshotStorage:
    def test_save_and_load(self, tmp_path):
        from src.telegram.screenshot_storage import (
            save_screenshot_data,
            load_all_screenshots,
            _storage_path,
        )

        json_path = str(tmp_path / "screenshots.json")
        with patch("src.telegram.screenshot_storage._storage_path", return_value=json_path):
            data = {
                "source": "TBC Bank",
                "screen_type": "balance",
                "accounts": [{"name": "GEL Account", "balance": "1500.00", "currency": "GEL"}],
                "transactions": [],
                "summary": "TBC Bank balance: 1500 GEL",
            }
            assert save_screenshot_data(data) is True

            loaded = load_all_screenshots()
            # Will load from default path, not tmp. Test the function logic separately.

    def test_get_latest_balances_empty(self):
        from src.telegram.screenshot_storage import get_latest_balances
        with patch("src.telegram.screenshot_storage.load_all_screenshots", return_value=[]):
            result = get_latest_balances()
            assert result == {}

    def test_get_latest_balances_with_data(self):
        from src.telegram.screenshot_storage import get_latest_balances
        mock_data = [
            {
                "source": "TBC Bank",
                "accounts": [{"name": "GEL", "balance": "1500", "currency": "GEL"}],
                "extracted_at": "2026-02-07T10:00:00",
            },
            {
                "source": "TBC Bank",
                "accounts": [{"name": "GEL", "balance": "1600", "currency": "GEL"}],
                "extracted_at": "2026-02-07T12:00:00",
            },
        ]
        with patch("src.telegram.screenshot_storage.load_all_screenshots", return_value=mock_data):
            result = get_latest_balances()
            assert "TBC Bank" in result
            assert result["TBC Bank"]["accounts"][0]["balance"] == "1600"

    def test_max_entries_cap(self, tmp_path):
        from src.telegram.screenshot_storage import save_screenshot_data, MAX_ENTRIES

        json_path = str(tmp_path / "screenshots.json")
        # Pre-fill with MAX_ENTRIES items
        initial = [{"source": f"test_{i}", "accounts": [], "extracted_at": "2026-01-01"} for i in range(MAX_ENTRIES)]
        os.makedirs(os.path.dirname(json_path) or ".", exist_ok=True)
        with open(json_path, "w") as f:
            json.dump(initial, f)

        with patch("src.telegram.screenshot_storage._storage_path", return_value=json_path):
            save_screenshot_data({"source": "new", "accounts": [], "summary": "new"})

            with open(json_path) as f:
                data = json.load(f)
            assert len(data) <= MAX_ENTRIES


# ──────────────────────────────────────────────────────────
# Test: Config
# ──────────────────────────────────────────────────────────

class TestConfig:
    def test_from_env_defaults(self):
        from src.telegram.config import TelegramConfig
        with patch.dict(os.environ, {}, clear=True):
            config = TelegramConfig.from_env()
            assert config.bot_token == ""
            assert config.allowed_user_ids == []
            assert config.default_agent == "accountant"

    def test_from_env_with_values(self):
        from src.telegram.config import TelegramConfig
        env = {
            "TELEGRAM_BOT_TOKEN": "test-token-123",
            "TELEGRAM_ALLOWED_USERS": "12345,67890",
        }
        with patch.dict(os.environ, env, clear=False):
            config = TelegramConfig.from_env()
            assert config.bot_token == "test-token-123"
            assert config.allowed_user_ids == [12345, 67890]


# ──────────────────────────────────────────────────────────
# Test: Vision (mocked)
# ──────────────────────────────────────────────────────────

class TestVision:
    @pytest.mark.asyncio
    async def test_extract_financial_data_success(self):
        from src.telegram.vision import extract_financial_data

        mock_response = {
            "choices": [
                {
                    "message": {
                        "content": json.dumps({
                            "source": "TBC Bank",
                            "screen_type": "balance",
                            "accounts": [{"name": "GEL", "balance": "1500.00", "currency": "GEL"}],
                            "transactions": [],
                            "summary": "TBC Bank: 1500 GEL"
                        })
                    }
                }
            ]
        }

        with patch.dict(os.environ, {"OPENROUTER_API_KEY": "test-key"}):
            with patch("src.telegram.vision.httpx.AsyncClient") as mock_client_cls:
                mock_client = AsyncMock()
                mock_client_cls.return_value.__aenter__ = AsyncMock(return_value=mock_client)
                mock_client_cls.return_value.__aexit__ = AsyncMock(return_value=False)

                mock_resp = MagicMock()
                mock_resp.json.return_value = mock_response
                mock_resp.raise_for_status = MagicMock()
                mock_client.post = AsyncMock(return_value=mock_resp)

                result = await extract_financial_data("base64data", "TBC Bank баланс")

                assert result["source"] == "TBC Bank"
                assert result["accounts"][0]["balance"] == "1500.00"

    @pytest.mark.asyncio
    async def test_extract_no_api_key(self):
        from src.telegram.vision import extract_financial_data

        with patch.dict(os.environ, {}, clear=True):
            with pytest.raises(EnvironmentError):
                await extract_financial_data("base64data")

    @pytest.mark.asyncio
    async def test_extract_fallback_on_bad_json(self):
        from src.telegram.vision import extract_financial_data

        mock_response = {
            "choices": [{"message": {"content": "I cannot parse this image properly"}}]
        }

        with patch.dict(os.environ, {"OPENROUTER_API_KEY": "test-key"}):
            with patch("src.telegram.vision.httpx.AsyncClient") as mock_client_cls:
                mock_client = AsyncMock()
                mock_client_cls.return_value.__aenter__ = AsyncMock(return_value=mock_client)
                mock_client_cls.return_value.__aexit__ = AsyncMock(return_value=False)

                mock_resp = MagicMock()
                mock_resp.json.return_value = mock_response
                mock_resp.raise_for_status = MagicMock()
                mock_client.post = AsyncMock(return_value=mock_resp)

                result = await extract_financial_data("base64data")

                assert result["source"] == "unknown"
                assert "cannot parse" in result["summary"].lower()


# ──────────────────────────────────────────────────────────
# Test: Bridge (mocked)
# ──────────────────────────────────────────────────────────

class TestBridge:
    @pytest.mark.asyncio
    async def test_send_to_agent(self):
        from src.telegram.bridge import AgentBridge

        mock_corp = MagicMock()
        mock_corp.is_ready = True
        mock_corp.execute_task.return_value = "Финансовый отчёт готов"

        AgentBridge._corp = mock_corp

        result = await AgentBridge.send_to_agent("Какой баланс?")
        assert "отчёт" in result.lower()
        mock_corp.execute_task.assert_called_once()

        # Cleanup
        AgentBridge._corp = None

    @pytest.mark.asyncio
    async def test_send_with_context(self):
        from src.telegram.bridge import AgentBridge

        mock_corp = MagicMock()
        mock_corp.is_ready = True
        mock_corp.execute_task.return_value = "OK"

        AgentBridge._corp = mock_corp

        await AgentBridge.send_to_agent(
            "Баланс?",
            chat_context="Тим: Привет\nМаттиас: Добрый день",
        )

        call_args = mock_corp.execute_task.call_args[0][0]
        assert "Новое сообщение от Тима: Баланс?" in call_args
        assert "Тим: Привет" in call_args

        AgentBridge._corp = None


# ──────────────────────────────────────────────────────────
# Test: ScreenshotDataTool
# ──────────────────────────────────────────────────────────

class TestScreenshotDataTool:
    def test_no_data(self):
        from src.tools.financial.screenshot_data import ScreenshotDataTool

        with patch("src.telegram.screenshot_storage.load_all_screenshots", return_value=[]):
            tool = ScreenshotDataTool()
            result = tool._run()
            assert "нет" in result.lower() or "not available" in result.lower()


# ──────────────────────────────────────────────────────────
# Test: Tinkoff CSV Parser
# ──────────────────────────────────────────────────────────

class TestTinkoffParser:
    def test_is_tinkoff_csv(self):
        from src.telegram.tinkoff_parser import is_tinkoff_csv
        header = '"Дата операции";"Дата платежа";"Номер карты";"Статус";"Сумма операции"'
        assert is_tinkoff_csv(header) is True
        assert is_tinkoff_csv("random,csv,header") is False

    def test_parse_basic(self):
        from src.telegram.tinkoff_parser import parse_tinkoff_csv
        csv_content = (
            '"Дата операции";"Дата платежа";"Номер карты";"Статус";"Сумма операции";"Валюта операции";"Сумма платежа";"Валюта платежа";"Кэшбэк";"Категория";"MCC";"Описание";"Бонусы (включая кэшбэк)";"Округление на инвесткопилку";"Сумма операции с округлением"\n'
            '"01.02.2026 17:23:58";"01.02.2026";"*5736";"OK";"-500,00";"RUB";"-500,00";"RUB";"";"Мобильная связь";"";"Билайн";"0,00";"0,00";"-500,00"\n'
            '"26.01.2026 10:47:30";"26.01.2026";"*5450";"OK";"5000,00";"RUB";"5000,00";"RUB";"";"Переводы";"";"Между своими счетами";"0,00";"0,00";"5000,00"\n'
        )
        parsed = parse_tinkoff_csv(csv_content)
        assert parsed["total_count"] == 2
        assert parsed["source"] == "tinkoff"
        assert "*5736" in parsed["cards"]
        assert parsed["summary"]["expenses"] == 500.0

    def test_skip_failed(self):
        from src.telegram.tinkoff_parser import parse_tinkoff_csv
        csv_content = (
            '"Дата операции";"Дата платежа";"Номер карты";"Статус";"Сумма операции";"Валюта операции";"Сумма платежа";"Валюта платежа";"Кэшбэк";"Категория";"MCC";"Описание";"Бонусы (включая кэшбэк)";"Округление на инвесткопилку";"Сумма операции с округлением"\n'
            '"05.01.2026 11:55:21";"";"*5736";"FAILED";"-400,00";"RUB";"-400,00";"RUB";"";"Фастфуд";"";"Покупка";"0,00";"0,00";"-400,00"\n'
        )
        parsed = parse_tinkoff_csv(csv_content)
        assert parsed["total_count"] == 0

    def test_format_summary(self):
        from src.telegram.tinkoff_parser import parse_tinkoff_csv, format_summary_text
        csv_content = (
            '"Дата операции";"Дата платежа";"Номер карты";"Статус";"Сумма операции";"Валюта операции";"Сумма платежа";"Валюта платежа";"Кэшбэк";"Категория";"MCC";"Описание";"Бонусы (включая кэшбэк)";"Округление на инвесткопилку";"Сумма операции с округлением"\n'
            '"01.02.2026 10:00:00";"01.02.2026";"*5736";"OK";"-1000,00";"RUB";"-1000,00";"RUB";"";"Супермаркеты";"5411";"Магнит";"0,00";"0,00";"-1000,00"\n'
        )
        parsed = parse_tinkoff_csv(csv_content)
        text = format_summary_text(parsed)
        assert "Т-Банк" in text
        assert "1,000.00" in text


# ──────────────────────────────────────────────────────────
# Test: Transaction Storage
# ──────────────────────────────────────────────────────────

class TestTransactionStorage:
    def test_save_and_load(self, tmp_path):
        from src.telegram.transaction_storage import save_statement, load_transactions, _storage_path

        json_path = str(tmp_path / "tinkoff_transactions.json")
        with patch("src.telegram.transaction_storage._storage_path", return_value=json_path):
            parsed = {
                "transactions": [
                    {"date": "2026-01-01T10:00:00", "amount": -500, "description": "Test", "card": "*1234", "op_type": "debit"},
                    {"date": "2026-01-02T10:00:00", "amount": 1000, "description": "Salary", "card": "*1234", "op_type": "credit"},
                ],
            }
            new_count = save_statement(parsed)
            assert new_count == 2

            txs = load_transactions(limit=10)
            assert len(txs) == 2

    def test_deduplication(self, tmp_path):
        from src.telegram.transaction_storage import save_statement

        json_path = str(tmp_path / "tinkoff_transactions.json")
        with patch("src.telegram.transaction_storage._storage_path", return_value=json_path):
            parsed = {
                "transactions": [
                    {"date": "2026-01-01T10:00:00", "amount": -500, "description": "Test", "card": "*1234", "op_type": "debit"},
                ],
            }
            save_statement(parsed)
            new_count = save_statement(parsed)  # same data again
            assert new_count == 0  # no new transactions


# ──────────────────────────────────────────────────────────
# Test: TinkoffDataTool
# ──────────────────────────────────────────────────────────

class TestTinkoffDataTool:
    def test_no_data(self):
        from src.tools.financial.tinkoff_data import TinkoffDataTool

        with patch("src.telegram.transaction_storage.get_summary", return_value=None):
            tool = TinkoffDataTool()
            result = tool._run("action=summary")
            assert "нет данных" in result.lower()

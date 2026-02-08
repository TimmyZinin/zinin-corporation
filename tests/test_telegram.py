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
    def test_save_and_load(self):
        from src.telegram.screenshot_storage import (
            save_screenshot_data,
            load_all_screenshots,
        )

        storage = {"screenshot_data": []}

        def mock_load(key, default=None):
            return storage.get(key, default)

        def mock_save(key, data):
            storage[key] = data

        def mock_append(key, item, max_items=200):
            lst = storage.get(key, [])
            lst.append(item)
            if len(lst) > max_items:
                lst = lst[-max_items:]
            storage[key] = lst
            return True

        with patch("src.telegram.screenshot_storage.store.load", side_effect=mock_load), \
             patch("src.telegram.screenshot_storage.store.save", side_effect=mock_save), \
             patch("src.telegram.screenshot_storage.store.append_to_list", side_effect=mock_append):
            data = {
                "source": "TBC Bank",
                "screen_type": "balance",
                "accounts": [{"name": "GEL Account", "balance": "1500.00", "currency": "GEL"}],
                "transactions": [],
                "summary": "TBC Bank balance: 1500 GEL",
            }
            assert save_screenshot_data(data) is True

            loaded = load_all_screenshots()
            assert len(loaded) == 1
            assert loaded[0]["source"] == "TBC Bank"

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

    def test_max_entries_cap(self):
        from src.telegram.screenshot_storage import save_screenshot_data, MAX_ENTRIES

        # Pre-fill with MAX_ENTRIES items
        initial = [{"source": f"test_{i}", "accounts": [], "extracted_at": "2026-01-01"} for i in range(MAX_ENTRIES)]
        storage = {"screenshot_data": list(initial)}

        def mock_append(key, item, max_items=200):
            lst = storage.get(key, [])
            lst.append(item)
            if len(lst) > max_items:
                lst = lst[-max_items:]
            storage[key] = lst
            return True

        with patch("src.telegram.screenshot_storage.store.append_to_list", side_effect=mock_append):
            save_screenshot_data({"source": "new", "accounts": [], "summary": "new"})
            assert len(storage["screenshot_data"]) <= MAX_ENTRIES


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
    def test_save_and_load(self):
        from src.telegram.transaction_storage import save_statement, load_transactions

        storage = {}

        def mock_load(key, default=None):
            return storage.get(key, default)

        def mock_save(key, data):
            storage[key] = data

        with patch("src.telegram.transaction_storage.store.load", side_effect=mock_load), \
             patch("src.telegram.transaction_storage.store.save", side_effect=mock_save):
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

    def test_deduplication(self):
        from src.telegram.transaction_storage import save_statement

        storage = {}

        def mock_load(key, default=None):
            return storage.get(key, default)

        def mock_save(key, data):
            storage[key] = data

        with patch("src.telegram.transaction_storage.store.load", side_effect=mock_load), \
             patch("src.telegram.transaction_storage.store.save", side_effect=mock_save):
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

# ──────────────────────────────────────────────────────────
# Test: Charts & Dashboard
# ──────────────────────────────────────────────────────────

SAMPLE_DASHBOARD_DATA = {
    "crypto": {"EVM (5 chains)": 932.0, "Papaya": 296.6, "Eventum L3": 405.34, "Solana": 6.74, "TON": 10.23},
    "fiat": {"T-Bank": {"usd": 870.0, "original": "85,700 RUB"}},
    "manual": {"TG @wallet": {"usd": 870.0, "original": "~85,700 RUB"}},
    "total_usd": 3390.91,
    "tbank_summary": {
        "income": 125000.0, "expenses": 87000.0, "net": 38000.0,
        "top_categories": [("Рестораны", 15000), ("Такси", 12000), ("Подписки", 8000)],
        "monthly": {"2025-10": {"income": 55000, "expenses": 40000}, "2025-11": {"income": 48000, "expenses": 38000}},
    },
    "rates": {"RUB": 98.5, "GEL": 2.73},
    "timestamp": "2026-02-08 15:30",
}


class TestCharts:
    def test_portfolio_pie_returns_png(self):
        from src.telegram.charts import portfolio_pie
        png = portfolio_pie({"BTC": 100, "ETH": 50}, "Test")
        assert len(png) > 1000
        assert png[:8] == b"\x89PNG\r\n\x1a\n"

    def test_portfolio_pie_empty_data(self):
        from src.telegram.charts import portfolio_pie
        assert portfolio_pie({}) == b""
        assert portfolio_pie({"tiny": 0.1}) == b""

    def test_donut_b64_returns_base64(self):
        from src.telegram.charts import _render_donut_b64
        b64 = _render_donut_b64({"BTC": 100, "ETH": 50}, 150.0)
        assert len(b64) > 100
        import base64
        png = base64.b64decode(b64)
        assert png[:4] == b"\x89PNG"

    def test_donut_b64_empty(self):
        from src.telegram.charts import _render_donut_b64
        assert _render_donut_b64({}, 0) == ""

    def test_text_sparkline(self):
        from src.telegram.charts import _text_sparkline
        spark = _text_sparkline([10, 20, 15, 30, 5])
        assert len(spark) == 5
        assert all(c in "▁▂▃▄▅▆▇█" for c in spark)

    def test_text_sparkline_empty(self):
        from src.telegram.charts import _text_sparkline
        assert _text_sparkline([]) == ""

    def test_text_sparkline_constant(self):
        from src.telegram.charts import _text_sparkline
        spark = _text_sparkline([42, 42, 42])
        assert len(spark) == 3

    def test_build_dashboard_html(self):
        from src.telegram.charts import _build_dashboard_html
        html = _build_dashboard_html(SAMPLE_DASHBOARD_DATA, "fakebase64")
        assert "ZININ CORP" in html
        assert "$3,391" in html
        assert "EVM (5 chains)" in html
        assert "T-Bank" in html
        assert "85,700 RUB" in html
        assert "+125,000" in html
        assert "-87,000" in html
        assert "Рестораны" in html
        assert "1 USD = 98.5 RUB" in html

    def test_build_dashboard_html_no_tbank(self):
        from src.telegram.charts import _build_dashboard_html
        data = {**SAMPLE_DASHBOARD_DATA, "tbank_summary": None}
        html = _build_dashboard_html(data, "fakebase64")
        assert "ZININ CORP" in html
        assert "T-BANK" not in html

    def test_html_to_png_no_chromium(self):
        from src.telegram.charts import _html_to_png
        with patch("shutil.which", return_value=None), \
             patch("os.path.exists", return_value=False), \
             patch.dict(os.environ, {}, clear=True):
            result = _html_to_png("<html><body>test</body></html>")
            assert result == b""

    def test_render_donut_fallback(self):
        from src.telegram.charts import _render_donut_fallback
        sources = {"BTC": 1000, "ETH": 500, "T-Bank": 300}
        data = {
            "crypto": {"BTC": 1000, "ETH": 500},
            "fiat": {"T-Bank": {"usd": 300, "original": "29,500 RUB"}},
            "manual": {},
            "tbank_summary": {"income": 50000, "expenses": 35000},
        }
        png = _render_donut_fallback(sources, 1800, data)
        assert len(png) > 1000
        assert png[:8] == b"\x89PNG\r\n\x1a\n"

    def test_render_financial_dashboard_with_chromium_fallback(self):
        """If Chromium is not available, should fall back to matplotlib."""
        from src.telegram.charts import render_financial_dashboard
        with patch("src.telegram.charts._html_to_png", return_value=b""):
            png = render_financial_dashboard(SAMPLE_DASHBOARD_DATA)
            assert len(png) > 1000
            assert png[:8] == b"\x89PNG\r\n\x1a\n"

    def test_render_financial_dashboard_empty_data(self):
        from src.telegram.charts import render_financial_dashboard
        data = {"crypto": {}, "fiat": {}, "manual": {}, "total_usd": 0}
        assert render_financial_dashboard(data) == b""


class TestChartCaption:
    def test_build_chart_caption(self):
        import importlib
        mod = importlib.import_module("src.telegram.handlers.commands")
        caption = mod._build_chart_caption(SAMPLE_DASHBOARD_DATA)
        assert "$3,391" in caption
        assert "EVM" in caption
        assert "<b>" in caption

    def test_build_chart_text(self):
        import importlib
        mod = importlib.import_module("src.telegram.handlers.commands")
        text = mod._build_chart_text(SAMPLE_DASHBOARD_DATA)
        assert "ИТОГО" in text
        assert "$3,391" in text
        assert "T-Bank" in text
        assert "85,700 RUB" in text


class TestCollectAllData:
    def test_collect_all_with_mocked_sources(self):
        import importlib
        mod = importlib.import_module("src.telegram.handlers.commands")

        with patch.object(mod, "_collect_portfolio_data", return_value={"BTC": 100}), \
             patch("src.tools.financial.forex.get_rates", return_value={"rates": {"RUB": 98.5}}), \
             patch("src.telegram.transaction_storage.get_summary", return_value={
                 "income": 50000, "expenses": 30000, "net": 20000,
                 "top_categories": [("Еда", 10000)], "monthly": {},
             }), \
             patch("src.tools.financial.base.load_financial_config", return_value={
                 "manual_sources": {"telegram_wallet": {"last_known_balance": "~85700 RUB"}},
             }), \
             patch("src.telegram.screenshot_storage.get_latest_balances", return_value={}):
            result = mod._collect_all_financial_data()
            assert result["crypto"] == {"BTC": 100}
            assert "T-Bank" in result["fiat"]
            assert "TG @wallet" in result["manual"]
            assert result["total_usd"] > 100

    def test_collect_all_crypto_only(self):
        import importlib
        mod = importlib.import_module("src.telegram.handlers.commands")

        with patch.object(mod, "_collect_portfolio_data", return_value={"BTC": 500}), \
             patch("src.tools.financial.forex.get_rates", side_effect=Exception("no internet")), \
             patch("src.telegram.transaction_storage.get_summary", return_value=None), \
             patch("src.tools.financial.base.load_financial_config", return_value={}), \
             patch("src.telegram.screenshot_storage.get_latest_balances", return_value={}):
            result = mod._collect_all_financial_data()
            assert result["crypto"] == {"BTC": 500}
            assert result["fiat"] == {}
            assert result["manual"] == {}
            assert result["total_usd"] == 500.0


class TestTinkoffDataTool:
    def test_no_data(self):
        from src.tools.financial.tinkoff_data import TinkoffDataTool

        with patch("src.telegram.transaction_storage.get_summary", return_value=None):
            tool = TinkoffDataTool()
            result = tool._run("action=summary")
            assert "нет данных" in result.lower()

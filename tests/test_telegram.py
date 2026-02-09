"""Tests for Telegram bot modules."""

import asyncio
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
        assert "▸" in caption  # key-value bullets
        assert "·" in caption  # dot leaders
        assert "<code>" in caption  # values in code tags
        assert "━" in caption  # separator

    def test_build_chart_text(self):
        import importlib
        mod = importlib.import_module("src.telegram.handlers.commands")
        text = mod._build_chart_text(SAMPLE_DASHBOARD_DATA)
        assert "ИТОГО" in text
        assert "$3,391" in text
        assert "Т-Банк" in text  # section header
        assert "<b>" in text  # HTML formatted
        assert "▸" in text  # key-value bullets
        assert "+125,000" in text  # income
        assert "-87,000" in text  # expenses


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


# ──────────────────────────────────────────────────────────
# Test: Portfolio Collection (parallel)
# ──────────────────────────────────────────────────────────

class TestPortfolioCollectionParallel:
    """Test that _collect_portfolio_data uses parallel execution."""

    def test_parallel_collection_returns_dict(self):
        import importlib
        mod = importlib.import_module("src.telegram.handlers.commands")

        with patch("src.tools.financial.moralis_evm.EVMPortfolioTool") as mock_evm, \
             patch("src.tools.financial.papaya.PapayaPositionsTool") as mock_papaya, \
             patch("src.tools.financial.eventum.EventumPortfolioTool") as mock_eventum, \
             patch("src.tools.financial.stacks.StacksPortfolioTool") as mock_stacks, \
             patch("src.tools.financial.helius_solana.SolanaPortfolioTool") as mock_sol, \
             patch("src.tools.financial.tonapi.TONPortfolioTool") as mock_ton, \
             patch.dict(os.environ, {"MORALIS_API_KEY": "test"}):

            mock_evm.return_value._run.return_value = "$500.00 USD total across 5 chains"
            mock_papaya.return_value._run.return_value = "ИТОГО $200.00"
            mock_eventum.return_value._run.return_value = "ИТОГО $100.00"
            mock_stacks.return_value._run.return_value = "ИТОГО STX: 1000"
            mock_sol.return_value._run.return_value = "$10.00 USD total"
            mock_ton.return_value._run.return_value = "$5.00 USD total"

            result = mod._collect_portfolio_data()
            assert "EVM (5 chains)" in result
            assert result["EVM (5 chains)"] == 500.0
            assert "Papaya" in result
            assert result["Papaya"] == 200.0
            assert "Eventum L3" in result
            assert result["Eventum L3"] == 100.0
            assert "Stacks" in result
            assert result["Stacks"] == 500.0  # 1000 * 0.5
            assert "Solana" in result
            assert result["Solana"] == 10.0
            assert "TON" in result
            assert result["TON"] == 5.0

    def test_partial_failure_returns_successful(self):
        import importlib
        mod = importlib.import_module("src.telegram.handlers.commands")

        with patch("src.tools.financial.moralis_evm.EVMPortfolioTool") as mock_evm, \
             patch("src.tools.financial.papaya.PapayaPositionsTool") as mock_papaya, \
             patch("src.tools.financial.eventum.EventumPortfolioTool") as mock_eventum, \
             patch("src.tools.financial.stacks.StacksPortfolioTool") as mock_stacks, \
             patch("src.tools.financial.helius_solana.SolanaPortfolioTool") as mock_sol, \
             patch("src.tools.financial.tonapi.TONPortfolioTool") as mock_ton, \
             patch.dict(os.environ, {"MORALIS_API_KEY": "test"}):

            mock_evm.return_value._run.side_effect = Exception("API error")
            mock_papaya.return_value._run.return_value = "ИТОГО $200.00"
            mock_eventum.return_value._run.side_effect = Exception("timeout")
            mock_stacks.return_value._run.return_value = "no data"
            mock_sol.return_value._run.return_value = "$10.00 USD total"
            mock_ton.return_value._run.side_effect = Exception("network error")

            result = mod._collect_portfolio_data()
            assert "Papaya" in result
            assert result["Papaya"] == 200.0
            assert "Solana" in result
            assert "EVM (5 chains)" not in result
            assert "Eventum L3" not in result

    def test_no_moralis_key_skips_evm(self):
        import importlib
        mod = importlib.import_module("src.telegram.handlers.commands")

        with patch("src.tools.financial.papaya.PapayaPositionsTool") as mock_papaya, \
             patch("src.tools.financial.eventum.EventumPortfolioTool") as mock_eventum, \
             patch("src.tools.financial.stacks.StacksPortfolioTool") as mock_stacks, \
             patch("src.tools.financial.helius_solana.SolanaPortfolioTool") as mock_sol, \
             patch("src.tools.financial.tonapi.TONPortfolioTool") as mock_ton, \
             patch.dict(os.environ, {}, clear=True):

            mock_papaya.return_value._run.return_value = "ИТОГО $100.00"
            mock_eventum.return_value._run.return_value = "ИТОГО $50.00"
            mock_stacks.return_value._run.return_value = "no data"
            mock_sol.return_value._run.return_value = "no data"
            mock_ton.return_value._run.return_value = "no data"

            result = mod._collect_portfolio_data()
            assert "Papaya" in result
            assert "EVM (5 chains)" not in result


# ──────────────────────────────────────────────────────────
# Test: Command Handlers (async, mocked)
# ──────────────────────────────────────────────────────────

class TestCommandHandlers:
    """Test all command handlers with mocked bot/message."""

    def _make_message(self):
        msg = AsyncMock()
        msg.answer = AsyncMock(return_value=AsyncMock(delete=AsyncMock()))
        msg.answer_photo = AsyncMock()
        msg.answer_chat_action = AsyncMock()
        msg.from_user = MagicMock(id=123)
        return msg

    @pytest.mark.asyncio
    async def test_cmd_start(self):
        from src.telegram.handlers.commands import cmd_start
        msg = self._make_message()
        await cmd_start(msg)
        msg.answer.assert_called_once()
        call_text = msg.answer.call_args[0][0]
        assert "Маттиас" in call_text
        assert "/chart" in call_text
        assert "<b>" in call_text  # HTML formatted
        assert "▸" in call_text  # Unicode bullets

    @pytest.mark.asyncio
    async def test_cmd_help(self):
        from src.telegram.handlers.commands import cmd_help
        msg = self._make_message()
        await cmd_help(msg)
        msg.answer.assert_called_once()
        call_text = msg.answer.call_args[0][0]
        assert "/report" in call_text
        assert "/chart" in call_text
        assert "<b>" in call_text  # HTML formatted
        assert "▸" in call_text  # Unicode bullets

    @pytest.mark.asyncio
    async def test_cmd_balances_no_data(self):
        from src.telegram.handlers.commands import cmd_balances
        msg = self._make_message()
        with patch("src.telegram.handlers.commands.get_latest_balances", return_value={}):
            await cmd_balances(msg)
        msg.answer.assert_called_once()
        call_text = msg.answer.call_args[0][0]
        assert "нет данных" in call_text.lower() or "Пока нет" in call_text

    @pytest.mark.asyncio
    async def test_cmd_balances_with_data(self):
        from src.telegram.handlers.commands import cmd_balances
        msg = self._make_message()
        mock_data = {
            "TBC Bank": {
                "accounts": [{"balance": "1500.00", "currency": "GEL"}],
                "extracted_at": "2026-02-08T10:00:00",
            }
        }
        with patch("src.telegram.handlers.commands.get_latest_balances", return_value=mock_data):
            await cmd_balances(msg)
        call_text = msg.answer.call_args[0][0]
        assert "TBC" in call_text
        assert "1500" in call_text

    @pytest.mark.asyncio
    async def test_cmd_tinkoff_no_data(self):
        from src.telegram.handlers.commands import cmd_tinkoff
        msg = self._make_message()
        with patch("src.telegram.transaction_storage.get_summary", return_value=None):
            await cmd_tinkoff(msg)
        call_text = msg.answer.call_args[0][0]
        assert "нет данных" in call_text.lower() or "Пока нет" in call_text

    @pytest.mark.asyncio
    async def test_cmd_tinkoff_with_data(self):
        from src.telegram.handlers.commands import cmd_tinkoff
        msg = self._make_message()
        mock_summary = {
            "total_count": 42,
            "income": 85000,
            "expenses": 62000,
            "net": 23000,
            "period": {"start": "2026-01-01T00:00:00", "end": "2026-02-01T00:00:00"},
            "top_categories": [("Рестораны", 12000), ("Такси", 8000)],
            "monthly": {"2026-01": {"income": 85000, "expenses": 62000}},
            "last_updated": "2026-02-08T10:00:00",
        }
        with patch("src.telegram.transaction_storage.get_summary", return_value=mock_summary):
            await cmd_tinkoff(msg)
        call_text = msg.answer.call_args[0][0]
        assert "85,000" in call_text or "85000" in call_text

    @pytest.mark.asyncio
    async def test_cmd_expenses_no_data(self):
        from src.telegram.handlers.commands import cmd_expenses
        msg = self._make_message()
        with patch("src.telegram.transaction_storage.get_summary", return_value=None):
            await cmd_expenses(msg)
        msg.answer.assert_called_once()
        assert "нет данных" in msg.answer.call_args[0][0].lower() or "Нет данных" in msg.answer.call_args[0][0]

    @pytest.mark.asyncio
    async def test_cmd_chart_success(self):
        from src.telegram.handlers.commands import cmd_chart
        import importlib
        mod = importlib.import_module("src.telegram.handlers.commands")

        msg = self._make_message()
        mock_data = {
            "crypto": {"BTC": 1000},
            "fiat": {},
            "manual": {},
            "total_usd": 1000.0,
            "tbank_summary": None,
            "rates": {},
            "timestamp": "2026-02-08",
        }

        with patch.object(mod, "_collect_all_financial_data", return_value=mock_data), \
             patch("src.telegram.charts.render_financial_dashboard", return_value=b"\x89PNG" + b"\x00" * 1000):
            await cmd_chart(msg)

        msg.answer_photo.assert_called_once()
        photo_kwargs = msg.answer_photo.call_args[1]
        assert "caption" in photo_kwargs
        assert "$1,000" in photo_kwargs["caption"]

    @pytest.mark.asyncio
    async def test_cmd_chart_no_data(self):
        from src.telegram.handlers.commands import cmd_chart
        import importlib
        mod = importlib.import_module("src.telegram.handlers.commands")

        msg = self._make_message()
        mock_data = {
            "crypto": {},
            "fiat": {},
            "manual": {},
            "total_usd": 0.0,
            "tbank_summary": None,
            "rates": {},
            "timestamp": "2026-02-08",
        }

        with patch.object(mod, "_collect_all_financial_data", return_value=mock_data):
            await cmd_chart(msg)

        # Should send "no data" message (not a photo)
        msg.answer_photo.assert_not_called()

    @pytest.mark.asyncio
    async def test_cmd_chart_timeout(self):
        from src.telegram.handlers.commands import cmd_chart
        import importlib
        mod = importlib.import_module("src.telegram.handlers.commands")

        msg = self._make_message()

        def slow_collect():
            import time
            time.sleep(200)

        with patch.object(mod, "_collect_all_financial_data", side_effect=slow_collect):
            # Override timeout to 0.01s to trigger fast
            orig_wait = asyncio.wait_for

            async def fast_timeout(coro, *, timeout=None):
                return await orig_wait(coro, timeout=0.01)

            with patch("src.telegram.handlers.commands.asyncio.wait_for", side_effect=asyncio.TimeoutError()):
                await cmd_chart(msg)

        calls = [str(c) for c in msg.answer.call_args_list]
        assert any("Таймаут" in str(c) or "тайм" in str(c).lower() for c in calls)

    @pytest.mark.asyncio
    async def test_cmd_status(self):
        from src.telegram.handlers.commands import cmd_status
        msg = self._make_message()

        with patch("src.tools.financial.base.load_financial_config", return_value={
            "crypto_wallets": {"evm": {"enabled": True, "addresses": ["0x..."]}},
            "banks": {"tbank": {"enabled": False}},
            "payments": {"tribute": {"enabled": False}},
        }), \
             patch("src.tools.financial.base.CredentialBroker.is_configured", return_value=True), \
             patch("src.telegram.handlers.commands.get_latest_balances", return_value={}), \
             patch("src.telegram.transaction_storage.get_summary", return_value=None):
            await cmd_status(msg)

        call_text = msg.answer.call_args[0][0]
        assert "Статус" in call_text


# ──────────────────────────────────────────────────────────
# Test: Message Handler
# ──────────────────────────────────────────────────────────

class TestMessageHandler:
    @pytest.mark.asyncio
    async def test_handle_text_calls_agent(self):
        from src.telegram.handlers.messages import handle_text, _chat_context

        msg = AsyncMock()
        msg.text = "Какой баланс?"
        msg.answer = AsyncMock(return_value=AsyncMock(delete=AsyncMock()))
        msg.answer_chat_action = AsyncMock()

        with patch("src.telegram.handlers.messages.AgentBridge") as mock_bridge:
            mock_bridge.send_to_agent = AsyncMock(return_value="Баланс: $1000")
            await handle_text(msg)

        mock_bridge.send_to_agent.assert_called_once()
        assert any("Баланс" in str(c) or "$1000" in str(c) for c in msg.answer.call_args_list)

    @pytest.mark.asyncio
    async def test_handle_text_empty_ignored(self):
        from src.telegram.handlers.messages import handle_text

        msg = AsyncMock()
        msg.text = "   "
        msg.answer = AsyncMock()
        await handle_text(msg)
        msg.answer.assert_not_called()


# ──────────────────────────────────────────────────────────
# Test: Formatters (extended)
# ──────────────────────────────────────────────────────────

class TestFormattersExtended:
    def test_mono_table(self):
        from src.telegram.formatters import mono_table
        result = mono_table(["Name", "Value"], [["BTC", "$1000"], ["ETH", "$500"]])
        assert "<pre>" in result
        assert "BTC" in result
        assert "$1000" in result

    def test_sparkline(self):
        from src.telegram.formatters import sparkline
        result = sparkline([10, 20, 30, 15, 5])
        assert len(result) == 5
        assert all(c in "▁▂▃▄▅▆▇█" for c in result)

    def test_sparkline_empty(self):
        from src.telegram.formatters import sparkline
        assert sparkline([]) == ""

    def test_progress_bar(self):
        from src.telegram.formatters import progress_bar
        result = progress_bar(75, 100, width=10)
        assert "█" in result
        assert "75%" in result

    def test_format_for_telegram_exact_boundary(self):
        from src.telegram.formatters import format_for_telegram
        text = "A" * 4096
        result = format_for_telegram(text, max_length=4096)
        assert len(result) == 1
        assert len(result[0]) == 4096

    def test_format_for_telegram_unicode(self):
        from src.telegram.formatters import format_for_telegram
        text = "Баланс: ₽85,000 — Т-Банк 🏦"
        result = format_for_telegram(text)
        assert result == [text]


# ──────────────────────────────────────────────────────────
# Test: Markdown → HTML Conversion
# ──────────────────────────────────────────────────────────

class TestMarkdownToTelegramHtml:
    def test_empty_input(self):
        from src.telegram.formatters import markdown_to_telegram_html
        assert markdown_to_telegram_html("") == ""
        assert markdown_to_telegram_html(None) == ""

    def test_bold(self):
        from src.telegram.formatters import markdown_to_telegram_html
        result = markdown_to_telegram_html("This is **bold** text")
        assert "<b>bold</b>" in result

    def test_inline_code(self):
        from src.telegram.formatters import markdown_to_telegram_html
        result = markdown_to_telegram_html("Use `code` here")
        assert "<code>code</code>" in result

    def test_code_block(self):
        from src.telegram.formatters import markdown_to_telegram_html
        result = markdown_to_telegram_html("```python\nprint('hello')\n```")
        assert "<pre>" in result
        assert "print" in result

    def test_headers(self):
        from src.telegram.formatters import markdown_to_telegram_html
        result = markdown_to_telegram_html("## Section Title")
        assert "<b>" in result
        assert "SECTION TITLE" in result
        assert "━" in result

    def test_h3_header(self):
        from src.telegram.formatters import markdown_to_telegram_html
        result = markdown_to_telegram_html("### Subsection")
        assert "<b>Subsection</b>" in result
        assert "───" in result

    def test_bullets(self):
        from src.telegram.formatters import markdown_to_telegram_html
        result = markdown_to_telegram_html("- Item one\n- Item two")
        assert "▸ Item one" in result
        assert "▸ Item two" in result

    def test_horizontal_rule(self):
        from src.telegram.formatters import markdown_to_telegram_html
        result = markdown_to_telegram_html("text\n---\nmore")
        assert "━━━" in result

    def test_html_escape(self):
        from src.telegram.formatters import markdown_to_telegram_html
        result = markdown_to_telegram_html("1 < 2 & 3 > 1")
        assert "&lt;" in result
        assert "&amp;" in result
        assert "&gt;" in result
        assert "<" not in result.replace("&lt;", "").replace("<b>", "").replace("</b>", "").replace("<i>", "").replace("</i>", "").replace("<code>", "").replace("</code>", "").replace("<pre>", "").replace("</pre>", "").replace("<blockquote>", "").replace("</blockquote>", "")

    def test_italic(self):
        from src.telegram.formatters import markdown_to_telegram_html
        result = markdown_to_telegram_html("This is *italic* text")
        assert "<i>italic</i>" in result

    def test_combined_formatting(self):
        from src.telegram.formatters import markdown_to_telegram_html
        result = markdown_to_telegram_html("**bold** and `code` and *italic*")
        assert "<b>bold</b>" in result
        assert "<code>code</code>" in result
        assert "<i>italic</i>" in result

    def test_excessive_blank_lines(self):
        from src.telegram.formatters import markdown_to_telegram_html
        result = markdown_to_telegram_html("a\n\n\n\n\nb")
        assert "\n\n\n" not in result


# ──────────────────────────────────────────────────────────
# Test: Section Builders
# ──────────────────────────────────────────────────────────

class TestSectionBuilders:
    def test_section_header(self):
        from src.telegram.formatters import section_header
        result = section_header("Портфель", "🏦")
        assert "🏦" in result
        assert "<b>Портфель</b>" in result
        assert "━" in result

    def test_section_header_no_emoji(self):
        from src.telegram.formatters import section_header
        result = section_header("Title")
        assert "<b>Title</b>" in result
        assert "━" in result

    def test_key_value(self):
        from src.telegram.formatters import key_value
        result = key_value("Доход", "+85,000 RUB")
        assert "▸ Доход" in result
        assert "·" in result
        assert "<code>+85,000 RUB</code>" in result

    def test_separator_thick(self):
        from src.telegram.formatters import separator
        result = separator("thick")
        assert "━" in result

    def test_separator_thin(self):
        from src.telegram.formatters import separator
        result = separator("thin")
        assert "─" in result

    def test_status_indicator(self):
        from src.telegram.formatters import status_indicator
        assert status_indicator("ok") == "🟢"
        assert status_indicator("warn") == "🟡"
        assert status_indicator("error") == "🔴"
        assert status_indicator("off") == "⚫"
        assert status_indicator("unknown") == "⚪"

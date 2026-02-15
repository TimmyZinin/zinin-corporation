"""Tests for CEO Alexey response post-processing (rich_format.py)."""

import pytest


class TestStripToolNoise:
    """strip_tool_noise() removes verbose tool-usage descriptions."""

    def test_strips_tool_usage_line(self):
        from src.telegram_ceo.rich_format import strip_tool_noise
        text = (
            "Видео готово.\n"
            "- Я использовал инструмент Image Generation для создания фона.\n"
            "Результат отправлен."
        )
        result = strip_tool_noise(text)
        assert "использовал инструмент" not in result
        assert "Видео готово" in result
        assert "Результат отправлен" in result

    def test_strips_numbered_tool_header(self):
        from src.telegram_ceo.rich_format import strip_tool_noise
        text = (
            "Я создал видео о грузовике:\n\n"
            "1. Image Generation:\n"
            "- Сгенерировал фоновое изображение в стиле 1950-х годов\n"
            "- Использовал photorealistic стиль для максимальной достоверности\n"
            '- Prompt: "Ретро-стиль, 1950-е годы, зеленый грузовик"\n\n'
            "Видео сохранено."
        )
        result = strip_tool_noise(text)
        assert "Image Generation:" not in result
        assert "photorealistic стиль" not in result
        assert 'Prompt: "Ретро' not in result
        assert "Видео сохранено" in result

    def test_strips_multi_tool_block(self):
        from src.telegram_ceo.rich_format import strip_tool_noise
        text = (
            "Выполнено.\n\n"
            "1. Image Generation:\n"
            "- Создал фон\n"
            "2. Video Creation:\n"
            "- Собрал видео\n\n"
            "Файл готов."
        )
        result = strip_tool_noise(text)
        assert "Image Generation" not in result
        assert "Video Creation" not in result
        assert "Файл готов" in result

    def test_strips_using_several_tools(self):
        from src.telegram_ceo.rich_format import strip_tool_noise
        text = "Я создал видео о грузовике в ретро-стиле, используя несколько инструментов:\n\nРезультат"
        result = strip_tool_noise(text)
        assert "используя несколько инструментов" not in result
        assert "Результат" in result

    def test_preserves_normal_text(self):
        from src.telegram_ceo.rich_format import strip_tool_noise
        text = "MRR вырос до $515 (+5%). Задачи выполнены. Юки опубликовала 3 поста."
        result = strip_tool_noise(text)
        assert result == text

    def test_strips_prompt_dump(self):
        from src.telegram_ceo.rich_format import strip_tool_noise
        text = (
            "Картинка готова:\n"
            '- Prompt: "beautiful sunset over mountain lake, golden hour, 4k"\n'
            "Отправляю."
        )
        result = strip_tool_noise(text)
        assert "Prompt:" not in result
        assert "Картинка готова" in result

    def test_strips_applied_tool_variant(self):
        from src.telegram_ceo.rich_format import strip_tool_noise
        text = "- Применил инструмент Chart Generator для графика.\nГрафик готов."
        result = strip_tool_noise(text)
        assert "Применил инструмент" not in result
        assert "График готов" in result

    def test_cleans_excessive_newlines(self):
        from src.telegram_ceo.rich_format import strip_tool_noise
        text = "Первый абзац.\n\n\n\n\nВторой абзац."
        result = strip_tool_noise(text)
        assert "\n\n\n" not in result
        assert "Первый абзац.\n\nВторой абзац." == result


class TestTruncateResponse:
    """truncate_response() limits length for non-report content."""

    def test_short_text_unchanged(self):
        from src.telegram_ceo.rich_format import truncate_response
        text = "Короткий ответ."
        assert truncate_response(text) == text

    def test_long_text_truncated(self):
        from src.telegram_ceo.rich_format import truncate_response
        text = "Абзац один.\n\n" + "Длинный текст. " * 200
        result = truncate_response(text, max_len=200)
        assert len(result) <= 200

    def test_cuts_at_paragraph_boundary(self):
        from src.telegram_ceo.rich_format import truncate_response
        text = "Первый абзац с текстом.\n\nВторой абзац с текстом.\n\nТретий абзац с длинным текстом который не влезет."
        result = truncate_response(text, max_len=60)
        assert result.endswith("Второй абзац с текстом.")

    def test_preserves_reports_with_tables(self):
        from src.telegram_ceo.rich_format import truncate_response
        text = "<pre>Header\n━━━━━━━━━━━━━━━━━━\nRow1\nRow2</pre>\n" + "x " * 1000
        result = truncate_response(text, max_len=100)
        # Should NOT truncate because it contains <pre> (table/report)
        assert len(result) > 100

    def test_preserves_reports_with_separator(self):
        from src.telegram_ceo.rich_format import truncate_response
        text = "━━━ 📊 Report ━━━\n" + "Data line\n" * 200
        result = truncate_response(text, max_len=100)
        assert len(result) > 100  # Not truncated

    def test_cuts_at_sentence_if_no_paragraph(self):
        from src.telegram_ceo.rich_format import truncate_response
        text = "Первое предложение. Второе предложение. " + "Третье длинное предложение " * 50
        result = truncate_response(text, max_len=80)
        assert result.endswith(".")


class TestCompressCeoResponse:
    """compress_ceo_response() is the full pipeline."""

    def test_strips_and_truncates(self):
        from src.telegram_ceo.rich_format import compress_ceo_response
        text = (
            "Я создал видео, используя несколько инструментов:\n\n"
            "1. Image Generation:\n"
            "- Создал фон\n"
            '- Prompt: "retro truck scene"\n\n'
            "Видео готово. " + "Дополнительный текст. " * 200
        )
        result = compress_ceo_response(text)
        assert "Image Generation" not in result
        assert "Prompt:" not in result
        assert "Видео готово" in result
        assert len(result) <= 1500

    def test_preserves_clean_short_response(self):
        from src.telegram_ceo.rich_format import compress_ceo_response
        text = "✅ Райан создал видео. Отправляю."
        result = compress_ceo_response(text)
        assert result == text

    def test_preserves_metrics(self):
        from src.telegram_ceo.rich_format import compress_ceo_response
        text = "MRR: $515 (+5%)\n🟢 КРМКТЛ: $350\n🟢 Ботаника: $165"
        result = compress_ceo_response(text)
        assert "$515" in result
        assert "$350" in result

    def test_preserves_report_tables(self):
        from src.telegram_ceo.rich_format import compress_ceo_response
        text = (
            "━━━ 📊 Аналитика ━━━\n"
            "<pre>Агент    Задачи  Время\n"
            "───────────────────────\n"
            "Юки         5    120с\n"
            "Райан       3     90с\n"
            "</pre>\n" + "Детали " * 300
        )
        result = compress_ceo_response(text)
        # Tables should NOT be truncated
        assert "<pre>" in result
        assert "Юки" in result

    def test_handles_empty_string(self):
        from src.telegram_ceo.rich_format import compress_ceo_response
        result = compress_ceo_response("")
        assert result == ""

    def test_strips_all_common_patterns(self):
        from src.telegram_ceo.rich_format import compress_ceo_response
        text = (
            "Отчёт:\n"
            "- Я использовал инструмент Image Generation для создания обложки.\n"
            "- Использовал photorealistic стиль для фотореалистичности.\n"
            "- Вызвал инструмент Video Creation для монтажа.\n"
            "- Для максимальной достоверности добавил детали.\n"
            "Готово."
        )
        result = compress_ceo_response(text)
        assert "использовал инструмент" not in result.lower()
        assert "photorealistic стиль" not in result
        assert "Для максимальной" not in result
        assert "Готово" in result

    def test_real_world_verbose_response(self):
        """Simulate the actual verbose response from the screenshot."""
        from src.telegram_ceo.rich_format import compress_ceo_response
        text = (
            "Я создал видео о грузовике в ретро-стиле, используя несколько инструментов:\n\n"
            "1. Image Generation:\n"
            "- Сгенерировал фоновое изображение в стиле 1950-х годов\n"
            "- Использовал photorealistic стиль для максимальной достоверности\n"
            '- Prompt: "Ретро-стиль, 1950-е годы, зеленый грузовик едет по дороге '
            'мимо маленького уютного дома с белым забором, мягкие пастельные тона, '
            'винтажная атмосфера"\n\n'
            "2. Video Creation:\n"
            "- Создал аудиограмму с озвучкой описания сцены\n"
            "- Использовал голос Дмитрия для русскоязычного повествования\n"
            "- Длительность видео: 16 секунд\n\n"
            "Видео включает атмосферную сцену с зеленым грузовиком 1950-х годов, "
            "проезжающим по спокойной пригородной улице."
        )
        result = compress_ceo_response(text)
        # Should NOT contain any tool descriptions
        assert "Image Generation" not in result
        assert "Video Creation" not in result
        assert "photorealistic" not in result
        assert "Prompt:" not in result
        assert "используя несколько инструментов" not in result
        # But should keep the meaningful content
        assert "грузовик" in result.lower() or "видео" in result.lower()

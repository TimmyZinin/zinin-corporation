"""Claude Vision API for parsing financial screenshots."""

import json
import logging
import os
import re

import httpx

logger = logging.getLogger(__name__)

VISION_PROMPT = """Ты — финансовый ассистент. Перед тобой скриншот банковского приложения или крипто-кошелька.

Извлеки ВСЮ финансовую информацию:
1. Название банка/сервиса (TBC Bank, Telegram @wallet, и т.д.)
2. Тип экрана (баланс, выписка, транзакция)
3. Все суммы с валютами (точные цифры, не округляй)
4. Названия счетов
5. Даты (если видны)
6. Контрагенты транзакций (если видны)

Ответь ТОЛЬКО JSON (без markdown блока):
{
  "source": "TBC Bank / Telegram @wallet / другое",
  "screen_type": "balance / statement / transaction",
  "accounts": [
    {"name": "...", "balance": "...", "currency": "..."}
  ],
  "transactions": [
    {"date": "...", "amount": "...", "currency": "...", "description": "...", "counterparty": "..."}
  ],
  "summary": "краткое описание на русском — что видно на скриншоте, ключевые цифры"
}

Если что-то не видно или нечитаемо — укажи null. НЕ ВЫДУМЫВАЙ данных."""


async def extract_financial_data(
    b64_image: str,
    user_hint: str = "",
) -> dict:
    """Extract financial data from a base64-encoded screenshot.

    Uses Claude Sonnet 4 via OpenRouter for accurate OCR of financial data.
    """
    api_key = os.getenv("OPENROUTER_API_KEY", "")
    if not api_key:
        raise EnvironmentError("OPENROUTER_API_KEY not set")

    prompt = VISION_PROMPT
    if user_hint:
        prompt += f"\n\nПодсказка от пользователя: {user_hint}"

    payload = {
        "model": "anthropic/claude-sonnet-4",
        "messages": [
            {
                "role": "user",
                "content": [
                    {
                        "type": "image_url",
                        "image_url": {
                            "url": f"data:image/jpeg;base64,{b64_image}",
                        },
                    },
                    {"type": "text", "text": prompt},
                ],
            }
        ],
        "max_tokens": 2000,
        "temperature": 0,
    }

    async with httpx.AsyncClient(timeout=60.0) as client:
        response = await client.post(
            "https://openrouter.ai/api/v1/chat/completions",
            headers={
                "Authorization": f"Bearer {api_key}",
                "Content-Type": "application/json",
            },
            json=payload,
        )
        response.raise_for_status()
        data = response.json()

    content = data["choices"][0]["message"]["content"]

    # Extract JSON from response
    json_match = re.search(r"\{[\s\S]*\}", content)
    if json_match:
        try:
            return json.loads(json_match.group())
        except json.JSONDecodeError:
            pass

    # Fallback: return raw text as summary
    return {
        "source": "unknown",
        "screen_type": "unknown",
        "accounts": [],
        "transactions": [],
        "summary": content[:500],
    }

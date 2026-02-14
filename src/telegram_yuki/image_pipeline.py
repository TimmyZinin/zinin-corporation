"""
Image Pipeline — Routes image generation to Ryan (Designer) or local Yuki fallback.

Feature flag: RYAN_IMAGE_PIPELINE=1 (env var) enables Ryan delegation.
Default: uses local image_gen.py (Yuki's own generator).
"""

import logging
import os

logger = logging.getLogger(__name__)


def is_ryan_pipeline_enabled() -> bool:
    """Check if Ryan image pipeline is enabled via env var."""
    return os.getenv("RYAN_IMAGE_PIPELINE", "0") == "1"


async def generate_image_via_pipeline(topic: str, post_text: str = "") -> str:
    """Generate image — routes to Ryan if pipeline enabled, else local Yuki.

    Returns path to saved image file, or empty string on failure.
    """
    if is_ryan_pipeline_enabled():
        return await _generate_via_ryan(topic)
    else:
        return await _generate_via_yuki(topic, post_text)


async def _generate_via_ryan(topic: str) -> str:
    """Delegate image generation to Ryan via AgentBridge."""
    try:
        from ..telegram.bridge import AgentBridge
        result = await AgentBridge.run_generate_image(topic=topic, style="isotype")

        # Result is either "Изображение сохранено: /path/to/file.png" or error
        if "сохранено:" in result:
            path = result.split("сохранено:", 1)[1].strip()
            logger.info("Ryan generated image: %s", path)
            return path
        elif result.startswith("/") or result.startswith("data/"):
            return result
        else:
            logger.warning("Ryan image generation failed: %s", result[:200])
            # Fallback to Yuki
            return await _generate_via_yuki(topic, "")
    except Exception as e:
        logger.warning("Ryan pipeline error, falling back to Yuki: %s", e)
        return await _generate_via_yuki(topic, "")


async def _generate_via_yuki(topic: str, post_text: str) -> str:
    """Local Yuki image generation (original behavior)."""
    import asyncio
    from .image_gen import generate_image
    return await asyncio.to_thread(generate_image, topic, post_text)

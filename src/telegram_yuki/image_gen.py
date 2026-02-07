"""Image generation for Yuki SMM bot — ISOTYPE pictographic style via OpenRouter."""

import base64
import json
import logging
import os
import random
import time
from datetime import datetime
from pathlib import Path
from urllib.request import urlopen, Request
from urllib.error import URLError, HTTPError

logger = logging.getLogger(__name__)

IMAGES_DIR = Path(__file__).parent.parent.parent / "data" / "yuki_images"
IMAGES_DIR.mkdir(parents=True, exist_ok=True)

# ============================================================================
# SCENE LIBRARY — ISOTYPE pictographic scenes
# ============================================================================

SCENES = {
    "career_stairs": """EXACT SCENE — CAREER GROWTH: A person climbing stairs upward:

ELEMENT 1 — STAIRS (center):
4 black rectangles arranged as ascending steps, each 12% wide, 6% tall, positioned from lower-left to upper-right.

ELEMENT 2 — PERSON (on stairs):
Black human figure silhouette: small square head (4%), tall rectangle body (6% × 16%), thin base (10% × 3%). Standing on the third step.

ELEMENT 3 — ARROW (KEY — LIME):
Bold bright electric lime (#DFFF00) arrow pointing UP from the top step. Triangle tip (12% × 10%) + rectangle shaft (6% × 14%).

ELEMENT 4 — GROUND LINE:
Thin horizontal black rectangle at bottom (70% × 2%).""",

    "standout_grid": """EXACT SCENE — STANDING OUT: One highlighted figure among identical ones:

ELEMENT 1 — GRID OF FIGURES:
5 small black human figure silhouettes in a row, each: square head (3%), rectangle body (5% × 12%), base (8% × 2%).

ELEMENT 2 — HIGHLIGHTED FIGURE (KEY — LIME):
One bright electric lime (#DFFF00) human figure silhouette, same proportions but 1.5x larger, positioned above the row. This person STANDS OUT.

ELEMENT 3 — SPOTLIGHT:
Lime triangle (15% base, 12% height) pointing DOWN above the highlighted figure.

ELEMENT 4 — GROUND LINE:
Thin horizontal black rectangle at bottom.""",

    "document_transform": """EXACT SCENE — DOCUMENT IMPROVEMENT: Old document transforms into new:

ELEMENT 1 — OLD DOCUMENT (left):
Black vertical rectangle (18% × 24%) with 3 thin white horizontal lines inside.

ELEMENT 2 — ARROW (KEY — LIME):
Bright electric lime (#DFFF00) horizontal arrow: triangle tip (10% × 8%) + shaft (20% × 4%).

ELEMENT 3 — NEW DOCUMENT (right):
Black vertical rectangle (18% × 24%) with white lines + lime checkmark (8% × 8%) above it.

ELEMENT 4 — GROUND LINE:
Thin horizontal black rectangle at bottom.""",

    "chart_growth": """EXACT SCENE — GROWTH CHART: Rising bar chart with upward arrow:

ELEMENT 1 — BAR CHART (center):
3 black vertical rectangles, each 6% wide with 2% gaps. Heights: 12%, 20%, 28%.

ELEMENT 2 — ARROW (KEY — LIME):
Bold bright electric lime (#DFFF00) arrow pointing UP from tallest bar. Triangle (12% × 10%) + shaft (6% × 14%).

ELEMENT 3 — PERSON (left):
Black human figure silhouette next to the chart. Head (4%), body (6% × 16%), base (10% × 3%).

ELEMENT 4 — BASELINE:
Thin horizontal black rectangle under the bars (30% × 2%).""",

    "bridge_gap": """EXACT SCENE — BRIDGING A GAP: Person crossing between two platforms:

ELEMENT 1 — LOWER PLATFORM (left):
Black horizontal rectangle (30% × 8%) in lower-left.

ELEMENT 2 — HIGHER PLATFORM (right):
Black horizontal rectangle (30% × 8%) in upper-right, 20% higher.

ELEMENT 3 — BRIDGE (KEY — LIME):
Bright electric lime (#DFFF00) diagonal rectangle (25% × 4%) spanning the gap.

ELEMENT 4 — PERSON:
Black human figure silhouette on the bridge, mid-crossing.

ELEMENT 5 — GROUND LINE:
Thin horizontal black rectangle at bottom.""",

    "lever_lift": """EXACT SCENE — LEVERAGE: Person using lever to lift heavy object:

ELEMENT 1 — LEVER (diagonal):
Thick black diagonal rectangle (60% × 5%) at ~30° angle.

ELEMENT 2 — FULCRUM:
Black triangle (12% base, 10% height) under lever at 1/3 point.

ELEMENT 3 — PERSON (left):
Black human figure pushing DOWN at low end.

ELEMENT 4 — RISING OBJECT (KEY — LIME):
Large bright electric lime (#DFFF00) rectangle (18% × 14%) at high end, being LIFTED.

ELEMENT 5 — RESULT ARROW:
Lime arrow pointing UP near the rising object.""",

    "puzzle_system": """EXACT SCENE — SYSTEM BUILDING: Puzzle pieces coming together:

ELEMENT 1 — ASSEMBLED PIECES (center):
3 black rectangles (15% × 12% each) arranged in an L-shape, touching each other — the system being built.

ELEMENT 2 — MISSING PIECE (KEY — LIME):
One bright electric lime (#DFFF00) rectangle (15% × 12%) floating above, with a small gap — about to complete the structure.

ELEMENT 3 — ARROW:
Lime arrow pointing DOWN toward the gap.

ELEMENT 4 — PERSON (right):
Black human figure silhouette holding/guiding the lime piece.

ELEMENT 5 — GROUND LINE:
Thin horizontal black rectangle at bottom.""",

    "target_hit": """EXACT SCENE — HITTING THE TARGET: Arrow hitting bullseye:

ELEMENT 1 — TARGET (center-right):
Concentric squares: outer black (30% × 30%), inner white (20% × 20%), center lime (#DFFF00) (10% × 10%).

ELEMENT 2 — ARROW:
Black diagonal line (rectangle 3% × 40%) pointing from lower-left to center of target.

ELEMENT 3 — IMPACT (KEY — LIME):
Lime star-burst: 4 small lime rectangles (3% × 10% each) at 45° angles radiating from center — impact flash.

ELEMENT 4 — PERSON (left):
Black human figure silhouette in shooting stance.

ELEMENT 5 — GROUND LINE:
Thin horizontal black rectangle at bottom.""",
}

# Topic keyword → scene variants mapping
TOPIC_MAPPING = {
    "карьер": ["career_stairs", "chart_growth", "bridge_gap"],
    "рост": ["career_stairs", "chart_growth"],
    "зарплат": ["lever_lift", "chart_growth", "bridge_gap"],
    "резюме": ["document_transform", "standout_grid"],
    "cv": ["document_transform", "standout_grid"],
    "собеседов": ["standout_grid", "target_hit"],
    "интервью": ["standout_grid", "target_hit"],
    "лидер": ["career_stairs", "standout_grid"],
    "менедж": ["puzzle_system", "lever_lift"],
    "ai": ["puzzle_system", "chart_growth", "target_hit"],
    "ии": ["puzzle_system", "chart_growth"],
    "агент": ["puzzle_system", "lever_lift"],
    "автоматиз": ["puzzle_system", "lever_lift"],
    "linkedin": ["document_transform", "standout_grid"],
    "контент": ["document_transform", "target_hit"],
    "пост": ["document_transform", "target_hit"],
    "бренд": ["standout_grid", "target_hit"],
    "стратег": ["chart_growth", "lever_lift", "bridge_gap"],
    "бизнес": ["chart_growth", "lever_lift"],
    "команд": ["puzzle_system", "standout_grid"],
    "навык": ["career_stairs", "bridge_gap"],
    "skill": ["career_stairs", "bridge_gap"],
    "remote": ["bridge_gap", "puzzle_system"],
    "удалён": ["bridge_gap", "puzzle_system"],
}

DEFAULT_SCENES = list(SCENES.keys())


def _select_scene(topic: str) -> str:
    """Select a scene based on topic keywords."""
    topic_lower = topic.lower()
    for keyword, variants in TOPIC_MAPPING.items():
        if keyword in topic_lower:
            return random.choice(variants)
    return random.choice(DEFAULT_SCENES)


def _build_prompt(topic: str, post_text: str) -> str:
    """Build the full image generation prompt."""
    scene_key = _select_scene(topic)
    scene_desc = SCENES[scene_key]

    return f"""Create a flat 2D vector illustration in the style of ISOTYPE pictograms meets Soviet Constructivist poster. Square format 1:1. Pure white background (#FFFFFF).

STYLE DIRECTION:
This is NOT abstract art. This is a PICTOGRAPHIC ILLUSTRATION where recognizable objects (people, documents, arrows, laptops) are built from simple geometric shapes. Each object is a simplified silhouette assembled from 2-4 rectangles, squares, and triangles. Think: Gerd Arntz pictograms, Otto Neurath ISOTYPE charts.

{scene_desc}

HOW TO BUILD PICTOGRAPHIC OBJECTS:
- A PERSON = small square head (4%) on tall rectangle body (6% × 16%) on thin base (10% × 3%).
- A DOCUMENT = vertical rectangle with 2-3 thin horizontal rectangles inside.
- AN ARROW = triangle tip on a rectangle shaft.
- A CHECKMARK = two thick rectangles joined at angle forming V-check.
- STAIRS = 3-4 rectangles in ascending step pattern.

COMPOSITION RULES:
- Total: 8-12 geometric shapes forming 2-4 recognizable pictographic objects
- Shapes fill 40-50% of canvas — DENSE and BOLD
- ASYMMETRIC layout
- Lime (#DFFF00) element is the FOCAL POINT — viewer's eye goes there FIRST

COLOR PALETTE — STRICT:
- Black (#000000) — primary objects
- White (#FFFFFF) — background ONLY
- Electric lime (#DFFF00) — exactly ONE key element. BRIGHT yellow-green. RGB: 223, 255, 0.

STRICT PROHIBITIONS:
- NO text, letters, numbers, words
- NO gradients, shadows, glows
- NO 3D, perspective, depth
- NO textures, noise
- NO colors other than black, white, lime (#DFFF00)
- NO curves, circles, rounded corners
- NO realistic detail — SIMPLIFIED PICTOGRAMS only

The result must look like a bold pictographic poster: instantly readable, powerful composition."""


def _call_openrouter(prompt: str, max_retries: int = 2) -> dict:
    """Call OpenRouter API with Gemini 2.5 Flash Image."""
    api_key = os.getenv("OPENROUTER_API_KEY", "")
    if not api_key:
        logger.warning("OPENROUTER_API_KEY not set — image generation skipped")
        return {"error": "API key not configured"}

    url = "https://openrouter.ai/api/v1/chat/completions"
    payload = {
        "model": "google/gemini-2.5-flash-image",
        "messages": [{"role": "user", "content": prompt}],
        "modalities": ["image", "text"],
    }
    headers = {
        "Content-Type": "application/json",
        "Authorization": f"Bearer {api_key}",
        "HTTP-Referer": "https://zinin.corp",
        "X-Title": "Yuki SMM Bot",
    }

    for attempt in range(max_retries):
        try:
            req = Request(url, data=json.dumps(payload).encode(), headers=headers)
            with urlopen(req, timeout=120) as resp:
                return json.loads(resp.read().decode())
        except HTTPError as e:
            if e.code == 429:
                time.sleep(60)
            elif attempt < max_retries - 1:
                time.sleep(2 ** attempt)
            else:
                return {"error": f"HTTP {e.code}"}
        except (URLError, Exception) as e:
            if attempt < max_retries - 1:
                time.sleep(2 ** attempt)
            else:
                return {"error": str(e)}

    return {"error": "Max retries exceeded"}


def _extract_image(response: dict) -> bytes | None:
    """Extract image bytes from OpenRouter API response."""
    if "error" in response:
        return None

    choices = response.get("choices", [])
    if not choices:
        return None

    message = choices[0].get("message", {})

    # Check images field
    for img in message.get("images", []):
        url = img.get("image_url", {}).get("url", "")
        if url.startswith("data:image") and "," in url:
            return base64.b64decode(url.split(",", 1)[1])

    # Check content array
    content = message.get("content", "")
    if isinstance(content, list):
        for item in content:
            if isinstance(item, dict) and item.get("type") == "image_url":
                url = item.get("image_url", {}).get("url", "")
                if url.startswith("data:image") and "," in url:
                    return base64.b64decode(url.split(",", 1)[1])

    logger.warning(f"No image in response. Keys: {list(response.keys())}")
    return None


def generate_image(topic: str, post_text: str = "") -> str:
    """Generate an ISOTYPE-style image for a post topic.

    Returns path to saved image file, or empty string on failure.
    """
    try:
        prompt = _build_prompt(topic, post_text)
        logger.info(f"Generating image for topic: {topic[:50]}")

        response = _call_openrouter(prompt)
        image_data = _extract_image(response)

        if not image_data:
            logger.warning("Image generation returned no image data")
            return ""

        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        path = IMAGES_DIR / f"yuki_{timestamp}.png"
        path.parent.mkdir(parents=True, exist_ok=True)

        with open(path, "wb") as f:
            f.write(image_data)

        logger.info(f"Image saved: {path}")
        return str(path)

    except Exception as e:
        logger.error(f"Image generation error: {e}", exc_info=True)
        return ""

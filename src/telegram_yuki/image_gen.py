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

    # ── NEW SCENES ──────────────────────────────────────────────────────

    "network_nodes": """EXACT SCENE — NETWORKING: Connected nodes forming a network:

ELEMENT 1 — CENTRAL NODE (KEY — LIME):
Bright electric lime (#DFFF00) square (12% × 12%) in the center — the main person/hub.

ELEMENT 2 — SATELLITE NODES:
5 black squares (6% × 6%) arranged around the central node at varying distances, like a constellation.

ELEMENT 3 — CONNECTIONS:
Black horizontal and vertical rectangles (2% wide) connecting the central lime node to each satellite. Lines form a star pattern.

ELEMENT 4 — GROUND LINE:
Thin horizontal black rectangle at bottom.""",

    "shield_protect": """EXACT SCENE — PROTECTION/SECURITY: A shield protecting a person:

ELEMENT 1 — SHIELD (KEY — LIME):
Large bright electric lime (#DFFF00) rectangle (20% × 28%) with a smaller white rectangle cutout inside (12% × 18%), forming a frame/shield shape.

ELEMENT 2 — PERSON BEHIND SHIELD:
Black human figure silhouette partially visible behind the shield.

ELEMENT 3 — THREATS (left):
3 small black triangles pointing RIGHT toward the shield — incoming threats being blocked.

ELEMENT 4 — GROUND LINE:
Thin horizontal black rectangle at bottom.""",

    "megaphone_voice": """EXACT SCENE — CONTENT/VOICE: Person with megaphone broadcasting:

ELEMENT 1 — PERSON (left):
Black human figure silhouette, head (4%), body (6% × 16%).

ELEMENT 2 — MEGAPHONE (KEY — LIME):
Bright electric lime (#DFFF00) trapezoid/triangle (20% wide, 14% tall) pointing RIGHT from the person's head — the voice/content being broadcast.

ELEMENT 3 — SOUND WAVES:
3 black vertical rectangles (2% × varying heights: 10%, 16%, 22%) to the right of megaphone — expanding sound waves.

ELEMENT 4 — GROUND LINE:
Thin horizontal black rectangle at bottom.""",

    "clock_deadline": """EXACT SCENE — TIME/DEADLINE: Clock with urgent arrow:

ELEMENT 1 — CLOCK FACE:
Large black square (30% × 30%) with white square inside (22% × 22%), forming a thick frame — the clock.

ELEMENT 2 — CLOCK HANDS (KEY — LIME):
Two bright electric lime (#DFFF00) rectangles inside the clock: one vertical (3% × 12%) pointing up, one horizontal (3% × 8%) pointing right — showing time.

ELEMENT 3 — PERSON RUNNING:
Black human figure silhouette in motion (leaning forward) to the right of the clock.

ELEMENT 4 — URGENCY ARROW:
Lime arrow pointing RIGHT from the clock toward the person.

ELEMENT 5 — GROUND LINE:
Thin horizontal black rectangle at bottom.""",

    "scales_balance": """EXACT SCENE — WORK-LIFE BALANCE: Scales with two sides:

ELEMENT 1 — BALANCE BEAM:
Thick horizontal black rectangle (50% × 4%) balanced on a vertical black rectangle pillar (6% × 20%).

ELEMENT 2 — LEFT PLATE — WORK:
Black horizontal rectangle (20% × 3%) hanging from left end. On top: black rectangle (14% × 10%) — a laptop/work symbol.

ELEMENT 3 — RIGHT PLATE — LIFE (KEY — LIME):
Bright electric lime (#DFFF00) horizontal rectangle (20% × 3%) hanging from right end. On top: lime rectangle (14% × 10%) — life/personal time.

ELEMENT 4 — TILT:
Beam tilted ~10° showing imbalance.

ELEMENT 5 — GROUND LINE:
Thin horizontal black rectangle at bottom.""",

    "rocket_launch": """EXACT SCENE — STARTUP/LAUNCH: Rocket taking off:

ELEMENT 1 — ROCKET:
Tall vertical black rectangle (8% × 30%) with black triangle on top (12% base, 10% height) — the rocket body.

ELEMENT 2 — FLAME (KEY — LIME):
Bright electric lime (#DFFF00) triangle pointing DOWN (14% base, 16% height) at the bottom of the rocket — exhaust flame.

ELEMENT 3 — LAUNCH PAD:
Thick horizontal black rectangle (30% × 6%) at the bottom.

ELEMENT 4 — SMOKE TRAIL:
2-3 small black rectangles at slight angles around the flame area.

ELEMENT 5 — GROUND LINE:
Thin horizontal black rectangle at bottom.""",

    "filter_funnel": """EXACT SCENE — SELECTION/FILTERING: Funnel filtering items:

ELEMENT 1 — FUNNEL TOP:
Wide black trapezoid (40% wide top, 10% bottom, 20% tall) — the filter.

ELEMENT 2 — INPUT ITEMS:
5-6 small black squares (4% × 4%) entering the funnel from above.

ELEMENT 3 — OUTPUT (KEY — LIME):
One bright electric lime (#DFFF00) rectangle (8% × 8%) exiting the bottom — the selected/best item.

ELEMENT 4 — REJECTED:
2-3 small black rectangles to the sides, tilted — rejected items.

ELEMENT 5 — GROUND LINE:
Thin horizontal black rectangle at bottom.""",

    "handshake_deal": """EXACT SCENE — PARTNERSHIP/DEAL: Two figures reaching toward each other:

ELEMENT 1 — PERSON LEFT:
Black human figure silhouette on the left side, arm extended (rectangle 3% × 12%) pointing RIGHT.

ELEMENT 2 — PERSON RIGHT:
Black human figure silhouette on the right side, arm extended pointing LEFT.

ELEMENT 3 — HANDSHAKE ZONE (KEY — LIME):
Bright electric lime (#DFFF00) square (10% × 10%) where the two arms meet — the deal/connection point.

ELEMENT 4 — CONNECTING LINE:
Lime horizontal rectangle (2% × 20%) connecting both figures through the center square.

ELEMENT 5 — GROUND LINE:
Thin horizontal black rectangle at bottom.""",

    "mountain_peak": """EXACT SCENE — ACHIEVEMENT/GOAL: Person at mountain peak:

ELEMENT 1 — MOUNTAIN:
Large black triangle (50% base, 40% height) — the mountain.

ELEMENT 2 — PEAK FLAG (KEY — LIME):
Bright electric lime (#DFFF00) rectangle flag (8% × 6%) on a thin vertical lime rectangle pole (2% × 10%) at the top of the mountain.

ELEMENT 3 — PERSON:
Small black human figure silhouette at the peak, next to the flag.

ELEMENT 4 — PATH:
Thin black zigzag rectangles going up the mountain — the path taken.

ELEMENT 5 — GROUND LINE:
Thin horizontal black rectangle at bottom.""",

    "magnifier_search": """EXACT SCENE — RESEARCH/ANALYSIS: Magnifying glass examining data:

ELEMENT 1 — DATA BARS (left):
4 black vertical rectangles of varying heights (8%, 14%, 20%, 26%) — data to analyze.

ELEMENT 2 — MAGNIFIER (KEY — LIME):
Bright electric lime (#DFFF00) square frame (20% × 20%) positioned over the tallest bar, with a diagonal lime rectangle handle (3% × 16%) extending to lower-right — the magnifying glass.

ELEMENT 3 — PERSON (right):
Black human figure silhouette holding the magnifier.

ELEMENT 4 — GROUND LINE:
Thin horizontal black rectangle at bottom.""",

    "door_opportunity": """EXACT SCENE — NEW OPPORTUNITY: Person opening a door:

ELEMENT 1 — WALL:
Large black rectangle (60% × 50%) — the barrier.

ELEMENT 2 — DOOR (KEY — LIME):
Bright electric lime (#DFFF00) vertical rectangle (16% × 40%) cut into the wall — the open door.

ELEMENT 3 — LIGHT RAYS:
3 lime triangles/rectangles emanating from the door opening — opportunity/light.

ELEMENT 4 — PERSON:
Black human figure silhouette stepping through the door.

ELEMENT 5 — GROUND LINE:
Thin horizontal black rectangle at bottom.""",

    "speech_debate": """EXACT SCENE — COMMUNICATION/DEBATE: Two people with speech bubbles:

ELEMENT 1 — PERSON LEFT:
Black human figure silhouette on the left.

ELEMENT 2 — SPEECH BUBBLE LEFT:
Black rectangle (16% × 10%) with small triangle pointer on bottom — left person's speech.

ELEMENT 3 — PERSON RIGHT:
Black human figure silhouette on the right.

ELEMENT 4 — SPEECH BUBBLE RIGHT (KEY — LIME):
Bright electric lime (#DFFF00) rectangle (16% × 10%) with small triangle pointer on bottom — the winning/key argument.

ELEMENT 5 — GROUND LINE:
Thin horizontal black rectangle at bottom.""",
}

# Topic keyword → scene variants mapping
TOPIC_MAPPING = {
    "карьер": ["career_stairs", "chart_growth", "bridge_gap", "mountain_peak"],
    "рост": ["career_stairs", "chart_growth", "rocket_launch"],
    "зарплат": ["lever_lift", "chart_growth", "bridge_gap", "scales_balance"],
    "резюме": ["document_transform", "standout_grid", "filter_funnel"],
    "cv": ["document_transform", "standout_grid", "filter_funnel"],
    "собеседов": ["standout_grid", "target_hit", "speech_debate"],
    "интервью": ["standout_grid", "target_hit", "speech_debate"],
    "лидер": ["career_stairs", "standout_grid", "mountain_peak"],
    "менедж": ["puzzle_system", "lever_lift", "network_nodes"],
    "ai": ["puzzle_system", "chart_growth", "target_hit", "rocket_launch"],
    "ии": ["puzzle_system", "chart_growth", "rocket_launch"],
    "агент": ["puzzle_system", "lever_lift", "network_nodes"],
    "автоматиз": ["puzzle_system", "lever_lift", "filter_funnel"],
    "linkedin": ["document_transform", "standout_grid", "megaphone_voice"],
    "контент": ["document_transform", "target_hit", "megaphone_voice"],
    "пост": ["document_transform", "target_hit", "megaphone_voice"],
    "бренд": ["standout_grid", "target_hit", "megaphone_voice"],
    "стратег": ["chart_growth", "lever_lift", "bridge_gap", "mountain_peak"],
    "бизнес": ["chart_growth", "lever_lift", "rocket_launch"],
    "команд": ["puzzle_system", "standout_grid", "network_nodes"],
    "навык": ["career_stairs", "bridge_gap", "mountain_peak"],
    "skill": ["career_stairs", "bridge_gap", "mountain_peak"],
    "remote": ["bridge_gap", "puzzle_system", "network_nodes"],
    "удалён": ["bridge_gap", "puzzle_system", "network_nodes"],
    "нетворк": ["network_nodes", "handshake_deal"],
    "партнёр": ["handshake_deal", "network_nodes"],
    "сотрудн": ["handshake_deal", "network_nodes", "puzzle_system"],
    "безопас": ["shield_protect", "filter_funnel"],
    "защит": ["shield_protect", "filter_funnel"],
    "запуск": ["rocket_launch", "door_opportunity"],
    "старт": ["rocket_launch", "door_opportunity"],
    "startup": ["rocket_launch", "door_opportunity"],
    "время": ["clock_deadline", "scales_balance"],
    "дедлайн": ["clock_deadline", "lever_lift"],
    "баланс": ["scales_balance", "bridge_gap"],
    "burnout": ["scales_balance", "shield_protect"],
    "выгоран": ["scales_balance", "shield_protect"],
    "фильтр": ["filter_funnel", "magnifier_search"],
    "отбор": ["filter_funnel", "standout_grid"],
    "найм": ["filter_funnel", "standout_grid", "handshake_deal"],
    "исследов": ["magnifier_search", "chart_growth"],
    "анализ": ["magnifier_search", "chart_growth"],
    "data": ["magnifier_search", "chart_growth"],
    "возможност": ["door_opportunity", "bridge_gap"],
    "переговор": ["speech_debate", "handshake_deal", "lever_lift"],
    "коммуник": ["speech_debate", "megaphone_voice", "network_nodes"],
    "презентац": ["megaphone_voice", "target_hit"],
    "pitch": ["megaphone_voice", "target_hit", "rocket_launch"],
    "цель": ["target_hit", "mountain_peak"],
    "goal": ["target_hit", "mountain_peak"],
    "достиж": ["mountain_peak", "career_stairs", "target_hit"],
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

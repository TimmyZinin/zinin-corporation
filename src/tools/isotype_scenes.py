"""
🎨 ISOTYPE Scene Library — Shared between Ryan (Designer) and Yuki (SMM)

36 scenes, 10 categories, topic-keyword mapping.
Ported from telegram_yuki/image_gen.py for cross-agent reuse.
"""

import random

# Re-export from Yuki's image_gen (single source of truth)
from ..telegram_yuki.image_gen import SCENES, TOPIC_MAPPING, DEFAULT_SCENES


def select_scene(topic: str) -> str:
    """Select a scene key based on topic keywords."""
    topic_lower = topic.lower()
    for keyword, variants in TOPIC_MAPPING.items():
        if keyword in topic_lower:
            return random.choice(variants)
    return random.choice(DEFAULT_SCENES)


def get_scene_description(scene_key: str) -> str:
    """Get scene description by key. Returns empty string if not found."""
    return SCENES.get(scene_key, "")


def get_all_scene_keys() -> list[str]:
    """Get all available scene keys."""
    return list(SCENES.keys())


def get_categories() -> dict[str, list[str]]:
    """Get scenes organized by category prefix."""
    categories: dict[str, list[str]] = {}
    for key in SCENES:
        prefix = key.rsplit("_", 1)[0] if "_v" in key else key
        # Extract category (before _vN)
        parts = key.split("_v")
        cat = parts[0] if parts else key
        categories.setdefault(cat, []).append(key)
    return categories


def build_isotype_prompt(topic: str, post_text: str = "") -> str:
    """Build a full ISOTYPE prompt for image generation.

    Returns the complete prompt including scene, style guide, and rules.
    This is the shared version — no Yuki-specific feedback loop.
    """
    scene_key = select_scene(topic)
    scene_desc = SCENES[scene_key]

    return f"""Create a flat 2D vector illustration in the style of ISOTYPE pictograms meets Soviet Constructivist poster. Square format 1:1. Pure white background (#FFFFFF).

STYLE DIRECTION:
This is NOT abstract art. This is a PICTOGRAPHIC ILLUSTRATION where recognizable objects (people, documents, arrows, laptops, tables) are built from simple geometric shapes. Each object is a simplified silhouette assembled from 2-4 rectangles, squares, and triangles. Think: Gerd Arntz pictograms, Otto Neurath ISOTYPE charts, Soviet infographic posters. The viewer must understand WHAT the objects are within 0.5 seconds.

{scene_desc}

HOW TO BUILD PICTOGRAPHIC OBJECTS:
- A PERSON = small square head (4%) sitting on a tall rectangle body (6% × 16%) on a thin rectangle base (10% × 3%). Very simplified, like a bathroom sign figure but with all square corners.
- A DOCUMENT = vertical rectangle (18% × 24%) with 2-3 thin horizontal rectangles inside representing text lines.
- AN ARROW = triangle tip on a rectangle shaft.
- A LAPTOP = rectangle screen on thin rectangle keyboard base.
- A TABLE = horizontal rectangle on two vertical rectangle legs.
- A CHECKMARK = two thick rectangles joined at an angle forming a V-check.
- A CROSS/X = two thick rectangles crossed diagonally.
- STAIRS = 3-4 rectangles arranged in ascending step pattern.
- A WALL/BARRIER = one massive horizontal rectangle spanning most of the canvas width.
- A SPEECH BUBBLE = rectangle with a small triangle pointer on its bottom edge.
- A BAR CHART = 3-4 rectangles of increasing height standing side by side.

ALL objects are built ONLY from rectangles, squares, and triangles with SHARP 90-degree corners. No curves, no circles, no rounded corners. The figures are SCHEMATIC and GEOMETRIC but clearly RECOGNIZABLE.

COMPOSITION RULES:
- Total: 8-12 geometric shapes (forming 2-4 recognizable pictographic objects)
- Shapes fill approximately 40-50% of the canvas — DENSE and BOLD, not sparse
- ASYMMETRIC layout — visual weight shifted off-center
- Objects OVERLAP slightly or interact with each other — not floating in isolation
- Strong diagonal or directional energy — composition has a clear visual direction
- The lime (#DFFF00) element is the FOCAL POINT — the viewer's eye goes there FIRST
- Lime element(s) must occupy at least 12-15% of canvas area — IMMEDIATELY visible

COLOR PALETTE — STRICT, NO EXCEPTIONS:
- Black (#000000) — primary objects and forms
- White (#FFFFFF) — background ONLY
- Electric lime (#DFFF00) — exactly ONE key object or element. Must be BRIGHT electric yellow-green like a highlighter marker. NOT muted olive, NOT dark green, NOT yellow, NOT khaki. RGB: 223, 255, 0.

MANDATORY REQUIREMENTS:
- ALL shapes are THICK and MASSIVE — minimum dimension of any shape is 3% of canvas (for details like text lines) or 6% (for main shapes)
- Every shape has SHARP 90-degree corners — no rounded corners whatsoever
- Only rectangles, squares, triangles, parallelograms, and trapezoids allowed
- No circles, ovals, curves, or organic shapes
- Objects must be RECOGNIZABLE — a person should look like a person, a document should look like a document
- The scene tells a STORY — objects relate to each other, not just scattered randomly

STRICT PROHIBITIONS:
- NO text, letters, numbers, words, or typographic elements of any kind
- NO gradients, shadows, glows, or any lighting effects
- NO 3D rendering, perspective, depth, or volume
- NO textures, noise, grain, or patterns
- NO realistic detail — these are SIMPLIFIED PICTOGRAMS, not detailed illustrations
- NO decorative elements — every shape serves the pictographic meaning
- NO colors other than black (#000000), white (#FFFFFF), and lime (#DFFF00)
- NO thin lines or outlines — all forms are solid filled shapes
- NO facial features, fingers, or anatomical detail on human figures
- NO icons, emoji, or clip-art style imagery — these are BOLD GEOMETRIC CONSTRUCTIONS

ARTISTIC REFERENCES:
Gerd Arntz ISOTYPE pictograms — geometric human figures and symbols from simple shapes.
Otto Neurath statistical charts — pictographic data visualization with bold silhouettes.
El Lissitzky "Beat the Whites with the Red Wedge" — bold geometric symbolism, propaganda energy.
Alexander Rodchenko poster compositions — diagonal dynamics, limited palette.
Soviet-era safety and propaganda posters — simplified human figures in geometric style.

The result must look like a bold pictographic poster: instantly readable objects, powerful composition, impossible to scroll past. The viewer immediately understands what the image is about."""

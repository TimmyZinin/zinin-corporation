"""Image generation for Yuki SMM bot — ISOTYPE pictographic style via OpenRouter.

Ported from СБОРКА gemini_image.py v6.0 — full scene library + full prompt.
"""

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
# SCENE LIBRARY — ISOTYPE pictographic scenes (ported from СБОРКА v6.0)
# 36 scenes, 10 categories, 3-4 variants each
# ============================================================================

SCENES = {
    # =====================================================================
    # ЗАРПЛАТА / ПЕРЕГОВОРЫ — 4 варианта
    # =====================================================================

    "salary_v1_chart": """EXACT SCENE — SALARY NEGOTIATION: A person standing next to a rising bar chart with an upward arrow:

ELEMENT 1 — THE PERSON (left side):
A simplified human figure silhouette made of geometric shapes, positioned in the left third of the canvas. Built from: a small black square as the head (about 4% of canvas), a tall black rectangle as the body directly below (6% wide, 16% tall), and a thin black horizontal rectangle at the feet (10% wide, 3% tall) as the base. This person represents THE PROFESSIONAL who is negotiating.

ELEMENT 2 — THE BAR CHART (center-right):
Three black vertical rectangles standing side by side, each 6% wide with 2% gaps between them. Heights increase left to right: 12%, 20%, 28% of canvas. They rest on a thin horizontal black baseline rectangle (30% wide, 2% tall). This is SALARY GROWTH — each column higher than the last.

ELEMENT 3 — THE UPWARD ARROW (KEY ELEMENT — LIME):
A bold bright electric lime (#DFFF00) arrow pointing straight up, emerging from the top of the tallest bar chart column. Built from: a lime triangle pointing up (12% base, 10% height) sitting on a lime vertical rectangle shaft (6% wide, 14% tall). This arrow is the RESULT — salary going UP after negotiation. It must be the brightest, most prominent element.

ELEMENT 4 — BASELINE:
One thin horizontal black rectangle spanning the full bottom portion, grounding the composition (80% wide, 2% tall).

ELEMENT 5 — SUPPORTING CONTEXT:
One small black square (5% × 5%) positioned near the person's hand level, slightly overlapping with the first bar column — representing preparation/data the person brings to the negotiation.""",

    "salary_v2_scales": """EXACT SCENE — SALARY BALANCE: Scales weighing value vs payment:

ELEMENT 1 — BALANCE BEAM (center):
One thick horizontal black rectangle (50% × 4%) balanced on a vertical black rectangle pillar (6% × 20%). Classic scales shape.

ELEMENT 2 — LEFT PLATE — SKILLS:
One black horizontal rectangle (20% × 3%) hanging from the left end of the beam. On top: 3 small black squares (5% each) stacked — representing skills, experience, value.

ELEMENT 3 — RIGHT PLATE — PAYMENT (KEY ELEMENT — LIME):
One bright electric lime (#DFFF00) horizontal rectangle (20% × 3%) hanging from the right end, tilted DOWN (heavier). On top: one large lime rectangle (12% × 8%) — the salary package. The lime side is WINNING.

ELEMENT 4 — TILT INDICATOR:
The entire beam is tilted ~15° with the lime side DOWN — showing salary rising to match value.

ELEMENT 5 — GROUND LINE:
Thin horizontal black rectangle at the bottom grounding the composition.""",

    "salary_v3_lever": """EXACT SCENE — SALARY LEVERAGE: A person using a lever to lift heavy object:

ELEMENT 1 — THE LEVER (diagonal):
One thick black diagonal rectangle (60% × 5%) positioned from lower-left to upper-right at ~30° angle.

ELEMENT 2 — FULCRUM:
One black triangle (12% base, 10% height) under the lever, positioned at the 1/3 point from the left.

ELEMENT 3 — PERSON PUSHING (left):
One black human figure silhouette at the low end of the lever, pushing DOWN. Head (4%), body (6% × 16%), base (10% × 3%).

ELEMENT 4 — RISING OBJECT (KEY ELEMENT — LIME, right):
One large bright electric lime (#DFFF00) rectangle (18% × 14%) at the high end of the lever, being LIFTED UP. This represents the salary being raised through leverage.

ELEMENT 5 — EFFORT INDICATOR:
One small black arrow pointing down near the person — the small effort applied.

ELEMENT 6 — RESULT ARROW:
One lime arrow pointing UP near the rising object — the big result achieved.""",

    "salary_v4_gap": """EXACT SCENE — BRIDGING THE SALARY GAP: A person crossing a gap between two levels:

ELEMENT 1 — LOWER PLATFORM (left):
One black horizontal rectangle (30% × 8%) positioned in the lower-left — the current salary level.

ELEMENT 2 — HIGHER PLATFORM (right):
One black horizontal rectangle (30% × 8%) positioned in the upper-right, ~20% higher — the target salary.

ELEMENT 3 — THE GAP:
White space between platforms (15% wide) — the negotiation challenge.

ELEMENT 4 — BRIDGE (KEY ELEMENT — LIME):
One bright electric lime (#DFFF00) diagonal rectangle (25% × 4%) spanning the gap from lower to higher platform. This is the NEGOTIATION — the bridge to higher pay.

ELEMENT 5 — PERSON CROSSING:
One black human figure silhouette standing on the lime bridge, mid-crossing. Head (4%), body (6% × 16%), base (10% × 3%).

ELEMENT 6 — GROUND LINE:
Thin horizontal black rectangle at the very bottom.""",

    # =====================================================================
    # РЕЗЮМЕ — 4 варианта
    # =====================================================================

    "resume_v1_errors": """EXACT SCENE — RESUME WITH ERRORS: A document covered with X-marks showing mistakes:

ELEMENT 1 — THE RESUME DOCUMENT (KEY ELEMENT — LIME):
One large vertical rectangle in bright electric lime (#DFFF00), positioned center-left of the canvas. Size: 22% wide, 30% tall. Inside it: 3 thin horizontal white rectangles (14% × 2% each) evenly spaced — representing text lines on the resume. This is the RESUME — the central focus, glowing lime because it demands attention and fixing.

ELEMENT 2 — ERROR CROSS #1 (large):
Two thick black rectangles crossed diagonally (each 5% × 20%), forming an X-shape. Positioned overlapping the upper-right portion of the resume document. Tilted at 45° and 135°. This is ERROR #1 — a major mistake.

ELEMENT 3 — ERROR CROSS #2 (medium):
Two thick black rectangles crossed (each 4% × 14%), forming a smaller X. Positioned overlapping the lower-left portion of the resume. ERROR #2.

ELEMENT 4 — ERROR CROSS #3 (small):
Two thick black rectangles crossed (each 3% × 10%), forming a small X. Positioned to the right of the resume, slightly overlapping its edge. ERROR #3.

ELEMENT 5 — DEBRIS / CONSEQUENCES:
3-4 small black rectangular fragments (3-5% each) scattered around the resume and crosses, at various slight angles — representing shattered chances, lost opportunities.

ELEMENT 6 — GROUND LINE:
Thin horizontal black rectangle at the bottom (70% × 2%) grounding the composition.""",

    "resume_v2_improve": """EXACT SCENE — RESUME IMPROVEMENT: Document transforming with upward arrow:

ELEMENT 1 — OLD RESUME (left, faded):
One vertical black rectangle (18% × 24%) on the left side — the weak resume, static.

ELEMENT 2 — TRANSFORMATION ARROW (KEY ELEMENT — LIME):
One large bright electric lime (#DFFF00) horizontal arrow pointing RIGHT, connecting the two documents. Triangle tip (10% × 8%) + rectangle shaft (20% × 4%). This is the IMPROVEMENT PROCESS.

ELEMENT 3 — NEW RESUME (right):
One vertical black rectangle (18% × 24%) on the right side with 3 thin white horizontal lines inside — the improved resume.

ELEMENT 4 — CHECKMARK:
One lime checkmark (small, 8% × 8%) above the new resume — validation of improvement.

ELEMENT 5 — PERSON:
One black human figure silhouette below, centered, looking up at the transformation. Head (4%), body (6% × 16%), base (10% × 3%).

ELEMENT 6 — GROUND LINE:
Thin horizontal black rectangle at the bottom.""",

    "resume_v3_filter": """EXACT SCENE — RESUME PASSING THROUGH: Document successfully going through a barrier:

ELEMENT 1 — BARRIER WALL (center):
One thick vertical black rectangle (8% × 60%) positioned in the center — the FILTER/CHECKPOINT.

ELEMENT 2 — REJECTED RESUMES (left):
3-4 small black rectangles (documents, 10% × 14% each) clustered on the left side of the wall — failed attempts, blocked.

ELEMENT 3 — SUCCESSFUL RESUME (KEY ELEMENT — LIME):
One bright electric lime (#DFFF00) vertical rectangle (14% × 20%) positioned to the RIGHT of the wall — it PASSED THROUGH.

ELEMENT 4 — PASSAGE ARROW:
One thin lime horizontal rectangle (15% × 2%) going THROUGH the wall — the path of success.

ELEMENT 5 — CHECKMARK:
One lime checkmark (10% × 10%) above the successful resume — approved.

ELEMENT 6 — GROUND LINE:
Thin horizontal black rectangle at the bottom.""",

    "resume_v4_stack": """EXACT SCENE — STANDING OUT FROM STACK: One resume highlighted among many:

ELEMENT 1 — STACK OF RESUMES:
5-6 vertical black rectangles (14% × 20% each) overlapping slightly, arranged in a cascading stack from bottom-left to upper-right. Generic resumes, all the same.

ELEMENT 2 — HIGHLIGHTED RESUME (KEY ELEMENT — LIME):
One bright electric lime (#DFFF00) vertical rectangle (16% × 22%) positioned slightly above and to the side of the stack — PULLED OUT, separate, noticed. This is YOUR resume.

ELEMENT 3 — SPOTLIGHT TRIANGLE:
One lime triangle (15% base, 12% height) above the highlighted resume, pointing DOWN — drawing attention.

ELEMENT 4 — HAND/POINTER:
One black geometric hand shape (rectangle 4% × 12% + smaller rectangles as fingers) reaching toward the lime resume — the recruiter picking it up.

ELEMENT 5 — GROUND LINE:
Thin horizontal black rectangle at the bottom.""",

    # =====================================================================
    # ВЫДЕЛИТЬСЯ / КАНДИДАТЫ — 4 варианта
    # =====================================================================

    "standout_v1_row": """EXACT SCENE — ONE STANDS OUT FROM THE CROWD: A row of identical figures with one highlighted:

ELEMENT 1 — CROWD ROW (5 identical figures):
Five simplified human figure silhouettes standing in a horizontal row across the lower half of the canvas. Each figure is built from: a small black square head (3.5%), a tall black rectangle body (5% × 14%), and a thin black rectangle base (8% × 2.5%). All figures are identical, evenly spaced with 4% gaps between them. They represent THE MASS — identical, interchangeable.

ELEMENT 2 — THE STANDOUT FIGURE (KEY ELEMENT — LIME):
The third figure from the left is completely in bright electric lime (#DFFF00) instead of black. Same construction: lime square head, lime rectangle body, lime rectangle base. BUT this figure is shifted UPWARD by about 8% compared to the row — it literally RISES ABOVE the crowd. This is YOU — the one who stands out.

ELEMENT 3 — INDICATOR TRIANGLE:
One small lime triangle (6% base, 5% height) pointing DOWN, positioned directly above the lime figure's head. This draws the eye: "THIS ONE."

ELEMENT 4 — GROUND LINE:
One horizontal black rectangle (85% wide, 2.5% tall) at the bottom of the canvas, under the feet of the crowd row. The ground — the baseline everyone starts from.

ELEMENT 5 — WEIGHT/CONTEXT BLOCK:
One large black rectangle (25% × 8%) in the upper-right corner — creates compositional balance and adds visual weight/seriousness.""",

    "standout_v2_grid": """EXACT SCENE — DIFFERENT IN THE GRID: One figure rotated in a 3x3 grid:

ELEMENT 1 — GRID OF 8 BLACK FIGURES:
8 simplified human figure silhouettes arranged in a 3x3 grid pattern. Each: small black square head (3%), tall black rectangle body (4% × 12%), thin base (6% × 2%). All facing the same direction, evenly spaced.

ELEMENT 2 — CENTER FIGURE (KEY ELEMENT — LIME):
The CENTER position of the grid is a bright electric lime (#DFFF00) figure, same construction BUT ROTATED 45° — tilted, different orientation. This is YOU — thinking differently, acting differently.

ELEMENT 3 — EMPHASIS SQUARE:
One thin lime rectangle frame (20% × 20%) around the center figure — highlighting the difference.

ELEMENT 4 — CONNECTING LINES:
Thin black lines connecting the 8 outer figures — they're connected, conforming. The lime figure has NO connections — independent.

ELEMENT 5 — GROUND LINE:
Thin horizontal black rectangle at the bottom.""",

    "standout_v3_race": """EXACT SCENE — LEADING THE RACE: One figure ahead of the pack:

ELEMENT 1 — TRAILING FIGURES (4 figures):
4 black human figure silhouettes arranged in a diagonal line from lower-left to center, suggesting movement/racing. Each: head (3.5%), body (5% × 14%), base (8% × 2.5%). They're BEHIND, catching up.

ELEMENT 2 — LEADING FIGURE (KEY ELEMENT — LIME):
One bright electric lime (#DFFF00) figure positioned in the upper-right, AHEAD of the pack. Same construction but clearly in front. This is YOU — already ahead.

ELEMENT 3 — FINISH LINE:
One vertical black rectangle (3% × 40%) on the far right — the goal.

ELEMENT 4 — MOTION LINES:
2-3 thin horizontal black rectangles (20% × 1% each) behind the figures — motion blur, speed.

ELEMENT 5 — FLAG:
One small lime triangle (6% × 8%) attached to a thin lime rectangle pole (2% × 12%) at the finish line — victory marker.

ELEMENT 6 — GROUND LINE:
Thin horizontal black rectangle at the bottom.""",

    "standout_v4_spotlight": """EXACT SCENE — SPOTLIGHT ON ONE: Light beam highlighting one figure in crowd:

ELEMENT 1 — CROWD (6-7 figures):
6-7 black human figure silhouettes scattered in the lower half of canvas. Each: head (3%), body (5% × 12%), base (7% × 2%). Anonymous crowd.

ELEMENT 2 — SPOTLIGHT BEAM (KEY ELEMENT — LIME):
One large bright electric lime (#DFFF00) triangle (30% base at top, narrowing to 15% at bottom) pointing DOWN from the top of canvas — a spotlight beam.

ELEMENT 3 — ILLUMINATED FIGURE:
One black human figure standing IN the spotlight beam, at its center. This figure is slightly larger (head 4%, body 6% × 16%) — the one being SEEN.

ELEMENT 4 — LIGHT SOURCE:
One lime horizontal rectangle (20% × 4%) at the very top — the spotlight fixture.

ELEMENT 5 — SHADOW CONTRAST:
The figures outside the spotlight are smaller and positioned lower — less visible, less important.

ELEMENT 6 — GROUND LINE:
Thin horizontal black rectangle at the bottom.""",

    # =====================================================================
    # ATS / ФИЛЬТРЫ — 3 варианта
    # =====================================================================

    "ats_v1_wall": """EXACT SCENE — PASSING THROUGH ATS FILTER: A document going through a wall barrier to a checkmark:

ELEMENT 1 — THE RESUME DOCUMENT (left):
One vertical black rectangle (18% × 24%) on the left side — the resume being sent.

ELEMENT 2 — THE ATS WALL/BARRIER (center):
One massive horizontal black rectangle (70% × 12%) positioned vertically in the center of the canvas — this is the ATS FILTER, the barrier that blocks most resumes.

ELEMENT 3 — THE CHECKMARK (KEY ELEMENT — LIME, right):
One bright electric lime (#DFFF00) checkmark on the right side of the wall. Built from: a short thick rectangle tilted ~60° (4% × 10%) joined to a longer thick rectangle tilted ~30° (4% × 18%) forming a V-check shape. This is SUCCESS — passing through the filter.

ELEMENT 4 — BLOCKED RESUMES:
2-3 small black rectangles (documents) "stuck" against the left side of the wall — the filtered-out candidates.

ELEMENT 5 — PASSAGE LINE:
One thin lime horizontal rectangle (25% × 2%) passing THROUGH the wall from the left document to the right checkmark — the path of the successful resume.

ELEMENT 6 — GROUND LINE:
Thin horizontal black rectangle at the bottom grounding the composition.""",

    "ats_v2_funnel": """EXACT SCENE — FUNNEL FILTERING: Many resumes entering, few passing through:

ELEMENT 1 — FUNNEL SHAPE (center):
Two diagonal black rectangles (each 6% × 35%) forming a V-shape / funnel, wide at top, narrow at bottom.

ELEMENT 2 — INCOMING RESUMES (top):
5-6 small black rectangles (8% × 12% each) clustered above the funnel opening — many applications.

ELEMENT 3 — BLOCKED RESUMES:
3-4 small black rectangles stuck on the sides of the funnel, at various angles — filtered out.

ELEMENT 4 — PASSING RESUME (KEY ELEMENT — LIME):
One bright electric lime (#DFFF00) rectangle (10% × 14%) at the bottom of the funnel, emerging below — the ONE that passed through.

ELEMENT 5 — CHECKMARK:
One lime checkmark (8% × 8%) below the passing resume — approved.

ELEMENT 6 — GROUND LINE:
Thin horizontal black rectangle at the bottom.""",

    "ats_v3_scanner": """EXACT SCENE — DOCUMENT SCANNING: Resume passing through scanner beam:

ELEMENT 1 — SCANNER FRAME:
Two vertical black rectangles (5% × 50% each) on left and right sides — the scanner pillars.

ELEMENT 2 — SCAN BEAM (KEY ELEMENT — LIME):
One horizontal bright electric lime (#DFFF00) rectangle (70% × 3%) positioned between the pillars — the scanning light.

ELEMENT 3 — RESUME PASSING:
One black vertical rectangle (16% × 22%) positioned in the center, partially overlapping the lime beam — being scanned.

ELEMENT 4 — CHECKMARK RESULT:
One lime checkmark (10% × 10%) to the right of the scanner — approved result.

ELEMENT 5 — REJECTED PILE:
2 small black rectangles with X marks on them, positioned in the lower-left corner — rejected applications.

ELEMENT 6 — GROUND LINE:
Thin horizontal black rectangle at the bottom.""",

    # =====================================================================
    # ИНТЕРВЬЮ / СОБЕСЕДОВАНИЕ — 3 варианта
    # =====================================================================

    "interview_v1_table": """EXACT SCENE — INTERVIEW PREPARATION: Two figures at a table with speech bubbles:

ELEMENT 1 — CANDIDATE FIGURE (left):
A simplified human figure silhouette on the left side. Built from: small black square head (4%), tall black rectangle body (6% × 16%), thin black rectangle base (10% × 3%). The candidate.

ELEMENT 2 — INTERVIEWER FIGURE (right):
A slightly larger human figure silhouette on the right side (head 5%, body 7% × 18%, base 12% × 3%). The interviewer — slightly larger to show authority.

ELEMENT 3 — TABLE (center):
One horizontal black rectangle (30% × 4%) with two vertical black rectangles as legs (4% × 10% each) at the ends. The negotiation table between them.

ELEMENT 4 — CANDIDATE'S SPEECH BUBBLE (KEY ELEMENT — LIME):
One bright electric lime (#DFFF00) rectangle (16% × 10%) above the candidate with a small lime triangle (4% × 4%) pointing down from its bottom edge. This is the PREPARED ANSWER — confident, glowing.

ELEMENT 5 — INTERVIEWER'S SPEECH BUBBLE:
One small black rectangle (12% × 8%) above the interviewer with a small black triangle pointing down. The question.

ELEMENT 6 — GROUND LINE:
Thin horizontal black rectangle at the bottom.""",

    "interview_v2_questions": """EXACT SCENE — ANSWERING QUESTIONS: Person facing multiple question blocks:

ELEMENT 1 — CANDIDATE FIGURE (left):
One black human figure silhouette on the left side. Head (4%), body (6% × 16%), base (10% × 3%).

ELEMENT 2 — QUESTION BLOCKS (right, 4 blocks):
4 black rectangles (12% × 8% each) arranged in a 2x2 grid on the right — questions coming at the candidate.

ELEMENT 3 — ANSWER ARROW (KEY ELEMENT — LIME):
One bright electric lime (#DFFF00) arrow pointing from the candidate toward the questions. Triangle tip (8% × 6%) + shaft (15% × 3%). The PREPARED RESPONSE.

ELEMENT 4 — CHECKMARKS:
2 small lime checkmarks on 2 of the question blocks — already answered successfully.

ELEMENT 5 — REMAINING BLOCKS:
2 question blocks still black — yet to be answered.

ELEMENT 6 — GROUND LINE:
Thin horizontal black rectangle at the bottom.""",

    "interview_v3_handshake": """EXACT SCENE — SUCCESSFUL INTERVIEW: Two figures shaking hands:

ELEMENT 1 — CANDIDATE FIGURE (left):
One black human figure silhouette on the left. Head (4%), body (6% × 16%), base (10% × 3%).

ELEMENT 2 — EMPLOYER FIGURE (right):
One black human figure silhouette on the right, slightly larger. Head (5%), body (7% × 18%), base (12% × 3%).

ELEMENT 3 — HANDSHAKE (KEY ELEMENT — LIME, center):
Two overlapping bright electric lime (#DFFF00) rectangles (8% × 4% each) at an angle, between the figures — the HANDSHAKE, the agreement.

ELEMENT 4 — CHECKMARK ABOVE:
One lime checkmark (10% × 10%) above the handshake — deal closed.

ELEMENT 5 — TABLE (background):
One horizontal black rectangle (25% × 3%) behind the figures — the meeting table.

ELEMENT 6 — GROUND LINE:
Thin horizontal black rectangle at the bottom.""",

    # =====================================================================
    # ИИ / АВТОМАТИЗАЦИЯ — 3 варианта
    # =====================================================================

    "ai_v1_pressure": """EXACT SCENE — AI PRESSURE ON WORKFORCE: A laptop looming over crowd of workers:

ELEMENT 1 — THE LAPTOP (KEY ELEMENT — LIME, top):
One large bright electric lime (#DFFF00) construction representing a laptop. Screen: rectangle (24% × 14%), Base/keyboard: thin rectangle below (28% × 4%). Positioned in the upper portion of canvas, DOMINATING.

ELEMENT 2 — PRESSURE BAR:
One massive horizontal black rectangle (75% × 10%) below the laptop — the PRESSURE/DIVISION between AI and workers.

ELEMENT 3 — WORKER CROWD (bottom):
4-5 simplified human figures in black standing in a row below the pressure bar. Each: small square head (3%), tall rectangle body (5% × 12%), thin base (7% × 2%). They represent workers under pressure.

ELEMENT 4 — ADAPTED WORKER:
One black human figure standing ON TOP of (or next to) the laptop — the one who adapted and works WITH AI, not against it.

ELEMENT 5 — GROUND LINE:
Thin horizontal black rectangle at the very bottom.""",

    "ai_v2_collaboration": """EXACT SCENE — HUMAN + AI COLLABORATION: Person and machine working together:

ELEMENT 1 — HUMAN FIGURE (left):
One black human figure silhouette on the left side. Head (4%), body (6% × 16%), base (10% × 3%).

ELEMENT 2 — AI/ROBOT SHAPE (right):
One geometric robot shape: square head (6% × 6%), rectangular body (8% × 14%), all black. Simple, schematic.

ELEMENT 3 — BRIDGE CONNECTION (KEY ELEMENT — LIME):
One bright electric lime (#DFFF00) horizontal rectangle (25% × 4%) connecting human and robot at chest level — COLLABORATION, working together.

ELEMENT 4 — OUTPUT ARROW:
One lime arrow pointing upward from above the connection — combined output, enhanced results.

ELEMENT 5 — CHECKMARKS:
Two small lime checkmarks, one near each figure — both contributing.

ELEMENT 6 — GROUND LINE:
Thin horizontal black rectangle at the bottom.""",

    "ai_v3_tool": """EXACT SCENE — AI AS A TOOL: Person controlling/using AI device:

ELEMENT 1 — PERSON (left, larger):
One large black human figure silhouette. Head (5%), body (7% × 20%), base (12% × 3%). Positioned prominently — IN CONTROL.

ELEMENT 2 — AI DEVICE (KEY ELEMENT — LIME, right):
One bright electric lime (#DFFF00) laptop/screen shape. Screen (18% × 12%), base (22% × 3%). Positioned lower and to the right — a TOOL being used.

ELEMENT 3 — CONTROL LINES:
2-3 thin black rectangles (20% × 1% each) connecting the person's hand area to the device — control, direction.

ELEMENT 4 — OUTPUT:
One lime rectangle (10% × 6%) emerging from the device toward the right — the result produced.

ELEMENT 5 — GROUND LINE:
Thin horizontal black rectangle at the bottom.""",

    # =====================================================================
    # КАРЬЕРА / РОСТ — 3 варианта
    # =====================================================================

    "career_v1_stairs": """EXACT SCENE — CAREER LADDER: A person climbing stairs with arrow pointing up:

ELEMENT 1 — STAIRCASE (4-5 steps):
4-5 black horizontal rectangles arranged as ascending stairs from lower-left to upper-right. Each step: 12% × 6%, staggered rightward and upward by ~8%. Forms a clear staircase pattern.

ELEMENT 2 — PERSON ON LOWER STEP:
One black human figure silhouette standing on the second step from bottom. Head (3.5%), body (5% × 14%), base (8% × 2.5%).

ELEMENT 3 — TOP STEP (KEY ELEMENT — LIME):
The TOPMOST step is bright electric lime (#DFFF00) instead of black — the GOAL, the next level, the promotion.

ELEMENT 4 — UPWARD ARROW:
One black arrow (triangle tip + rectangle shaft) pointing up-right above the lime step — continued growth beyond.

ELEMENT 5 — GROUND LINE:
Thin horizontal black rectangle at the bottom, below the first step.""",

    "career_v2_chart": """EXACT SCENE — CAREER GROWTH CHART: Rising bar chart with person:

ELEMENT 1 — BAR CHART (4 bars):
4 vertical black rectangles of increasing height (10%, 16%, 24%, 32% tall), each 8% wide, evenly spaced. Career progression.

ELEMENT 2 — HIGHEST BAR (KEY ELEMENT — LIME):
The tallest (rightmost) bar is bright electric lime (#DFFF00) — the current achievement / next goal.

ELEMENT 3 — PERSON:
One black human figure silhouette standing at the base of the lime bar, looking up. Head (4%), body (6% × 16%), base (10% × 3%).

ELEMENT 4 — TREND LINE:
One diagonal lime rectangle (40% × 2%) connecting the tops of the bars — upward trend.

ELEMENT 5 — BASELINE:
Thin horizontal black rectangle under the bars — the x-axis.

ELEMENT 6 — GROUND LINE:
Thin horizontal black rectangle at the bottom.""",

    "career_v3_door": """EXACT SCENE — OPPORTUNITY DOOR: Person approaching an open door:

ELEMENT 1 — CLOSED DOORS (2, left):
2 vertical black rectangles (14% × 28% each) side by side on the left — closed opportunities.

ELEMENT 2 — OPEN DOOR (KEY ELEMENT — LIME, right):
One bright electric lime (#DFFF00) vertical rectangle (16% × 30%) with a smaller black rectangle removed from one side — the open door, the opportunity.

ELEMENT 3 — PERSON:
One black human figure silhouette walking toward the open door. Head (4%), body (6% × 16%), base (10% × 3%). Motion implied by lean.

ELEMENT 4 — LIGHT RAYS:
2-3 thin lime rectangles (15% × 1% each) emanating from the open door — opportunity light.

ELEMENT 5 — GROUND LINE:
Thin horizontal black rectangle at the bottom.""",

    # =====================================================================
    # СТРЕСС / ДАВЛЕНИЕ — 3 варианта
    # =====================================================================

    "stress_v1_pressure": """EXACT SCENE — PRESSURE AND RESILIENCE: A figure holding firm under crushing weight:

ELEMENT 1 — TOP PRESSURE MASS:
One very large black rectangle (80% × 25%) at the top of canvas, pressing DOWN. Overwhelming external pressure.

ELEMENT 2 — SIDE PRESSURE:
One tall black rectangle (18% × 40%) on the right side, pressing from the side.

ELEMENT 3 — THE RESILIENT FIGURE (KEY ELEMENT — LIME):
One bright electric lime (#DFFF00) human figure silhouette standing in the center-left, between the crushing masses. Built with head (4%), body (6% × 20%), base (10% × 3%). This figure HOLDS FIRM — it's not crushed.

ELEMENT 4 — COLLAPSED FIGURES:
2 small black shapes (tilted rectangles) on the left side, as if fallen/collapsed — those who couldn't handle the pressure.

ELEMENT 5 — BREATHING SPACE:
The white space around the lime figure is important — the SPACE it maintains under pressure.

ELEMENT 6 — GROUND LINE:
Thin horizontal black rectangle at the bottom.""",

    "stress_v2_clock": """EXACT SCENE — TIME PRESSURE: Person racing against clock:

ELEMENT 1 — LARGE CLOCK (right):
One large black square (30% × 30%) with two black rectangle hands inside at different angles — a clock face.

ELEMENT 2 — PERSON (left):
One black human figure silhouette on the left, leaning forward as if running. Head (4%), body (6% × 16%), base (10% × 3%).

ELEMENT 3 — DEADLINE HAND (KEY ELEMENT — LIME):
One bright electric lime (#DFFF00) rectangle (3% × 14%) as one of the clock hands — the deadline approaching.

ELEMENT 4 — MOTION LINES:
3 thin black rectangles (12% × 1% each) behind the person — speed, urgency.

ELEMENT 5 — TASK BLOCKS:
2-3 small black squares (6% each) between the person and clock — things to complete.

ELEMENT 6 — GROUND LINE:
Thin horizontal black rectangle at the bottom.""",

    "stress_v3_walls": """EXACT SCENE — CLOSING WALLS: Figure standing firm as walls approach:

ELEMENT 1 — LEFT WALL:
One tall black rectangle (15% × 60%) on the left side, angled slightly inward.

ELEMENT 2 — RIGHT WALL:
One tall black rectangle (15% × 60%) on the right side, angled slightly inward. Walls are CLOSING IN.

ELEMENT 3 — CENTRAL FIGURE (KEY ELEMENT — LIME):
One bright electric lime (#DFFF00) human figure silhouette standing firmly in the center. Head (4%), body (6% × 18%), base (10% × 3%). NOT CRUSHED, standing strong.

ELEMENT 4 — PRESSURE ARROWS:
Two black triangles (8% each) pointing inward from each wall — directional pressure.

ELEMENT 5 — SAFE SPACE:
The white space around the lime figure — the zone they maintain.

ELEMENT 6 — GROUND LINE:
Thin horizontal black rectangle at the bottom.""",

    # =====================================================================
    # ВЫБОР / ОФФЕРЫ — 3 варианта
    # =====================================================================

    "offers_v1_compare": """EXACT SCENE — COMPARING TWO OPTIONS: Two documents with one marked as chosen:

ELEMENT 1 — DOCUMENT 1 (left):
One vertical black rectangle (18% × 24%) on the left — OFFER 1.

ELEMENT 2 — DOCUMENT 2 (right):
One vertical black rectangle (18% × 24%) on the right — OFFER 2.

ELEMENT 3 — CHECKMARK ON CHOSEN (KEY ELEMENT — LIME):
One bright electric lime (#DFFF00) checkmark overlapping Document 2 (or 1). Built from two thick rectangles forming a V-check (short leg 4% × 8%, long leg 4% × 14%). This is THE CHOICE MADE.

ELEMENT 4 — DIVIDER:
One thin vertical lime rectangle (2% × 20%) between the two documents — the CRITERION for decision.

ELEMENT 5 — CONTEXT BLOCKS:
Small black squares (4% each) near each document representing factors/considerations.

ELEMENT 6 — GROUND LINE:
Thin horizontal black rectangle at the bottom.""",

    "offers_v2_scales": """EXACT SCENE — WEIGHING OPTIONS: Balance scales comparing offers:

ELEMENT 1 — SCALE BEAM:
One horizontal black rectangle (50% × 3%) balanced on a vertical black rectangle (5% × 20%). Classic scales.

ELEMENT 2 — LEFT PLATE + OFFER:
One black rectangle plate (18% × 3%) hanging from left end. On top: vertical black rectangle (12% × 16%) — Offer A.

ELEMENT 3 — RIGHT PLATE + OFFER (KEY ELEMENT — LIME):
One lime rectangle plate (18% × 3%) hanging from right end, LOWER (heavier/better). On top: bright electric lime (#DFFF00) vertical rectangle (12% × 16%) — Offer B, the winner.

ELEMENT 4 — TILT:
The beam is tilted ~15° with lime side down — clear winner.

ELEMENT 5 — PERSON:
One small black human figure below, looking up at the scales. Head (3%), body (5% × 12%), base (8% × 2%).

ELEMENT 6 — GROUND LINE:
Thin horizontal black rectangle at the bottom.""",

    "offers_v3_paths": """EXACT SCENE — CHOOSING A PATH: Person at fork with one highlighted path:

ELEMENT 1 — STARTING POINT:
One black human figure silhouette at the bottom center. Head (4%), body (6% × 16%), base (10% × 3%).

ELEMENT 2 — LEFT PATH:
One diagonal black rectangle (5% × 35%) going from center up to upper-left — Option A.

ELEMENT 3 — RIGHT PATH (KEY ELEMENT — LIME):
One diagonal bright electric lime (#DFFF00) rectangle (5% × 35%) going from center up to upper-right — Option B, the chosen path.

ELEMENT 4 — DESTINATION MARKERS:
Two small squares at the end of each path — one black (left), one lime (right).

ELEMENT 5 — FOOTPRINTS:
2-3 small lime rectangles (3% × 2% each) on the lime path — steps already taken toward the choice.

ELEMENT 6 — GROUND LINE:
Thin horizontal black rectangle at the bottom.""",

    # =====================================================================
    # СИСТЕМА / СБОРКА — 3 варианта
    # =====================================================================

    "system_v1_chaos": """EXACT SCENE — FROM CHAOS TO SYSTEM: Scattered figures becoming organized:

ELEMENT 1-3 — SCATTERED FIGURES (left):
3 black human figure silhouettes scattered chaotically in the lower-left quadrant, at random angles. Each: head (3%), body (5% × 12%), base (7% × 2%). CHAOS — unorganized efforts.

ELEMENT 4-6 — ORGANIZED FIGURES (right):
3 black human figure silhouettes standing in a neat row in the right portion, evenly spaced, all upright. ORDER — system, structure.

ELEMENT 7 — THE CONNECTOR (KEY ELEMENT — LIME):
One bright electric lime (#DFFF00) diagonal rectangle (12% × 4%) positioned between the scattered and organized groups, visually LINKING them. This is THE METHOD — the system that transforms chaos into structure.

ELEMENT 8 — DIRECTION ARROW:
One small black triangle pointing from chaos toward order.

ELEMENT 9 — PLATFORM:
One horizontal black rectangle under the organized group — the FOUNDATION they stand on.""",

    "system_v2_puzzle": """EXACT SCENE — PUZZLE COMING TOGETHER: Pieces assembling into whole:

ELEMENT 1 — SCATTERED PIECES (left):
4 black geometric shapes (various rectangles and squares, 8-12% each) scattered in the left portion — disconnected pieces.

ELEMENT 2 — ASSEMBLED STRUCTURE (right):
4 black geometric shapes fitted together into a unified square/rectangle pattern — organized whole.

ELEMENT 3 — CONNECTING PIECE (KEY ELEMENT — LIME):
One bright electric lime (#DFFF00) rectangle (10% × 8%) positioned as the FINAL piece clicking into place in the assembled structure.

ELEMENT 4 — MOTION ARROW:
One lime arrow from scattered to assembled — the transformation direction.

ELEMENT 5 — PERSON:
One small black human figure silhouette observing the assembly. Head (3%), body (5% × 12%), base (7% × 2%).

ELEMENT 6 — GROUND LINE:
Thin horizontal black rectangle at the bottom.""",

    "system_v3_network": """EXACT SCENE — CONNECTED NETWORK: Nodes linked together with central hub:

ELEMENT 1 — OUTER NODES (6 nodes):
6 black squares (6% × 6% each) arranged in a rough hexagonal pattern around the edges.

ELEMENT 2 — CENTER HUB (KEY ELEMENT — LIME):
One large bright electric lime (#DFFF00) square (12% × 12%) in the center — the central system, the core.

ELEMENT 3 — CONNECTION LINES:
6 thin lime rectangles (2% × variable length) connecting each outer node to the center hub — the network, the structure.

ELEMENT 4 — PERSON:
One black human figure silhouette positioned near one of the outer nodes, connected to the system. Head (3%), body (5% × 12%), base (7% × 2%).

ELEMENT 5 — GROUND LINE:
Thin horizontal black rectangle at the bottom.""",

    # =====================================================================
    # РЫНОК ТРУДА / ТРЕНДЫ — 3 варианта
    # =====================================================================

    "market_v1_wave": """EXACT SCENE — MARKET WAVE: Person surfing on trend wave:

ELEMENT 1 — WAVE SHAPE:
One large curved diagonal made of 3-4 overlapping black rectangles creating a wave pattern from lower-left to upper-right.

ELEMENT 2 — PERSON SURFING (positioned on wave):
One black human figure silhouette standing ON TOP of the wave. Head (4%), body (6% × 16%), base (10% × 3%).

ELEMENT 3 — SURFBOARD (KEY ELEMENT — LIME):
One bright electric lime (#DFFF00) horizontal rectangle (16% × 3%) under the person's feet — the surfboard, riding the trend.

ELEMENT 4 — TRAILING FIGURES:
2 small black figures behind/below the wave — those who missed it.

ELEMENT 5 — DIRECTION ARROW:
One black arrow pointing in the wave direction — market movement.

ELEMENT 6 — GROUND LINE:
Thin horizontal black rectangle at the bottom.""",

    "market_v2_map": """EXACT SCENE — MARKET MAP: Person navigating with compass:

ELEMENT 1 — MAP GRID:
6-8 thin black rectangles forming a grid pattern — the market landscape.

ELEMENT 2 — PERSON (left):
One black human figure silhouette. Head (4%), body (6% × 16%), base (10% × 3%).

ELEMENT 3 — COMPASS (KEY ELEMENT — LIME):
One bright electric lime (#DFFF00) diamond shape (12% × 12%) with a lime triangle inside pointing up — the compass, the direction.

ELEMENT 4 — PATH:
One lime diagonal rectangle (3% × 30%) showing the navigation path across the grid.

ELEMENT 5 — DESTINATION MARKER:
One lime square (8% × 8%) at the end of the path — the goal.

ELEMENT 6 — GROUND LINE:
Thin horizontal black rectangle at the bottom.""",

    "market_v3_radar": """EXACT SCENE — OPPORTUNITY RADAR: Person with radar scanning for opportunities:

ELEMENT 1 — RADAR DISH:
One black triangle (20% × 15%) pointing right — the radar dish/scanner.

ELEMENT 2 — SCAN BEAM (KEY ELEMENT — LIME):
One bright electric lime (#DFFF00) triangle (40% base, 25% height) emanating from the radar, spreading outward — the scan beam.

ELEMENT 3 — PERSON OPERATING:
One black human figure silhouette behind/next to the radar. Head (4%), body (6% × 16%), base (10% × 3%).

ELEMENT 4 — DETECTED OPPORTUNITIES:
3 small lime squares (5% × 5% each) within the scan beam — opportunities found.

ELEMENT 5 — MISSED AREAS:
2 small black squares outside the beam — unseen.

ELEMENT 6 — GROUND LINE:
Thin horizontal black rectangle at the bottom.""",
}

# ============================================================================
# Topic keyword → scene variants mapping (from СБОРКА v6.0)
# ============================================================================

TOPIC_MAPPING = {
    # Зарплата / переговоры
    "зарплат": ["salary_v1_chart", "salary_v2_scales", "salary_v3_lever", "salary_v4_gap"],
    "переговор": ["salary_v1_chart", "salary_v2_scales", "salary_v3_lever", "salary_v4_gap"],
    "повышен": ["salary_v1_chart", "salary_v3_lever", "salary_v4_gap"],
    "деньг": ["salary_v1_chart", "salary_v2_scales"],
    "оклад": ["salary_v1_chart", "salary_v2_scales", "salary_v3_lever"],

    # Резюме
    "ошибк": ["resume_v1_errors", "resume_v3_filter"],
    "резюме": ["resume_v1_errors", "resume_v2_improve", "resume_v3_filter", "resume_v4_stack"],
    "cv": ["resume_v2_improve", "resume_v3_filter", "resume_v4_stack"],
    "красн": ["resume_v1_errors"],
    "флаг": ["resume_v1_errors"],
    "провал": ["resume_v1_errors", "resume_v3_filter"],

    # Выделиться / кандидаты
    "выделиться": ["standout_v1_row", "standout_v2_grid", "standout_v3_race", "standout_v4_spotlight"],
    "кандидат": ["standout_v1_row", "standout_v2_grid", "standout_v3_race", "standout_v4_spotlight"],
    "конкурен": ["standout_v1_row", "standout_v3_race", "standout_v4_spotlight"],
    "уникальн": ["standout_v2_grid", "standout_v4_spotlight"],
    "отличаться": ["standout_v1_row", "standout_v2_grid", "standout_v3_race"],
    "личный бренд": ["standout_v2_grid", "standout_v4_spotlight"],
    "опереж": ["standout_v3_race"],

    # ATS
    "ats": ["ats_v1_wall", "ats_v2_funnel", "ats_v3_scanner"],
    "фильтр": ["ats_v1_wall", "ats_v2_funnel", "ats_v3_scanner"],
    "отбор": ["ats_v2_funnel", "ats_v3_scanner"],
    "воронк": ["ats_v2_funnel"],
    "отклик": ["ats_v1_wall", "ats_v2_funnel"],
    "пройти": ["ats_v1_wall", "ats_v3_scanner"],

    # Интервью / собеседование
    "собеседован": ["interview_v1_table", "interview_v2_questions", "interview_v3_handshake"],
    "интервью": ["interview_v1_table", "interview_v2_questions", "interview_v3_handshake"],
    "hr": ["interview_v1_table", "interview_v2_questions"],
    "рекрутер": ["interview_v1_table", "interview_v2_questions"],
    "вопрос": ["interview_v2_questions"],
    "ответ": ["interview_v2_questions"],

    # ИИ / автоматизация
    "ии": ["ai_v1_pressure", "ai_v2_collaboration", "ai_v3_tool"],
    "ai": ["ai_v1_pressure", "ai_v2_collaboration", "ai_v3_tool"],
    "искусственн": ["ai_v1_pressure", "ai_v2_collaboration"],
    "автоматиз": ["ai_v1_pressure", "ai_v3_tool"],
    "робот": ["ai_v1_pressure", "ai_v2_collaboration"],
    "сокращени": ["ai_v1_pressure"],
    "увольн": ["ai_v1_pressure"],
    "мультиагент": ["ai_v2_collaboration", "ai_v3_tool"],
    "агент": ["ai_v2_collaboration", "ai_v3_tool"],

    # Карьера / рост
    "карьер": ["career_v1_stairs", "career_v2_chart", "career_v3_door"],
    "рост": ["career_v1_stairs", "career_v2_chart"],
    "план": ["career_v1_stairs", "career_v2_chart"],
    "этап": ["career_v1_stairs"],
    "развит": ["career_v1_stairs", "career_v2_chart", "career_v3_door"],
    "лестниц": ["career_v1_stairs"],
    "навык": ["career_v1_stairs", "career_v2_chart"],
    "skill": ["career_v1_stairs", "career_v2_chart"],

    # Стресс / давление
    "стресс": ["stress_v1_pressure", "stress_v2_clock", "stress_v3_walls"],
    "давлен": ["stress_v1_pressure", "stress_v3_walls"],
    "выгоран": ["stress_v1_pressure", "stress_v2_clock"],
    "тревог": ["stress_v1_pressure", "stress_v3_walls"],
    "страх": ["stress_v1_pressure", "stress_v3_walls"],
    "неуверен": ["stress_v1_pressure"],
    "перегруз": ["stress_v1_pressure", "stress_v2_clock"],
    "дедлайн": ["stress_v2_clock"],
    "врем": ["stress_v2_clock"],
    "burnout": ["stress_v1_pressure", "stress_v2_clock"],

    # Выбор / сравнение офферов
    "оффер": ["offers_v1_compare", "offers_v2_scales", "offers_v3_paths"],
    "выбор": ["offers_v1_compare", "offers_v2_scales", "offers_v3_paths"],
    "сравнен": ["offers_v1_compare", "offers_v2_scales"],
    "vs": ["offers_v1_compare", "offers_v2_scales"],

    # Система / клуб
    "систем": ["system_v1_chaos", "system_v2_puzzle", "system_v3_network"],
    "сборка": ["system_v1_chaos", "system_v2_puzzle", "system_v3_network"],
    "клуб": ["system_v1_chaos", "system_v3_network"],
    "ментор": ["system_v3_network"],
    "метод": ["system_v1_chaos", "system_v2_puzzle"],
    "структур": ["system_v1_chaos", "system_v2_puzzle"],
    "хаос": ["system_v1_chaos"],

    # Рынок труда / тренды
    "рынок": ["market_v1_wave", "market_v2_map", "market_v3_radar"],
    "тренд": ["market_v1_wave", "market_v2_map"],
    "возможност": ["market_v3_radar", "career_v3_door"],
    "поиск работ": ["market_v2_map", "market_v3_radar"],
    "вакан": ["market_v2_map", "market_v3_radar"],

    # Нетворкинг / партнёрства
    "нетворк": ["system_v3_network", "interview_v3_handshake"],
    "партнёр": ["interview_v3_handshake", "system_v3_network"],
    "сотрудн": ["interview_v3_handshake", "system_v3_network", "ai_v2_collaboration"],

    # Контент / LinkedIn / бренд
    "linkedin": ["resume_v2_improve", "standout_v4_spotlight"],
    "контент": ["resume_v2_improve", "standout_v4_spotlight"],
    "пост": ["resume_v2_improve", "standout_v4_spotlight"],
    "бренд": ["standout_v4_spotlight", "standout_v2_grid"],
    "бизнес": ["career_v2_chart", "salary_v3_lever", "market_v1_wave"],
    "стратег": ["career_v2_chart", "salary_v3_lever", "market_v2_map"],

    # Команда / коллаборация
    "команд": ["system_v2_puzzle", "system_v3_network", "ai_v2_collaboration"],
    "remote": ["system_v3_network", "ai_v2_collaboration"],
    "удалён": ["system_v3_network", "ai_v2_collaboration"],

    # Безопасность / защита
    "безопас": ["stress_v3_walls", "ats_v1_wall"],
    "защит": ["stress_v3_walls", "ats_v1_wall"],

    # Запуск / стартап
    "запуск": ["career_v3_door", "market_v1_wave"],
    "старт": ["career_v3_door", "market_v1_wave"],
    "startup": ["career_v3_door", "market_v1_wave"],

    # Баланс
    "баланс": ["salary_v2_scales", "offers_v2_scales"],

    # Цели / достижения
    "цель": ["career_v1_stairs", "career_v2_chart"],
    "goal": ["career_v1_stairs", "career_v2_chart"],
    "достиж": ["career_v1_stairs", "career_v2_chart"],

    # Коммуникация
    "коммуник": ["interview_v1_table", "system_v3_network"],
    "презентац": ["standout_v4_spotlight", "interview_v1_table"],
    "pitch": ["standout_v4_spotlight", "interview_v1_table"],

    # Анализ / исследования
    "исследов": ["market_v3_radar", "career_v2_chart"],
    "анализ": ["market_v3_radar", "career_v2_chart"],
    "data": ["market_v3_radar", "career_v2_chart"],

    # Признание ИИ
    "признан": ["ai_v1_pressure", "ai_v2_collaboration"],
    "использован": ["ai_v3_tool", "ai_v2_collaboration"],
    "вытесня": ["ai_v1_pressure"],
    "замен": ["ai_v1_pressure", "ai_v2_collaboration"],
}

DEFAULT_SCENES = [
    "standout_v1_row", "standout_v2_grid", "standout_v3_race", "standout_v4_spotlight",
    "career_v1_stairs", "career_v2_chart", "career_v3_door",
    "system_v1_chaos", "system_v2_puzzle",
    "market_v1_wave", "market_v2_map",
]


def _select_scene(topic: str) -> str:
    """Select a scene based on topic keywords."""
    topic_lower = topic.lower()
    for keyword, variants in TOPIC_MAPPING.items():
        if keyword in topic_lower:
            return random.choice(variants)
    return random.choice(DEFAULT_SCENES)


def _build_prompt(topic: str, post_text: str) -> str:
    """Build the full image generation prompt — ISOTYPE v6.0."""
    scene_key = _select_scene(topic)
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


def _call_openrouter(prompt: str, max_retries: int = 3) -> dict:
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

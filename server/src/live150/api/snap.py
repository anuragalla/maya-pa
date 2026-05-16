"""Snap: 2-pass food volume and calorie estimation pipeline.

Mobile app sends a resized JPEG (base64, ~300KB) with LiDAR/depth metadata.
Two chained Gemini calls produce structured nutritional breakdown:
  Call 1 (Surveyor): image + metadata → per-item volume estimates
  Call 2 (Dietitian): volumes → grams, calories, macros
"""

import base64
import json
import logging
import time
from typing import Literal

import jwt
from fastapi import APIRouter, Depends, Header, HTTPException
from pydantic import BaseModel, Field

from live150.agent.genai_client import get_genai_client
from live150.config import settings

logger = logging.getLogger(__name__)
router = APIRouter(tags=["snap"])

GEMINI_MODEL = "gemini-3.1-flash-lite"
MAX_IMAGE_BYTES = 10 * 1024 * 1024  # 10 MB decoded


# ---------------------------------------------------------------------------
# Auth
# ---------------------------------------------------------------------------

def _require_jwt(authorization: str = Header(...)) -> dict:
    """Decode a liv150-api Bearer JWT. Returns claims or raises 401."""
    if not authorization.startswith("Bearer "):
        raise HTTPException(status_code=401, detail="Missing Bearer token")
    token = authorization[7:]
    try:
        return jwt.decode(token, settings.jwt_secret, algorithms=[settings.jwt_algorithm])
    except jwt.PyJWTError:
        raise HTTPException(status_code=401, detail="Invalid token")


# ---------------------------------------------------------------------------
# Request / response models
# ---------------------------------------------------------------------------

class SnapMetadata(BaseModel):
    sensor_type: Literal["lidar", "dual", "rgb"] = "lidar"
    camera_distance_cm: float
    anchor_width_cm: float
    anchor_length_cm: float
    anchor_thickness_cm: float
    anchor_shape_hint: str = "unknown"
    depth_reliable: bool = True


class SnapRequest(BaseModel):
    image_base64: str = Field(..., min_length=100)
    metadata: SnapMetadata




class MacroBreakdown(BaseModel):
    protein_g: float
    carbs_g: float
    fat_g: float


class MealItem(BaseModel):
    food_name: str
    estimated_grams: float
    calories: float
    macros: MacroBreakdown


class MealTotals(BaseModel):
    total_calories: float
    total_protein_g: float
    total_carbs_g: float
    total_fat_g: float


class SnapResponse(BaseModel):
    meal_breakdown: list[MealItem]
    meal_totals: MealTotals
    debug: dict | None = None


# ---------------------------------------------------------------------------
# Prompt templates
# ---------------------------------------------------------------------------

SURVEYOR_PROMPT = """\
[SYSTEM]
You are an expert food volume and portion estimator. You will receive an image of a meal \
with a bounding box drawn around the central/largest item. This boxed item is your physical "anchor."

You will also receive metadata providing the physical dimensions of this anchor object. \
Your trust in these dimensions depends on the Sensor Type:
- If "lidar": The dimensions are fairly accurate but see INFLATION WARNING below.
- If "dual" or "rgb": The dimensions are rough estimates based on camera disparity. You MUST \
cross-reference them against visual reference objects in the photo (like plates, forks, hands, \
or tables) to sanity-check the physical scale.

[INFLATION WARNING]
The anchor dimensions come from a depth-sensor bounding box, NOT a precise outline of the food. \
They are typically 15-25% LARGER than the actual food/container because:
- The bounding box includes vessel rims, handles, and spoons resting on the edge.
- The thickness includes the container walls, base thickness, and any gap to the surface below.
- Nearby objects (utensils, hands) can extend the box.
You MUST visually estimate the actual food container/item size and mentally shrink the provided \
dimensions accordingly before calculating volume.

[TASK]
1. Identify the food item inside the bounding box. If the food is inside a container (bowl, pot, \
plate, kadhai, etc.), identify BOTH the container and the food. The anchor dimensions describe \
the container's bounding box, NOT the food directly.
2. CONTAINER RULE: When food is in a container, estimate the container's actual interior \
dimensions (after applying the inflation correction above), then estimate what fraction of the \
container is filled with food. A pot that is 26cm wide and 10cm deep, filled to 60% depth, \
holds much less than its full volume.
3. GEOMETRY RULE: The provided dimensions represent a "Bounding Box" (maximum outer limits). \
Organic foods (like fruit slices, chicken breasts, or wedges) taper at the edges and do not \
fill their bounding boxes. Visually estimate how much of the bounding box is actually filled \
by the food and reduce your volume calculation accordingly.
4. Thickness measurements are often inflated because they include the container base, the \
surface the container sits on, or a hand holding the item. Use visual common sense to estimate \
actual food depth/thickness.
5. Identify all other food items in the image. Estimate their portion sizes by visually comparing \
their scale to the anchor object.
6. Express all portion sizes in standard volumetric units (e.g., metric cups, tablespoons, \
milliliters) or item counts (e.g., 3 medium pieces). Do not calculate grams.

[METADATA]
Sensor Type: {sensor_type}
Depth Reliable: {depth_reliable} (If false, ignore the physical dimensions completely and rely purely on visual estimation)
Camera Distance: {camera_distance_cm} cm
Anchor Box Dimensions (raw sensor — expect 15-25% inflation): {anchor_width_cm} cm wide x \
{anchor_length_cm} cm long x {anchor_thickness_cm} cm thick.
Anchor Shape: {anchor_shape_hint}

[OUTPUT FORMAT]
Return a JSON object with the following schema:
{{
  "items": [
    {{
      "food_name": "string (specific identification, e.g. 'chicken curry in kadhai' not just 'chicken curry')",
      "estimated_volume": "string (e.g., '1.5 cups', '3 tablespoons', '4 pieces')",
      "is_anchor_item": boolean,
      "reasoning": "string (1. what inflation correction was applied to the raw dimensions, \
2. if a container, what are the estimated interior dimensions and fill level, \
3. final volume calculation)"
    }}
  ]
}}"""

DIETITIAN_PROMPT = """\
[SYSTEM]
You are an expert clinical dietitian and nutritional database calculator. You will receive \
a structured JSON list of food items and their estimated visual volumes or counts.

[TASK]
1. Convert the provided volume/count into an estimated weight in grams. You must use your \
knowledge of food density (e.g., 1 cup of leafy greens weighs much less than 1 cup of cooked \
rice) to make this conversion accurate.
2. Calculate the nutritional breakdown (Calories, Protein, Carbs, Fats) based on that calculated \
gram weight.
3. Provide a total meal summary.

[INPUT DATA]
{surveyor_json}

[OUTPUT FORMAT]
Return a JSON object with the following schema:
{{
  "meal_breakdown": [
    {{
      "food_name": "string",
      "estimated_grams": number,
      "calories": number,
      "macros": {{
        "protein_g": number,
        "carbs_g": number,
        "fat_g": number
      }}
    }}
  ],
  "meal_totals": {{
    "total_calories": number,
    "total_protein_g": number,
    "total_carbs_g": number,
    "total_fat_g": number
  }}
}}"""


# ---------------------------------------------------------------------------
# Gemini helpers
# ---------------------------------------------------------------------------

def _build_surveyor_prompt(meta: SnapMetadata) -> str:
    return SURVEYOR_PROMPT.format(
        sensor_type=meta.sensor_type,
        depth_reliable=meta.depth_reliable,
        camera_distance_cm=round(meta.camera_distance_cm, 1),
        anchor_width_cm=round(meta.anchor_width_cm, 1),
        anchor_length_cm=round(meta.anchor_length_cm, 1),
        anchor_thickness_cm=round(meta.anchor_thickness_cm, 1),
        anchor_shape_hint=meta.anchor_shape_hint,
    )


async def _call_surveyor(image_bytes: bytes, meta: SnapMetadata) -> tuple[dict, dict]:
    """Call 1: multimodal — image + metadata → volume estimates.

    Returns (parsed_result, debug_info).
    """
    from google.genai import types

    client = get_genai_client()
    prompt_text = _build_surveyor_prompt(meta)

    logger.info("snap_llm_surveyor_request", extra={
        "model": GEMINI_MODEL,
        "prompt_length": len(prompt_text),
        "image_bytes": len(image_bytes),
        "metadata": meta.model_dump(),
    })

    t0 = time.monotonic()
    response = await client.aio.models.generate_content(
        model=GEMINI_MODEL,
        contents=[
            types.Part.from_bytes(data=image_bytes, mime_type="image/jpeg"),
            types.Part.from_text(text=prompt_text),
        ],
        config=types.GenerateContentConfig(
            response_mime_type="application/json",
            temperature=0.2,
        ),
    )
    elapsed_ms = int((time.monotonic() - t0) * 1000)

    raw_text = response.text or ""
    logger.info("snap_llm_surveyor_response", extra={
        "model": GEMINI_MODEL,
        "elapsed_ms": elapsed_ms,
        "response_length": len(raw_text),
        "raw_response": raw_text[:2000],
    })

    if not raw_text:
        raise ValueError("Surveyor call returned empty response")

    parsed = json.loads(raw_text)
    debug = {
        "prompt": prompt_text,
        "raw_response": raw_text,
        "elapsed_ms": elapsed_ms,
    }
    return parsed, debug


async def _call_dietitian(surveyor_output: dict) -> tuple[dict, dict]:
    """Call 2: text-only — volume estimates → grams, calories, macros.

    Returns (parsed_result, debug_info).
    """
    from google.genai import types

    client = get_genai_client()
    surveyor_json = json.dumps(surveyor_output, indent=2)
    prompt_text = DIETITIAN_PROMPT.format(surveyor_json=surveyor_json)

    logger.info("snap_llm_dietitian_request", extra={
        "model": GEMINI_MODEL,
        "prompt_length": len(prompt_text),
        "surveyor_items": len(surveyor_output.get("items", [])),
    })

    t0 = time.monotonic()
    response = await client.aio.models.generate_content(
        model=GEMINI_MODEL,
        contents=[types.Part.from_text(text=prompt_text)],
        config=types.GenerateContentConfig(
            response_mime_type="application/json",
            temperature=0.1,
        ),
    )
    elapsed_ms = int((time.monotonic() - t0) * 1000)

    raw_text = response.text or ""
    logger.info("snap_llm_dietitian_response", extra={
        "model": GEMINI_MODEL,
        "elapsed_ms": elapsed_ms,
        "response_length": len(raw_text),
        "raw_response": raw_text[:2000],
    })

    if not raw_text:
        raise ValueError("Dietitian call returned empty response")

    parsed = json.loads(raw_text)
    debug = {
        "prompt": prompt_text,
        "raw_response": raw_text,
        "elapsed_ms": elapsed_ms,
    }
    return parsed, debug


# ---------------------------------------------------------------------------
# Endpoint
# ---------------------------------------------------------------------------

@router.post("/analyze", response_model=SnapResponse)
async def analyze_meal(body: SnapRequest, claims: dict = Depends(_require_jwt)):
    """Two-pass food analysis: Surveyor (vision) → Dietitian (text)."""
    try:
        image_bytes = base64.b64decode(body.image_base64, validate=True)
    except Exception:
        raise HTTPException(status_code=400, detail="Invalid base64 image data")

    if len(image_bytes) > MAX_IMAGE_BYTES:
        raise HTTPException(status_code=413, detail=f"Decoded image exceeds {MAX_IMAGE_BYTES // (1024*1024)} MB")

    meta = body.metadata
    user_id = claims.get("sub", "unknown")
    logger.info("snap_analyze_start", extra={
        "user": user_id,
        "sensor": meta.sensor_type,
        "depth_reliable": meta.depth_reliable,
        "image_size": len(image_bytes),
    })

    try:
        surveyor_result, surveyor_debug = await _call_surveyor(image_bytes, meta)
    except json.JSONDecodeError as e:
        logger.error("snap_surveyor_json_error", extra={"user": user_id, "error": str(e)})
        raise HTTPException(status_code=502, detail="Surveyor model returned invalid JSON")
    except Exception as e:
        logger.error("snap_surveyor_error", extra={"user": user_id, "error": str(e)})
        raise HTTPException(status_code=502, detail=f"Surveyor call failed: {e}")

    logger.info("snap_surveyor_done", extra={
        "user": user_id,
        "item_count": len(surveyor_result.get("items", [])),
    })

    try:
        dietitian_result, dietitian_debug = await _call_dietitian(surveyor_result)
    except json.JSONDecodeError as e:
        logger.error("snap_dietitian_json_error", extra={"user": user_id, "error": str(e)})
        raise HTTPException(status_code=502, detail="Dietitian model returned invalid JSON")
    except Exception as e:
        logger.error("snap_dietitian_error", extra={"user": user_id, "error": str(e)})
        raise HTTPException(status_code=502, detail=f"Dietitian call failed: {e}")

    logger.info("snap_analyze_done", extra={
        "user": user_id,
        "total_calories": dietitian_result.get("meal_totals", {}).get("total_calories"),
    })

    dietitian_result["debug"] = {
        "surveyor": {
            "request": {"metadata": meta.model_dump(), "prompt": surveyor_debug["prompt"]},
            "response": surveyor_result,
            "raw_response": surveyor_debug["raw_response"],
            "elapsed_ms": surveyor_debug["elapsed_ms"],
        },
        "dietitian": {
            "request": {"prompt": dietitian_debug["prompt"]},
            "response": dietitian_result.get("meal_breakdown"),
            "raw_response": dietitian_debug["raw_response"],
            "elapsed_ms": dietitian_debug["elapsed_ms"],
        },
    }

    return dietitian_result

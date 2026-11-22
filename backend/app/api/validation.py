"""Small request-validation helpers shared by the API routes."""

from __future__ import annotations

import math
import re

from fastapi import HTTPException, Request

EMAIL_RE = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")


async def json_object(request: Request) -> dict:
    """Parse a JSON request body and require a JSON object (422 otherwise)."""
    try:
        data = await request.json()
    except (ValueError, UnicodeDecodeError) as exc:
        raise HTTPException(status_code=422, detail="invalid JSON body") from exc
    if not isinstance(data, dict):
        raise HTTPException(status_code=422, detail="JSON body must be an object")
    return data


def finite_number(value) -> float | None:
    """Return a finite float for numeric input; None for booleans/other values."""
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        return None
    number = float(value)
    return number if math.isfinite(number) else None


def clamp_int(value, low: int, high: int) -> int | None:
    number = finite_number(value)
    if number is None:
        return None
    return max(low, min(high, int(number)))

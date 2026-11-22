from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Request

from app.api.serializers import serialize_system_mode, serialize_system_mode_history
from app.api.validation import json_object
from app.database import get_db
from app.models import (
    SYSTEM_MODES,
    SystemMode,
    SystemModeHistory,
    set_system_mode,
)
from app.security import get_current_user, require_role, user_property_ids

router = APIRouter()


def _require_property(db, user_id: str, property_id: str) -> None:
    if property_id not in user_property_ids(db, user_id):
        raise HTTPException(status_code=404, detail="Not found")


@router.get("/api/v1/system/modes")
def list_modes(user=Depends(get_current_user), db=Depends(get_db)):
    """Current system mode per property (any member)."""
    return [
        serialize_system_mode(db.get(SystemMode, pid), pid)
        for pid in user_property_ids(db, user.id)
    ]


@router.put("/api/v1/system/modes/{property_id}")
async def set_mode(
    property_id: str,
    request: Request,
    user=Depends(get_current_user),
    db=Depends(get_db),
):
    """Set the system mode for a property (owner/admin)."""
    _require_property(db, user.id, property_id)
    require_role(db, user.id, property_id, {"owner", "admin"})
    data = await json_object(request)
    mode = data.get("mode")
    if not isinstance(mode, str) or mode not in SYSTEM_MODES:
        raise HTTPException(status_code=422, detail="mode must be one of: " + ", ".join(SYSTEM_MODES))
    set_system_mode(db, property_id, mode, changed_by=user.id)
    db.commit()
    return serialize_system_mode(db.get(SystemMode, property_id), property_id)


@router.get("/api/v1/system/modes/{property_id}/history")
def mode_history(property_id: str, user=Depends(get_current_user), db=Depends(get_db)):
    """Mode change history for a property, newest first (owner/admin/responder)."""
    _require_property(db, user.id, property_id)
    require_role(db, user.id, property_id, {"owner", "admin", "responder"})
    rows = (
        db.query(SystemModeHistory)
        .filter_by(property_id=property_id)
        .order_by(SystemModeHistory.changed_at.desc(), SystemModeHistory.id.desc())
        .all()
    )
    return {"items": [serialize_system_mode_history(r) for r in rows]}

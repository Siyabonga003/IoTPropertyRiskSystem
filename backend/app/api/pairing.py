from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Request

from app import pairing as pairing_service
from app.database import get_db
from app.security import bearer_token, get_current_user

router = APIRouter()


@router.post("/api/v1/devices/{device_id}/pair-start")
def pair_start(device_id: str, db=Depends(get_db)):
    return pairing_service.pair_start(db, device_id)


@router.get("/api/v1/devices/{device_id}/pair-status")
def pair_status(device_id: str, request: Request, db=Depends(get_db)):
    token = bearer_token(request)
    return pairing_service.pair_status(db, device_id, token)


@router.post("/api/v1/pair")
async def pair(request: Request, db=Depends(get_db), user=Depends(get_current_user)):
    data = await request.json()
    token = data.get("token")
    if not isinstance(token, str) or not token:
        raise HTTPException(status_code=401, detail="TOKEN_INVALID")
    property_id: str | None = data.get("property_id")
    return pairing_service.pair_claim(db, user.id, token, property_id)

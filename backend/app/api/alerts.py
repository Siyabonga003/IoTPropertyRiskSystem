from __future__ import annotations

from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException, Request

from app.api.serializers import serialize_alert
from app.database import get_db
from app.models import Alert, utcnow
from app.security import get_current_user, require_role, user_property_ids

router = APIRouter()


@router.get("/api/v1/alerts")
def list_alerts(
    request: Request,
    db=Depends(get_db),
    user=Depends(get_current_user),
):
    props = user_property_ids(db, user.id)
    if not props:
        return {"items": [], "total": 0, "limit": 50, "offset": 0}
    query = db.query(Alert).filter(Alert.property_id.in_(props))
    status = request.query_params.get("status")
    if status:
        query = query.filter(Alert.status == status)
    severity = request.query_params.get("severity")
    if severity:
        query = query.filter(Alert.severity == severity)
    device_id = request.query_params.get("device_id")
    if device_id:
        query = query.filter(Alert.device_id == device_id)
    since = request.query_params.get("since")
    if since:
        try:
            since_dt = datetime.fromisoformat(since)
            query = query.filter(Alert.last_seen_at >= since_dt)
        except ValueError:
            pass
    query = query.order_by(Alert.last_seen_at.desc(), Alert.first_seen_at.desc())
    total = query.count()
    try:
        limit = int(request.query_params.get("limit", "50"))
    except ValueError:
        limit = 50
    try:
        offset = int(request.query_params.get("offset", "0"))
    except ValueError:
        offset = 0
    limit = max(1, min(limit, 500))
    offset = max(0, offset)
    items = query.offset(offset).limit(limit).all()
    return {
        "items": [serialize_alert(a) for a in items],
        "total": total,
        "limit": limit,
        "offset": offset,
    }


@router.get("/api/v1/alerts/{alert_id}")
def get_alert(alert_id: str, db=Depends(get_db), user=Depends(get_current_user)):
    alert = db.get(Alert, alert_id)
    if alert is None or alert.property_id not in user_property_ids(db, user.id):
        raise HTTPException(status_code=404, detail="Not found")
    return serialize_alert(alert)


@router.post("/api/v1/alerts/{alert_id}/ack")
def ack_alert(alert_id: str, db=Depends(get_db), user=Depends(get_current_user)):
    alert = db.get(Alert, alert_id)
    if alert is None or alert.property_id not in user_property_ids(db, user.id):
        raise HTTPException(status_code=404, detail="Not found")
    require_role(db, user.id, alert.property_id, {"owner", "admin", "responder"})
    if alert.status == "open":
        alert.status = "acknowledged"
        alert.acknowledged_at = utcnow()
        db.commit()
    return serialize_alert(alert)

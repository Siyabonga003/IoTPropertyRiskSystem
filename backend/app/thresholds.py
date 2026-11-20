from __future__ import annotations


class Level:
    OK = 0
    NOTICE = 1
    WARNING = 2
    ALERT = 3
    CRITICAL = 4


SIGNALS = ("smoke_gas", "flame", "water_leak", "motion")

SEVERITY_NAMES = {
    Level.OK: "ok",
    Level.NOTICE: "notice",
    Level.WARNING: "warning",
    Level.ALERT: "alert",
    Level.CRITICAL: "critical",
}
SEVERITY_RANK = {name: level for level, name in SEVERITY_NAMES.items()}


def _num(value: object) -> float | None:
    if isinstance(value, bool):
        return None
    if isinstance(value, (int, float)):
        return float(value)
    return None


def smoke_level(value: float | None) -> int:
    """Smoke (ppm): warning >= 301 (clear <= 250), alert >= 701 (clear <= 650), critical > 1000 (clear <= 950)."""
    v = _num(value)
    if v is None or v <= 0:
        return Level.OK
    if v > 1000:
        return Level.CRITICAL
    if v >= 701:
        return Level.ALERT
    if v >= 301:
        return Level.WARNING
    return Level.OK


def gas_level(value: float | None) -> int:
    """Combustible gas (ppm): warning >= 11 (clear <= 8), alert >= 31 (clear <= 25), critical >= 61 (clear <= 50)."""
    v = _num(value)
    if v is None or v <= 0:
        return Level.OK
    if v >= 61:
        return Level.CRITICAL
    if v >= 31:
        return Level.ALERT
    if v >= 11:
        return Level.WARNING
    return Level.OK


def flame_level(detected: bool | None) -> int:
    """Flame is digital: critical when detected."""
    return Level.CRITICAL if detected else Level.OK


def water_leak_level(level: int | None) -> int:
    """Water leak level 0-100: warning >= 1, alert >= 25, critical >= 50 (draft scale)."""
    v = _num(level)
    if v is None or v <= 0:
        return Level.OK
    if v >= 50:
        return Level.CRITICAL
    if v >= 25:
        return Level.ALERT
    return Level.WARNING


def motion_level(motion_detected: bool | None) -> int:
    """Motion is informational (notice); never escalates."""
    return Level.NOTICE if motion_detected else Level.OK


def compute_levels(
    *,
    smoke_ppm: float | None = None,
    gas_ppm: float | None = None,
    flame_detected: bool | None = None,
    water_level: int | None = None,
    motion_detected: bool | None = None,
) -> dict[str, int]:
    """Compute the per-signal level for a telemetry reading."""
    return {
        "smoke_gas": max(smoke_level(smoke_ppm), gas_level(gas_ppm)),
        "flame": flame_level(flame_detected) if flame_detected is not None else Level.OK,
        "water_leak": water_leak_level(water_level) if water_level is not None else Level.OK,
        "motion": motion_level(motion_detected) if motion_detected is not None else Level.OK,
    }


def device_risk_level(levels: dict[str, int]) -> int:
    """Device risk = highest signal level."""
    return max((levels.get(s, Level.OK) for s in SIGNALS), default=Level.OK)

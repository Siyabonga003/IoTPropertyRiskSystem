from __future__ import annotations

from app.thresholds import Level, compute_levels, device_risk_level


def test_smoke_levels():
    assert compute_levels(smoke_ppm=0)["smoke_gas"] == Level.OK
    assert compute_levels(smoke_ppm=300)["smoke_gas"] == Level.OK
    assert compute_levels(smoke_ppm=301)["smoke_gas"] == Level.WARNING
    assert compute_levels(smoke_ppm=700)["smoke_gas"] == Level.WARNING
    assert compute_levels(smoke_ppm=701)["smoke_gas"] == Level.ALERT
    assert compute_levels(smoke_ppm=1000)["smoke_gas"] == Level.ALERT
    assert compute_levels(smoke_ppm=1001)["smoke_gas"] == Level.CRITICAL


def test_gas_levels():
    assert compute_levels(gas_ppm=10)["smoke_gas"] == Level.OK
    assert compute_levels(gas_ppm=11)["smoke_gas"] == Level.WARNING
    assert compute_levels(gas_ppm=30)["smoke_gas"] == Level.WARNING
    assert compute_levels(gas_ppm=31)["smoke_gas"] == Level.ALERT
    assert compute_levels(gas_ppm=60)["smoke_gas"] == Level.ALERT
    assert compute_levels(gas_ppm=61)["smoke_gas"] == Level.CRITICAL


def test_flame_levels():
    assert compute_levels(flame_detected=False)["flame"] == Level.OK
    assert compute_levels(flame_detected=True)["flame"] == Level.CRITICAL


def test_water_leak_levels():
    assert compute_levels(water_level=0)["water_leak"] == Level.OK
    assert compute_levels(water_level=1)["water_leak"] == Level.WARNING
    assert compute_levels(water_level=24)["water_leak"] == Level.WARNING
    assert compute_levels(water_level=25)["water_leak"] == Level.ALERT
    assert compute_levels(water_level=49)["water_leak"] == Level.ALERT
    assert compute_levels(water_level=50)["water_leak"] == Level.CRITICAL


def test_motion_levels():
    assert compute_levels(motion_detected=False)["motion"] == Level.OK
    assert compute_levels(motion_detected=True)["motion"] == Level.NOTICE


def test_device_risk_is_max_of_signals():
    levels = compute_levels(smoke_ppm=400, water_level=30)
    assert levels["smoke_gas"] == Level.WARNING
    assert levels["water_leak"] == Level.ALERT
    assert device_risk_level(levels) == Level.ALERT

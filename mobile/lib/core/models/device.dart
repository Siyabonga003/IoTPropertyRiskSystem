import '../utils.dart';
import 'system_mode.dart';

/// A device as returned by the backend (§5.2, docs/SPEC.md).
class Device {
  const Device({
    required this.deviceId,
    this.propertyId,
    this.name = '',
    this.firmwareVersion,
    this.status = 'pairing',
    this.pairedAt,
    this.lastSeenAt,
    this.riskLevel = 0,
    this.sensorLevels = const {},
    this.lastSmokePpm,
    this.lastGasPpm,
    this.lastFlameDetected,
    this.lastWaterLevel,
    this.lastMotionDetected,
    this.lastOccupancy,
    this.batteryPct,
    this.rssiDbm,
    this.deviceHealth = 'ok',
    this.faults = const [],
    this.systemMode = unarmedMode,
  });
  final String deviceId;
  final String? propertyId;
  final String name;
  final String? firmwareVersion;
  final String status;
  final DateTime? pairedAt;
  final DateTime? lastSeenAt;
  final int riskLevel;
  final Map<String, int> sensorLevels;
  final double? lastSmokePpm;
  final double? lastGasPpm;
  final bool? lastFlameDetected;
  final int? lastWaterLevel;
  final bool? lastMotionDetected;
  final bool? lastOccupancy;
  final int? batteryPct;
  final int? rssiDbm;
  final String deviceHealth;
  final List<String> faults;
  /// Current system mode of the device's property (backend-authoritative).
  final String systemMode;

  factory Device.fromJson(Map<String, dynamic> j) => Device(
        deviceId: j['device_id'] as String? ?? '',
        propertyId: j['property_id'] as String?,
        name: j['name'] as String? ?? '',
        firmwareVersion: j['firmware_version'] as String?,
        status: j['status'] as String? ?? 'pairing',
        pairedAt: parseDateTime(j['paired_at']),
        lastSeenAt: parseDateTime(j['last_seen_at']),
        riskLevel: intOf(j['risk_level']),
        sensorLevels: (j['sensor_levels'] as Map<String, dynamic>? ?? const {})
            .map((k, v) => MapEntry(k, intOf(v))),
        lastSmokePpm: doubleOf(j['last_smoke_ppm']),
        lastGasPpm: doubleOf(j['last_gas_ppm']),
        lastFlameDetected: j['last_flame_detected'] as bool?,
        lastWaterLevel: intOrNull(j['last_water_level']),
        lastMotionDetected: j['last_motion_detected'] as bool?,
        lastOccupancy: j['last_occupancy'] as bool?,
        batteryPct: intOrNull(j['battery_pct']),
        rssiDbm: intOrNull(j['rssi_dbm']),
        deviceHealth: j['device_health'] as String? ?? 'ok',
        faults: (j['faults'] as List<dynamic>? ?? const []).whereType<String>().toList(),
        systemMode: j['system_mode'] as String? ?? unarmedMode,
      );
}

/// Latest telemetry event for a device (§2.1, docs/SPEC.md).
class TelemetryEvent {
  const TelemetryEvent({
    required this.deviceId,
    this.sequence,
    this.timestamp,
    this.smokePpm,
    this.gasPpm,
    this.flameDetected,
    this.waterLevel,
    this.motionDetected,
    this.occupancy,
    this.batteryPct,
    this.rssiDbm,
    this.deviceHealth,
    this.deviceRisk,
    this.armedMode = '',
    this.faults = const [],
  });
  final String deviceId;
  final int? sequence;
  final DateTime? timestamp;
  final double? smokePpm;
  final double? gasPpm;
  final bool? flameDetected;
  final int? waterLevel;
  final bool? motionDetected;
  final bool? occupancy;
  final int? batteryPct;
  final int? rssiDbm;
  final String? deviceHealth;
  final int? deviceRisk;
  /// Arming mode reported by the device (§2 — system arming modes).
  final String armedMode;
  final List<String> faults;

  factory TelemetryEvent.fromJson(Map<String, dynamic> j) => TelemetryEvent(
        deviceId: j['device_id'] as String? ?? '',
        sequence: intOrNull(j['sequence']),
        timestamp: parseDateTime(j['timestamp']),
        smokePpm: doubleOf(j['smoke_ppm']),
        gasPpm: doubleOf(j['gas_ppm']),
        flameDetected: j['flame_detected'] as bool?,
        waterLevel: intOrNull(j['water_level']),
        motionDetected: j['motion_detected'] as bool?,
        occupancy: j['occupancy'] as bool?,
        batteryPct: intOrNull(j['battery_pct']),
        rssiDbm: intOrNull(j['rssi_dbm']),
        deviceHealth: j['device_health'] as String?,
        deviceRisk: intOrNull(j['device_risk']),
        armedMode: j['armed_mode'] as String? ?? '',
        faults: (j['faults'] as List<dynamic>? ?? const []).whereType<String>().toList(),
      );
}

/// Latest-status payload of `GET /api/v1/devices/{id}/status` (§5.2, docs/SPEC.md).
class DeviceStatus {
  const DeviceStatus({required this.device, this.propertyRiskLevel = 0, this.lastTelemetry});
  final Device device;
  final int propertyRiskLevel;
  final TelemetryEvent? lastTelemetry;

  factory DeviceStatus.fromJson(Map<String, dynamic> j) => DeviceStatus(
        device: Device.fromJson(j['device'] as Map<String, dynamic>),
        propertyRiskLevel: intOf(j['property_risk_level']),
        lastTelemetry: j['last_telemetry'] != null
            ? TelemetryEvent.fromJson(j['last_telemetry'] as Map<String, dynamic>)
            : null,
      );
}

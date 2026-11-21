import 'package:flutter_test/flutter_test.dart';
import 'package:iot_property_risk_mobile/core/models/alert.dart';
import 'package:iot_property_risk_mobile/core/models/device.dart';
import 'package:iot_property_risk_mobile/core/models/risk.dart';
import 'package:iot_property_risk_mobile/core/models/user.dart';

void main() {
  test('RiskLevel.fromSeverity maps backend severity names', () {
    expect(RiskLevel.fromSeverity('ok').value, 0);
    expect(RiskLevel.fromSeverity('notice').value, 1);
    expect(RiskLevel.fromSeverity('warning').value, 2);
    expect(RiskLevel.fromSeverity('alert').value, 3);
    expect(RiskLevel.fromSeverity('critical').value, 4);
    expect(RiskLevel.fromSeverity(null).value, 0);
  });

  test('Device.fromJson parses backend device payload', () {
    final d = Device.fromJson({
      'device_id': 'esp32-1',
      'property_id': 'prp_1',
      'name': 'Kitchen Smoke',
      'firmware_version': '1.0.0',
      'status': 'active',
      'risk_level': 2,
      'sensor_levels': {'smoke_gas': 2, 'flame': 0, 'water_leak': 0, 'motion': 0},
      'last_smoke_ppm': 350,
      'last_gas_ppm': 20,
      'last_flame_detected': false,
      'last_water_level': 0,
      'last_motion_detected': false,
      'last_occupancy': false,
      'battery_pct': 90,
      'device_health': 'ok',
      'faults': [],
    });
    expect(d.deviceId, 'esp32-1');
    expect(d.name, 'Kitchen Smoke');
    expect(d.riskLevel, 2);
    expect(d.sensorLevels['smoke_gas'], 2);
    expect(d.lastSmokePpm, 350.0);
  });

  test('DeviceStatus.fromJson parses status + last telemetry', () {
    final ds = DeviceStatus.fromJson({
      'device': {'device_id': 'esp32-1', 'status': 'active'},
      'property_risk_level': 2,
      'last_telemetry': {'device_id': 'esp32-1', 'sequence': 5, 'smoke_ppm': 350, 'device_risk': 2},
    });
    expect(ds.device.deviceId, 'esp32-1');
    expect(ds.propertyRiskLevel, 2);
    expect(ds.lastTelemetry?.sequence, 5);
    expect(ds.lastTelemetry?.smokePpm, 350.0);
  });

  test('Alert.fromJson parses alert payload', () {
    final a = Alert.fromJson({
      'id': 'alr_1',
      'property_id': 'prp_1',
      'device_id': 'esp32-1',
      'signal': 'smoke_gas',
      'severity': 'warning',
      'status': 'open',
    });
    expect(a.isOpen, true);
    expect(a.severity, 'warning');
  });

  test('User.roleOf maps property id to role', () {
    const u = User(
      id: 'u1',
      name: 'Alice',
      properties: [
        Property(id: 'prp_1', name: 'Home', riskLevel: 0, role: 'owner'),
        Property(id: 'prp_2', name: 'Garage', riskLevel: 1, role: 'viewer'),
      ],
    );
    expect(u.roleOf('prp_1'), 'owner');
    expect(u.roleOf('prp_2'), 'viewer');
    expect(u.roleOf('prp_other'), '');
  });
}

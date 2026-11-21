import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:flutter_test/flutter_test.dart';

import 'package:iot_property_risk_mobile/core/models/device.dart';
import 'package:iot_property_risk_mobile/core/models/user.dart';
import 'package:iot_property_risk_mobile/core/providers/api_provider.dart';
import 'package:iot_property_risk_mobile/core/providers/auth_provider.dart';
import 'package:iot_property_risk_mobile/core/providers/devices_provider.dart';
import 'package:iot_property_risk_mobile/ui/screens/device_detail_screen.dart';

import '../fakes.dart';

void main() {
  testWidgets('shows device card and all four sensor cards', (tester) async {
    final device = Device(
      deviceId: 'esp32-1',
      propertyId: 'prp_1',
      name: 'Kitchen Smoke',
      status: 'active',
      riskLevel: 2,
      sensorLevels: {'smoke_gas': 2, 'flame': 0, 'water_leak': 0, 'motion': 0},
      lastSmokePpm: 350.0,
      lastGasPpm: 20.0,
      lastFlameDetected: false,
      lastWaterLevel: 0,
      lastMotionDetected: false,
      lastOccupancy: false,
      batteryPct: 90,
    );
    final fake = FakeApiClient(devices: [device]);
    await tester.pumpWidget(ProviderScope(
      overrides: [
        apiProvider.overrideWith((ref) => fake),
        authProvider.overrideWith(
          (ref) => FakeAuthNotifier(fake, FakeTokenStore(), const User(id: 'u1', name: 'Alice', properties: [Property(id: 'prp_1', name: 'Home', role: 'owner')])),
        ),
        devicesProvider.overrideWith((ref) => FakeDevicesNotifier(fake, fake.devices)),
      ],
      child: MaterialApp(home: DeviceDetailScreen(deviceId: 'esp32-1')),
    ));
    await tester.pump();
    expect(find.text('Kitchen Smoke'), findsOneWidget);
    expect(find.text('Smoke / Gas'), findsOneWidget);
    expect(find.text('Flame'), findsOneWidget);
    expect(find.text('Water Leak'), findsOneWidget);
    expect(find.text('Motion'), findsOneWidget);
    expect(find.text('warning').evaluate().length, greaterThanOrEqualTo(1));
  });
}

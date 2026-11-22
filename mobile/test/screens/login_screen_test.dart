import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:flutter_test/flutter_test.dart';

import 'package:iot_property_risk_mobile/ui/app.dart';
import 'package:iot_property_risk_mobile/core/models/device.dart';
import 'package:iot_property_risk_mobile/core/providers/auth_provider.dart';
import 'package:iot_property_risk_mobile/core/providers/devices_provider.dart';

import '../fakes.dart';

void main() {
  testWidgets('login success navigates to Home with devices', (tester) async {
    final fake = FakeApiClient(devices: [
      Device(deviceId: 'esp32-1', propertyId: 'prp_1', name: 'Kitchen Smoke', status: 'active', riskLevel: 2),
    ]);
    await tester.pumpWidget(ProviderScope(
      overrides: [
        authProvider.overrideWith((ref) => FakeAuthNotifier(fake, FakeTokenStore(), null)),
        devicesProvider.overrideWith((ref) => FakeDevicesNotifier(fake, fake.devices)),
      ],
      child: const App(),
    ));
    await tester.pump();
    expect(find.byType(TextField), findsNWidgets(2));
    await tester.enterText(find.byType(TextField).at(0), 'a@b.c');
    await tester.enterText(find.byType(TextField).at(1), 'secret');
    await tester.tap(find.text('Log In'));
    await tester.pump(const Duration(milliseconds: 200));
    expect(find.text('Kitchen Smoke'), findsOneWidget);
  });

  testWidgets('login failure shows error', (tester) async {
    final fake = FakeApiClient(loginError: true);
    await tester.pumpWidget(ProviderScope(
      overrides: [
        authProvider.overrideWith((ref) => FakeAuthNotifier(fake, FakeTokenStore(), null)),
        devicesProvider.overrideWith((ref) => FakeDevicesNotifier(fake, fake.devices)),
      ],
      child: const App(),
    ));
    await tester.pump();
    await tester.enterText(find.byType(TextField).at(0), 'a@b.c');
    await tester.enterText(find.byType(TextField).at(1), 'secret');
    await tester.tap(find.text('Log In'));
    await tester.pump(const Duration(milliseconds: 200));
    expect(find.textContaining('Incorrect email or password'), findsOneWidget);
  });
}

import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:flutter_test/flutter_test.dart';

import 'package:iot_property_risk_mobile/core/models/user.dart';
import 'package:iot_property_risk_mobile/core/providers/api_provider.dart';
import 'package:iot_property_risk_mobile/core/providers/auth_provider.dart';
import 'package:iot_property_risk_mobile/core/providers/devices_provider.dart';
import 'package:iot_property_risk_mobile/ui/screens/home_screen.dart';

import '../fakes.dart';

void main() {
  testWidgets('mode picker switches system mode', (tester) async {
    final fake = FakeApiClient();
    final user = const User(id: 'u1', name: 'Alice', properties: [Property(id: 'prp_test', name: 'Home', role: 'owner')]);
    await tester.pumpWidget(ProviderScope(
      overrides: [
        apiProvider.overrideWith((ref) => fake),
        authProvider.overrideWith((ref) => FakeAuthNotifier(fake, FakeTokenStore(), user)),
        devicesProvider.overrideWith((ref) => FakeDevicesNotifier(fake, [])),
      ],
      child: const MaterialApp(home: HomeScreen()),
    ));
    await tester.pump();
    expect(find.text('Unarmed'), findsWidgets);
    await tester.tap(find.text('Armed'));
    await tester.pump(const Duration(milliseconds: 100));
    expect(fake.setSystemModes, contains('prp_test:armed'));
  });
}

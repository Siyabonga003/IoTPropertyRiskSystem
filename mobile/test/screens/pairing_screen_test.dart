import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:flutter_test/flutter_test.dart';

import 'package:iot_property_risk_mobile/core/providers/api_provider.dart';
import 'package:iot_property_risk_mobile/core/providers/devices_provider.dart';
import 'package:iot_property_risk_mobile/ui/screens/pairing_screen.dart';

import '../fakes.dart';

void main() {
  test('extractToken parses QR url', () {
    expect(PairingScreen.extractToken('https://host/pair?token=pt_abc'), 'pt_abc');
    expect(PairingScreen.extractToken('https://host/pair?t=pt_abc2'), 'pt_abc2');
    expect(PairingScreen.extractToken('  pt_xyz  '), 'pt_xyz');
  });

  testWidgets('manual token claim calls API', (tester) async {
    final fake = FakeApiClient(claimResult: {'device_id': 'esp32-9', 'property_id': 'prp_1', 'device_token': 'dt_fake'});
    await tester.pumpWidget(ProviderScope(
      overrides: [
        apiProvider.overrideWith((ref) => fake),
        devicesProvider.overrideWith((ref) => FakeDevicesNotifier(fake, fake.devices)),
      ],
      child: MaterialApp(home: PairingScreen()),
    ));
    await tester.pump();
    await tester.enterText(find.byType(TextField), 'pt_abc123');
    await tester.tap(find.text('Claim Device'));
    await tester.pump(const Duration(milliseconds: 100));
    expect(fake.claimedTokens, contains('pt_abc123'));
  });

  testWidgets('empty claim shows error', (tester) async {
    final fake = FakeApiClient();
    await tester.pumpWidget(ProviderScope(
      overrides: [
        apiProvider.overrideWith((ref) => fake),
        devicesProvider.overrideWith((ref) => FakeDevicesNotifier(fake, fake.devices)),
      ],
      child: MaterialApp(home: PairingScreen()),
    ));
    await tester.pump();
    await tester.tap(find.text('Claim Device'));
    await tester.pump(const Duration(milliseconds: 100));
    expect(find.textContaining('Enter a pairing token'), findsOneWidget);
    expect(fake.claimedTokens, isEmpty);
  });
}

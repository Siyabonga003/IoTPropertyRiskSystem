import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:flutter_test/flutter_test.dart';

import 'package:iot_property_risk_mobile/core/models/alert.dart';
import 'package:iot_property_risk_mobile/core/models/user.dart';
import 'package:iot_property_risk_mobile/core/providers/alerts_provider.dart';
import 'package:iot_property_risk_mobile/core/providers/api_provider.dart';
import 'package:iot_property_risk_mobile/core/providers/auth_provider.dart';
import 'package:iot_property_risk_mobile/ui/screens/alerts_screen.dart';
import 'package:iot_property_risk_mobile/ui/widgets/alert_tile.dart';

import '../fakes.dart';

void main() {
  testWidgets('lists open alerts, filters by sensor, acks', (tester) async {
    final smokeAlert = Alert(id: 'alr_1', propertyId: 'prp_1', deviceId: 'esp32-1', signal: 'smoke_gas', severity: 'warning', status: 'open');
    final flameAlert = Alert(id: 'alr_2', propertyId: 'prp_1', deviceId: 'esp32-2', signal: 'flame', severity: 'critical', status: 'open');
    final fake = FakeApiClient(alerts: [smokeAlert, flameAlert]);
    final user = const User(id: 'u1', name: 'Alice', properties: [Property(id: 'prp_1', name: 'Home', riskLevel: 3, role: 'owner')]);
    await tester.pumpWidget(ProviderScope(
      overrides: [
        apiProvider.overrideWith((ref) => fake),
        authProvider.overrideWith((ref) => FakeAuthNotifier(fake, FakeTokenStore(), user)),
        alertsProvider.overrideWith((ref) => FakeAlertsNotifier(fake, fake.alerts)),
      ],
      child: const MaterialApp(home: AlertsScreen()),
    ));
    await tester.pump();
    expect(find.byType(AlertTile), findsNWidgets(2));
    expect(find.text('Smoke / Gas'), findsOneWidget);
    // Filter to Flame — tap the segmented chip (first 'Flame' text = the chip, before the tiles).
    await tester.tap(find.text('Flame').first);
    await tester.pump();
    expect(find.byType(AlertTile), findsOneWidget);
    expect(find.text('Smoke / Gas'), findsNothing);
    // Ack the flame alert.
    await tester.tap(find.text('Ack'));
    await tester.pump(const Duration(milliseconds: 100));
    expect(fake.ackedAlerts, contains('alr_2'));
  });
}

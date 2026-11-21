import 'dart:async';

import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';

import '../../core/models/alert.dart';
import '../../core/models/risk.dart';
import '../../core/providers/alerts_provider.dart';
import '../../core/providers/api_provider.dart';
import '../../core/providers/auth_provider.dart';
import '../signal_labels.dart';
import '../utils.dart';
import '../widgets/alert_tile.dart';
import '../widgets/risk_badge.dart';

/// Active alerts screen: filterable by sensor type + ack (§3.4, docs/SPEC.md).
class AlertsScreen extends ConsumerStatefulWidget {
  const AlertsScreen({super.key});
  @override
  ConsumerState<AlertsScreen> createState() => _AlertsScreenState();
}

class _AlertsScreenState extends ConsumerState<AlertsScreen> {
  Timer? _timer;
  String filter = 'all'; // 'all' | 'smoke_gas' | 'flame' | 'water_leak' | 'motion'

  @override
  void initState() {
    super.initState();
    _timer = Timer.periodic(const Duration(seconds: 3), (_) => ref.read(alertsProvider.notifier).refresh());
  }

  @override
  void dispose() {
    _timer?.cancel();
    super.dispose();
  }

  @override
  Widget build(BuildContext context) {
    final user = ref.watch(authProvider).user;
    final active = ref
        .watch(alertsProvider)
        .where((a) => a.status != 'resolved' && (filter == 'all' || a.signal == filter))
        .toList();
    bool canAck(Alert a) => {'owner', 'admin', 'responder'}.contains(user?.roleOf(a.propertyId) ?? '');
    return Scaffold(
      appBar: AppBar(title: const Text('Alerts')),
      body: Column(
        children: [
          SegmentedButton<String>(
            segments: [
              ButtonSegment(value: 'all', label: const Text('All')),
              ButtonSegment(value: 'smoke_gas', label: const Text('Smoke/Gas')),
              ButtonSegment(value: 'flame', label: const Text('Flame')),
              ButtonSegment(value: 'water_leak', label: const Text('Water')),
              ButtonSegment(value: 'motion', label: const Text('Motion')),
            ],
            selected: {filter},
            onSelectionChanged: (sel) => setState(() => filter = sel.first),
          ),
          Expanded(
            child: active.isEmpty
                ? const Center(child: Text('No active alerts'))
                : ListView.builder(
                    itemCount: active.length,
                    itemBuilder: (_, i) => AlertTile(
                      alert: active[i],
                      canAck: canAck(active[i]),
                      onTap: () => Navigator.of(context).push(
                        MaterialPageRoute(builder: (_) => AlertDetailScreen(alert: active[i])),
                      ),
                      onAck: () {
                        ref.read(apiProvider).ackAlert(active[i].id);
                        ref.read(alertsProvider.notifier).refresh();
                        ScaffoldMessenger.of(context).showSnackBar(const SnackBar(content: Text('Acknowledged')));
                      },
                    ),
                  ),
          ),
        ],
      ),
    );
  }
}

/// Alert detail screen with acknowledge action.
class AlertDetailScreen extends ConsumerWidget {
  const AlertDetailScreen({super.key, required this.alert});
  final Alert alert;

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    final role = ref.watch(authProvider).user?.roleOf(alert.propertyId) ?? '';
    final canAck = role == 'owner' || role == 'admin' || role == 'responder';
    return Scaffold(
      appBar: AppBar(title: Text(signalLabel(alert.signal))),
      body: ListView(
        padding: const EdgeInsets.all(16),
        children: [
          ListTile(
            leading: RiskBadge(level: RiskLevel.fromSeverity(alert.severity)),
            title: const Text('Severity'),
            subtitle: Text(alert.severity),
          ),
          ListTile(title: const Text('Status'), subtitle: Text(alert.status)),
          ListTile(title: const Text('Device'), subtitle: Text(alert.deviceId)),
          ListTile(title: const Text('Property'), subtitle: Text(alert.propertyId)),
          ListTile(title: const Text('First seen'), subtitle: Text(formatTime(alert.firstSeenAt))),
          ListTile(title: const Text('Last seen'), subtitle: Text(formatTime(alert.lastSeenAt))),
          if (alert.acknowledgedAt != null)
            ListTile(title: const Text('Acknowledged'), subtitle: Text(formatTime(alert.acknowledgedAt))),
          if (alert.resolvedAt != null)
            ListTile(title: const Text('Resolved'), subtitle: Text(formatTime(alert.resolvedAt))),
          if (alert.notes.isNotEmpty) ListTile(title: const Text('Notes'), subtitle: Text(alert.notes)),
          if (canAck && alert.isOpen)
            TextButton(
              onPressed: () {
                ref.read(apiProvider).ackAlert(alert.id);
                ref.read(alertsProvider.notifier).refresh();
                Navigator.of(context).pop();
              },
              child: const Text('Acknowledge'),
            ),
        ],
      ),
    );
  }
}

import 'dart:async';

import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';

import '../../core/api_client.dart';
import '../../core/models/alert.dart';
import '../../core/models/risk.dart';
import '../../core/models/system_mode.dart';
import '../../core/providers/alerts_provider.dart';
import '../../core/providers/api_provider.dart';
import '../../core/providers/auth_provider.dart';
import '../signal_labels.dart';
import '../utils.dart';
import '../widgets/alert_tile.dart';
import '../widgets/risk_badge.dart';

const _filters = <(String, String)>[
  ('all', 'All'),
  ('smoke_gas', 'Smoke/Gas'),
  ('flame', 'Flame'),
  ('water_leak', 'Water'),
  ('motion', 'Motion'),
  ('sensor_fault', 'Faults'),
  ('device_disconnected', 'Offline'),
];

/// Active alerts screen: filterable by sensor type + ack (SPEC §2/§4).
class AlertsScreen extends ConsumerStatefulWidget {
  const AlertsScreen({super.key});
  @override
  ConsumerState<AlertsScreen> createState() => _AlertsScreenState();
}

class _AlertsScreenState extends ConsumerState<AlertsScreen> {
  Timer? _timer;
  String _filter = 'all';
  final Set<String> _acking = {};

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

  Future<void> _ack(Alert alert) async {
    if (_acking.contains(alert.id)) return;
    setState(() => _acking.add(alert.id));
    try {
      await ref.read(apiProvider).ackAlert(alert.id);
      await ref.read(alertsProvider.notifier).refresh();
      if (!mounted) return;
      ScaffoldMessenger.of(context).showSnackBar(const SnackBar(content: Text('Alert acknowledged')));
    } catch (error) {
      if (!mounted) return;
      ScaffoldMessenger.of(context).showSnackBar(SnackBar(content: Text(apiErrorMessage(error))));
    } finally {
      if (mounted) setState(() => _acking.remove(alert.id));
    }
  }

  @override
  Widget build(BuildContext context) {
    final user = ref.watch(authProvider).user;
    final state = ref.watch(alertsProvider);
    final active = state.active.where((a) => _filter == 'all' || a.signal == _filter).toList();
    bool canAck(Alert a) => {'owner', 'admin', 'responder'}.contains(user?.roleOf(a.propertyId) ?? '');
    return Scaffold(
      appBar: AppBar(
        title: const Text('Alerts'),
        actions: [
          IconButton(
            tooltip: 'Refresh',
            onPressed: () => ref.read(alertsProvider.notifier).refresh(showLoading: true),
            icon: const Icon(Icons.refresh),
          ),
        ],
      ),
      body: Column(
        children: [
          if (state.error != null)
            Container(
              width: double.infinity,
              color: Theme.of(context).colorScheme.errorContainer,
              padding: const EdgeInsets.symmetric(horizontal: 16, vertical: 8),
              child: Text(state.error!, style: TextStyle(color: Theme.of(context).colorScheme.onErrorContainer)),
            ),
          SingleChildScrollView(
            scrollDirection: Axis.horizontal,
            padding: const EdgeInsets.fromLTRB(12, 8, 12, 4),
            child: Row(
              children: [
                for (final (value, label) in _filters)
                  Padding(
                    padding: const EdgeInsets.symmetric(horizontal: 4),
                    child: ChoiceChip(
                      label: Text(label),
                      selected: _filter == value,
                      onSelected: (_) => setState(() => _filter = value),
                    ),
                  ),
              ],
            ),
          ),
          Expanded(
            child: state.loading && state.items.isEmpty
                ? const Center(child: CircularProgressIndicator())
                : state.error != null && state.items.isEmpty
                    ? Center(
                        child: Padding(
                          padding: const EdgeInsets.all(24),
                          child: Column(
                            mainAxisSize: MainAxisSize.min,
                            children: [
                              const Icon(Icons.cloud_off, size: 48),
                              const SizedBox(height: 12),
                              Text(state.error!, textAlign: TextAlign.center),
                              const SizedBox(height: 12),
                              FilledButton(
                                onPressed: () => ref.read(alertsProvider.notifier).refresh(showLoading: true),
                                child: const Text('Retry'),
                              ),
                            ],
                          ),
                        ),
                      )
                    : active.isEmpty
                        ? Center(
                            child: Text(
                              state.items.isEmpty ? 'No alerts yet' : 'No active alerts for this filter',
                              style: Theme.of(context).textTheme.bodyMedium,
                            ),
                          )
                        : RefreshIndicator(
                        onRefresh: () => ref.read(alertsProvider.notifier).refresh(),
                        child: ListView.builder(
                          physics: const AlwaysScrollableScrollPhysics(),
                          padding: const EdgeInsets.only(bottom: 16),
                          itemCount: active.length,
                          itemBuilder: (_, i) => AlertTile(
                            alert: active[i],
                            canAck: canAck(active[i]),
                            busy: _acking.contains(active[i].id),
                            onTap: () => Navigator.of(context).push(
                              MaterialPageRoute(builder: (_) => AlertDetailScreen(alert: active[i])),
                            ),
                            onAck: () => _ack(active[i]),
                          ),
                        ),
                      ),
          ),
        ],
      ),
    );
  }
}

/// Alert detail screen with acknowledge action.
class AlertDetailScreen extends ConsumerStatefulWidget {
  const AlertDetailScreen({super.key, required this.alert});
  final Alert alert;

  @override
  ConsumerState<AlertDetailScreen> createState() => _AlertDetailScreenState();
}

class _AlertDetailScreenState extends ConsumerState<AlertDetailScreen> {
  bool _busy = false;
  String? _error;

  Future<void> _ack() async {
    if (_busy) return;
    setState(() {
      _busy = true;
      _error = null;
    });
    try {
      await ref.read(apiProvider).ackAlert(widget.alert.id);
      await ref.read(alertsProvider.notifier).refresh();
      if (!mounted) return;
      ScaffoldMessenger.of(context).showSnackBar(const SnackBar(content: Text('Alert acknowledged')));
      Navigator.of(context).pop();
    } catch (error) {
      if (!mounted) return;
      final message = apiErrorMessage(error);
      setState(() => _error = message);
      ScaffoldMessenger.of(context).showSnackBar(SnackBar(content: Text(message)));
    } finally {
      if (mounted) setState(() => _busy = false);
    }
  }

  @override
  Widget build(BuildContext context) {
    final alert = widget.alert;
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
          ListTile(
            leading: const Icon(Icons.shield_outlined),
            title: const Text('Arming mode when raised'),
            subtitle: Text('${modeLabel(alert.systemMode)} — ${modeDescription(alert.systemMode)}'),
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
          if (_error != null)
            Padding(
              padding: const EdgeInsets.symmetric(vertical: 8),
              child: Text(_error!, style: TextStyle(color: Theme.of(context).colorScheme.error)),
            ),
          if (canAck && alert.isOpen)
            FilledButton.icon(
              onPressed: _busy ? null : _ack,
              icon: _busy
                  ? const SizedBox(width: 16, height: 16, child: CircularProgressIndicator(strokeWidth: 2))
                  : const Icon(Icons.check),
              label: Text(_busy ? 'Acknowledging…' : 'Acknowledge'),
            )
          else if (alert.isOpen)
            Text(
              'Only owners, admins and responders can acknowledge alerts.',
              style: Theme.of(context).textTheme.bodySmall,
            ),
        ],
      ),
    );
  }
}

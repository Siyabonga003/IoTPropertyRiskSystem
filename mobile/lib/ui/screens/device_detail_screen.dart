import 'dart:async';

import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';

import '../../core/api_client.dart';
import '../../core/models/device.dart';
import '../../core/providers/api_provider.dart';
import '../../core/providers/auth_provider.dart';
import '../../core/providers/devices_provider.dart';
import '../utils.dart';
import '../widgets/device_info_card.dart';
import '../widgets/sensor_card.dart';
import 'alerts_screen.dart';

/// Live device monitoring: readings + risk badge per sensor (§1, docs/SPEC.md).
class DeviceDetailScreen extends ConsumerStatefulWidget {
  const DeviceDetailScreen({super.key, required this.deviceId});
  final String deviceId;

  @override
  ConsumerState<DeviceDetailScreen> createState() => _DeviceDetailScreenState();
}

class _DeviceDetailScreenState extends ConsumerState<DeviceDetailScreen> {
  Timer? _timer;
  DeviceStatus? _status;
  bool _loading = true;
  bool _refreshing = false;
  bool _revoking = false;
  String? _error;

  @override
  void initState() {
    super.initState();
    _timer = Timer.periodic(const Duration(seconds: 5), (_) => _refresh());
    unawaited(_refresh());
  }

  @override
  void dispose() {
    _timer?.cancel();
    super.dispose();
  }

  /// Live monitoring (SPEC §4): poll `GET /api/v1/devices/{id}/status` every 5 s.
  Future<void> _refresh() async {
    if (_refreshing) return;
    _refreshing = true;
    try {
      final status = await ref.read(apiProvider).fetchDeviceStatus(widget.deviceId);
      if (!mounted) return;
      setState(() {
        _status = status;
        _error = null;
      });
    } catch (error) {
      if (!mounted) return;
      setState(() => _error = apiErrorMessage(error));
    } finally {
      _refreshing = false;
      if (mounted && _loading) setState(() => _loading = false);
    }
  }

  Device? _deviceFromState(DevicesState state) {
    if (_status != null) return _status!.device;
    for (final device in state.items) {
      if (device.deviceId == widget.deviceId) return device;
    }
    return null;
  }

  Future<void> _revoke() async {
    final confirmed = await showDialog<bool>(
      context: context,
      builder: (dialogContext) => AlertDialog(
        title: const Text('Revoke device?'),
        content: const Text('The device will stop sending telemetry and must be paired again.'),
        actions: [
          TextButton(onPressed: () => Navigator.of(dialogContext).pop(false), child: const Text('Cancel')),
          FilledButton(onPressed: () => Navigator.of(dialogContext).pop(true), child: const Text('Revoke')),
        ],
      ),
    );
    if (confirmed != true || !mounted) return;
    setState(() => _revoking = true);
    try {
      await ref.read(apiProvider).revokeDevice(widget.deviceId);
      await ref.read(devicesProvider.notifier).refresh();
      if (!mounted) return;
      ScaffoldMessenger.of(context).showSnackBar(const SnackBar(content: Text('Device revoked')));
      Navigator.of(context).pop();
    } catch (error) {
      if (!mounted) return;
      ScaffoldMessenger.of(context).showSnackBar(SnackBar(content: Text(apiErrorMessage(error))));
    } finally {
      if (mounted) setState(() => _revoking = false);
    }
  }

  @override
  Widget build(BuildContext context) {
    final state = ref.watch(devicesProvider);
    final device = _deviceFromState(state);
    final role = ref.watch(authProvider).user?.roleOf(device?.propertyId ?? '') ?? '';
    if (device == null) {
      return Scaffold(
        appBar: AppBar(title: const Text('Device')),
        body: _loading
            ? const Center(child: CircularProgressIndicator())
            : _error != null
                ? _RetryMessage(message: _error!, onRetry: _refresh)
                : const Center(child: Text('Device not found')),
      );
    }
    final telemetry = _status?.lastTelemetry;
    return Scaffold(
      appBar: AppBar(
        title: const Text('Device'),
        actions: [
          IconButton(
            icon: const Icon(Icons.list_alt),
            onPressed: () => Navigator.of(context).push(MaterialPageRoute(builder: (_) => const AlertsScreen())),
            tooltip: 'Alerts',
          ),
          if (role == 'owner' || role == 'admin')
            IconButton(
              icon: _revoking
                  ? const SizedBox(width: 18, height: 18, child: CircularProgressIndicator(strokeWidth: 2))
                  : const Icon(Icons.delete_forever),
              onPressed: _revoking ? null : _revoke,
              tooltip: 'Revoke device',
            ),
        ],
      ),
      body: RefreshIndicator(
        onRefresh: _refresh,
        child: ListView(
          physics: const AlwaysScrollableScrollPhysics(),
          padding: const EdgeInsets.only(bottom: 24),
          children: [
            if (device.status != 'active')
              _Notice(
                icon: Icons.sensors_off,
                message: device.status == 'disconnected'
                    ? 'Device is disconnected. Readings below are the last known values.'
                    : 'Device status: ${device.status}.',
              ),
            if (_error != null) _Notice(icon: Icons.cloud_off, message: _error!, action: TextButton(onPressed: _refresh, child: const Text('Retry'))),
            DeviceInfoCard(device: device),
            if (telemetry != null)
              Padding(
                padding: const EdgeInsets.fromLTRB(16, 0, 16, 4),
                child: Text(
                  'Latest reading #${telemetry.sequence ?? '-'} at ${formatTime(telemetry.timestamp)}',
                  style: Theme.of(context).textTheme.bodySmall,
                ),
              ),
            SensorCard(
              title: 'Smoke / Gas',
              risk: signalRisk(device, 'smoke_gas'),
              details: 'Smoke: ${ppmOf(device.lastSmokePpm)} · Gas: ${ppmOf(device.lastGasPpm)}',
              faults: device.faults.where((f) => f.contains('smoke') || f.contains('gas')).toList(),
            ),
            SensorCard(
              title: 'Flame',
              risk: signalRisk(device, 'flame'),
              details: device.lastFlameDetected == true ? 'Flame detected' : 'No flame detected',
              faults: device.faults.where((f) => f.contains('flame')).toList(),
            ),
            SensorCard(
              title: 'Water Leak',
              risk: signalRisk(device, 'water_leak'),
              details: (device.lastWaterLevel ?? 0) > 0
                  ? 'Leak detected — level ${device.lastWaterLevel}%'
                  : 'No leak detected',
              faults: device.faults.where((f) => f.contains('water')).toList(),
            ),
            SensorCard(
              title: 'Motion',
              risk: signalRisk(device, 'motion'),
              details: '${device.lastMotionDetected == true ? 'Motion detected' : 'No motion'} · '
                  'Occupancy: ${device.lastOccupancy == true ? 'yes' : 'no'}',
              faults: device.faults.where((f) => f.contains('motion')).toList(),
            ),
          ],
        ),
      ),
    );
  }
}

class _Notice extends StatelessWidget {
  const _Notice({required this.icon, required this.message, this.action});
  final IconData icon;
  final String message;
  final Widget? action;

  @override
  Widget build(BuildContext context) {
    return Card(
      color: Theme.of(context).colorScheme.surfaceContainerHighest,
      margin: const EdgeInsets.fromLTRB(16, 8, 16, 4),
      child: Padding(
        padding: const EdgeInsets.symmetric(horizontal: 12, vertical: 8),
        child: Row(
          children: [
            Icon(icon, size: 18),
            const SizedBox(width: 8),
            Expanded(child: Text(message, style: Theme.of(context).textTheme.bodySmall)),
            if (action != null) action!,
          ],
        ),
      ),
    );
  }
}

class _RetryMessage extends StatelessWidget {
  const _RetryMessage({required this.message, required this.onRetry});
  final String message;
  final VoidCallback onRetry;

  @override
  Widget build(BuildContext context) {
    return Center(
      child: Padding(
        padding: const EdgeInsets.all(24),
        child: Column(
          mainAxisSize: MainAxisSize.min,
          children: [
            const Icon(Icons.cloud_off, size: 48),
            const SizedBox(height: 12),
            Text(message, textAlign: TextAlign.center),
            const SizedBox(height: 12),
            FilledButton(onPressed: onRetry, child: const Text('Retry')),
          ],
        ),
      ),
    );
  }
}

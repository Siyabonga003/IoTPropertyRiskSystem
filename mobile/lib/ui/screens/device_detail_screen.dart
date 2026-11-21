import 'dart:async';

import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';

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

  /// Live monitoring (SPEC §5): poll `GET /api/v1/devices/{id}/status` every 5 s.
  Future<void> _refresh() async {
    try {
      final st = await ref.read(apiProvider).fetchDeviceStatus(widget.deviceId);
      if (!mounted) return;
      setState(() => _status = st);
    } catch (_) {
      // Retry on next poll.
    }
  }

  Device? get _device {
    final status = _status;
    if (status != null) return status.device;
    for (final d in ref.watch(devicesProvider)) {
      if (d.deviceId == widget.deviceId) return d;
    }
    return null;
  }

  Future<void> _revoke() async {
    await ref.read(apiProvider).revokeDevice(widget.deviceId);
    ref.read(devicesProvider.notifier).refresh();
  }

  @override
  Widget build(BuildContext context) {
    final device = _device;
    final role = ref.watch(authProvider).user?.roleOf(device?.propertyId ?? '') ?? '';
    if (device == null) {
      return Scaffold(appBar: AppBar(title: const Text('Device')), body: const Center(child: Text('Device not found')));
    }
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
            IconButton(icon: const Icon(Icons.delete_forever), onPressed: _revoke, tooltip: 'Revoke device'),
        ],
      ),
      body: SingleChildScrollView(
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            DeviceInfoCard(device: device),
            SensorCard(
              title: 'Smoke / Gas',
              risk: signalRisk(device, 'smoke_gas'),
              details: 'Smoke: ${ppmOf(device.lastSmokePpm)}, Gas: ${ppmOf(device.lastGasPpm)}',
              faults: device.faults.where((f) => f.contains('smoke') || f.contains('gas')).toList(),
            ),
            SensorCard(
              title: 'Flame',
              risk: signalRisk(device, 'flame'),
              details: 'Flame: ${device.lastFlameDetected == true ? 'detected' : 'not detected'}',
              faults: device.faults.where((f) => f.contains('flame')).toList(),
            ),
            SensorCard(
              title: 'Water Leak',
              risk: signalRisk(device, 'water_leak'),
              details: 'Level: ${device.lastWaterLevel ?? 0}',
              faults: device.faults.where((f) => f.contains('water')).toList(),
            ),
            SensorCard(
              title: 'Motion',
              risk: signalRisk(device, 'motion'),
              details: 'Motion: ${device.lastMotionDetected == true ? 'yes' : 'no'}, Occupancy: ${device.lastOccupancy == true ? 'yes' : 'no'}',
              faults: device.faults.where((f) => f.contains('motion')).toList(),
            ),
          ],
        ),
      ),
    );
  }
}

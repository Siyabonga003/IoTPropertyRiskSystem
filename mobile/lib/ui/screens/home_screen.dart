import 'dart:async';

import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';

import '../../core/models/device.dart';
import '../../core/models/user.dart';
import '../../core/providers/alerts_provider.dart';
import '../../core/providers/auth_provider.dart';
import '../../core/providers/devices_provider.dart';
import '../utils.dart';
import '../widgets/device_tile.dart';
import '../widgets/mode_picker.dart';
import '../widgets/risk_badge.dart';
import 'alerts_screen.dart';
import 'device_detail_screen.dart';
import 'pairing_screen.dart';

/// Device list screen — the app's home.
class HomeScreen extends ConsumerStatefulWidget {
  const HomeScreen({super.key});
  @override
  ConsumerState<HomeScreen> createState() => _HomeScreenState();
}

class _HomeScreenState extends ConsumerState<HomeScreen> {
  Timer? _timer;

  @override
  void initState() {
    super.initState();
    _timer = Timer.periodic(const Duration(seconds: 5), (_) => _refresh());
  }

  @override
  void dispose() {
    _timer?.cancel();
    super.dispose();
  }

  Future<void> _refresh() async {
    await Future.wait([
      ref.read(devicesProvider.notifier).refresh(),
      ref.read(alertsProvider.notifier).refresh(),
    ]);
  }

  @override
  Widget build(BuildContext context) {
    final user = ref.watch(authProvider).user;
    if (user == null) return const SizedBox();
    final devicesState = ref.watch(devicesProvider);
    final alertsState = ref.watch(alertsProvider);
    final openAlerts = alertsState.active.length;
    final canAdd = user.properties.any((p) => p.role == 'owner' || p.role == 'admin');
    final error = devicesState.error ?? alertsState.error;
    return Scaffold(
      appBar: AppBar(
        title: const Text('IoT Property Risk'),
        actions: [
          IconButton(
            tooltip: 'Alerts',
            onPressed: () => Navigator.of(context).push(MaterialPageRoute(builder: (_) => const AlertsScreen())),
            icon: Badge.count(
              count: openAlerts,
              isLabelVisible: openAlerts > 0,
              child: const Icon(Icons.notifications_outlined),
            ),
          ),
          IconButton(
            tooltip: 'Sign out',
            icon: const Icon(Icons.logout),
            onPressed: () => ref.read(authProvider.notifier).logout(),
          ),
        ],
      ),
      body: RefreshIndicator(
        onRefresh: _refresh,
        child: ListView(
          physics: const AlwaysScrollableScrollPhysics(),
          padding: const EdgeInsets.symmetric(vertical: 12),
          children: [
            if (error != null)
              _ErrorBanner(message: error, onRetry: _refresh),
            if (devicesState.loading && devicesState.items.isEmpty)
              const Padding(
                padding: EdgeInsets.symmetric(vertical: 64),
                child: Center(child: CircularProgressIndicator()),
              )
            else if (user.properties.isEmpty)
              _EmptyDevices(canAdd: canAdd)
            else
              ..._buildPropertySections(user, devicesState.items),
          ],
        ),
      ),
      floatingActionButton: canAdd
          ? FloatingActionButton.extended(
              onPressed: () => Navigator.of(context).push(MaterialPageRoute(builder: (_) => const PairingScreen())),
              icon: const Icon(Icons.qr_code_scanner),
              label: const Text('Pair device'),
            )
          : null,
    );
  }

  List<Widget> _buildPropertySections(User user, List<Device> devices) {
    final byProperty = <String, List<Device>>{};
    for (final device in devices) {
      byProperty.putIfAbsent(device.propertyId ?? '', () => []).add(device);
    }
    final widgets = <Widget>[];
    final known = <String>{};
    for (final property in user.properties) {
      known.add(property.id);
      final propertyDevices = byProperty[property.id] ?? const <Device>[];
      widgets.add(_PropertySection(property: property, devices: propertyDevices));
    }
    final other = byProperty.entries.where((e) => !known.contains(e.key)).expand((e) => e.value).toList();
    if (other.isNotEmpty) {
      widgets.add(const Padding(
        padding: EdgeInsets.fromLTRB(20, 16, 20, 4),
        child: Text('Other devices', style: TextStyle(fontWeight: FontWeight.bold)),
      ));
      widgets.addAll(other.map(_deviceTile));
    }
    return widgets;
  }

  Widget _deviceTile(Device device) => DeviceTile(
        device: device,
        onTap: () => Navigator.of(context).push(
          MaterialPageRoute(builder: (_) => DeviceDetailScreen(deviceId: device.deviceId)),
        ),
      );
}

class _PropertySection extends StatelessWidget {
  const _PropertySection({required this.property, required this.devices});
  final Property property;
  final List<Device> devices;

  @override
  Widget build(BuildContext context) {
    return Column(
      crossAxisAlignment: CrossAxisAlignment.start,
      children: [
        Card(
          margin: const EdgeInsets.fromLTRB(16, 8, 16, 4),
          child: Padding(
            padding: const EdgeInsets.all(14),
            child: Column(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                Row(
                  children: [
                    const Icon(Icons.home_outlined, size: 20),
                    const SizedBox(width: 8),
                    Expanded(
                      child: Text(property.name, style: Theme.of(context).textTheme.titleMedium?.copyWith(fontWeight: FontWeight.bold)),
                    ),
                    if (property.riskLevel > 0) RiskBadge(level: riskLevelOf(property.riskLevel)),
                  ],
                ),
                const SizedBox(height: 12),
                ModePicker(property: property),
              ],
            ),
          ),
        ),
        if (devices.isEmpty)
          const Padding(
            padding: EdgeInsets.fromLTRB(24, 4, 24, 12),
            child: Text('No devices paired to this property yet.'),
          )
        else
          ...devices.map(
            (d) => DeviceTile(
              device: d,
              onTap: () => Navigator.of(context).push(
                MaterialPageRoute(builder: (_) => DeviceDetailScreen(deviceId: d.deviceId)),
              ),
            ),
          ),
      ],
    );
  }
}

class _ErrorBanner extends StatelessWidget {
  const _ErrorBanner({required this.message, required this.onRetry});
  final String message;
  final VoidCallback onRetry;

  @override
  Widget build(BuildContext context) {
    return Card(
      color: Theme.of(context).colorScheme.errorContainer,
      margin: const EdgeInsets.fromLTRB(16, 8, 16, 4),
      child: Padding(
        padding: const EdgeInsets.symmetric(horizontal: 12, vertical: 8),
        child: Row(
          children: [
            Icon(Icons.cloud_off, color: Theme.of(context).colorScheme.onErrorContainer),
            const SizedBox(width: 8),
            Expanded(child: Text(message, style: TextStyle(color: Theme.of(context).colorScheme.onErrorContainer))),
            TextButton(onPressed: onRetry, child: const Text('Retry')),
          ],
        ),
      ),
    );
  }
}

class _EmptyDevices extends StatelessWidget {
  const _EmptyDevices({required this.canAdd});
  final bool canAdd;

  @override
  Widget build(BuildContext context) {
    return Padding(
      padding: const EdgeInsets.fromLTRB(24, 64, 24, 24),
      child: Column(
        children: [
          Icon(Icons.sensors_off, size: 56, color: Theme.of(context).colorScheme.outline),
          const SizedBox(height: 12),
          Text('No devices yet', style: Theme.of(context).textTheme.titleMedium),
          const SizedBox(height: 4),
          Text(
            canAdd ? 'Pair your first ESP32 device to start monitoring.' : 'Ask an owner or admin to pair a device.',
            textAlign: TextAlign.center,
            style: Theme.of(context).textTheme.bodySmall,
          ),
        ],
      ),
    );
  }
}

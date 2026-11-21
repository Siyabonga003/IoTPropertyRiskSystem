import 'dart:async';

import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';

import '../../core/providers/auth_provider.dart';
import '../../core/providers/devices_provider.dart';
import '../widgets/device_tile.dart';
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
    _timer = Timer.periodic(const Duration(seconds: 5), (_) => ref.read(devicesProvider.notifier).refresh());
  }

  @override
  void dispose() {
    _timer?.cancel();
    super.dispose();
  }

  @override
  Widget build(BuildContext context) {
    final user = ref.watch(authProvider).user;
    if (user == null) return const SizedBox();
    final devices = ref.watch(devicesProvider);
    final canAdd = user.properties.any((p) => p.role == 'owner' || p.role == 'admin');
    return Scaffold(
      appBar: AppBar(
        title: const Text('IoT Property Risk'),
        actions: [
          IconButton(icon: const Icon(Icons.logout), onPressed: () => ref.read(authProvider.notifier).logout()),
        ],
      ),
      body: ListView(
        padding: const EdgeInsets.symmetric(vertical: 16),
        children: [
          if (devices.isEmpty) const Padding(padding: EdgeInsets.all(24), child: Text('No devices yet')),
          for (final d in devices)
            DeviceTile(
              device: d,
              onTap: () =>
                  Navigator.of(context).push(MaterialPageRoute(builder: (_) => DeviceDetailScreen(deviceId: d.deviceId))),
            ),
        ],
      ),
      floatingActionButton: canAdd
          ? FloatingActionButton(
              onPressed: () => Navigator.of(context).push(MaterialPageRoute(builder: (_) => const PairingScreen())),
              child: const Icon(Icons.qr_code_scanner),
            )
          : null,
    );
  }
}

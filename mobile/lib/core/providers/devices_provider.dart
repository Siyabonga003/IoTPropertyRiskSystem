import 'package:flutter_riverpod/flutter_riverpod.dart';

import '../api_client.dart';
import '../models/device.dart';
import 'api_provider.dart';

class DevicesNotifier extends StateNotifier<List<Device>> {
  DevicesNotifier(ApiClient api) : _api = api, super(const []) {
    refresh();
  }
  final ApiClient _api;

  Future<void> refresh() async {
    try {
      state = await _api.listDevices();
    } catch (_) {
      // Retry on next poll.
    }
  }
}

final devicesProvider = StateNotifierProvider<DevicesNotifier, List<Device>>(
  (ref) => DevicesNotifier(ref.watch(apiProvider)),
);

import 'package:flutter_riverpod/flutter_riverpod.dart';

import '../api_client.dart';
import '../models/device.dart';
import 'api_provider.dart';

/// Devices plus the loading/error state needed for a clean first paint.
class DevicesState {
  const DevicesState({this.items = const [], this.loading = false, this.error});
  final List<Device> items;
  final bool loading;
  final String? error;
}

class DevicesNotifier extends StateNotifier<DevicesState> {
  DevicesNotifier(ApiClient api) : _api = api, super(const DevicesState(loading: true)) {
    refresh();
  }
  final ApiClient _api;
  bool _inFlight = false;
  bool _disposed = false;

  @override
  void dispose() {
    _disposed = true;
    super.dispose();
  }

  Future<void> refresh({bool showLoading = false}) async {
    if (_inFlight) return;
    _inFlight = true;
    if (showLoading || state.items.isEmpty) {
      state = DevicesState(items: state.items, loading: true);
    }
    try {
      final items = await _api.listDevices();
      if (_disposed) return;
      state = DevicesState(items: items);
    } catch (error) {
      if (_disposed) return;
      state = DevicesState(items: state.items, error: apiErrorMessage(error));
    } finally {
      _inFlight = false;
    }
  }
}

final devicesProvider = StateNotifierProvider<DevicesNotifier, DevicesState>(
  (ref) => DevicesNotifier(ref.watch(apiProvider)),
);

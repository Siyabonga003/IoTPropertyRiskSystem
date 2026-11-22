import 'package:flutter_riverpod/flutter_riverpod.dart';

import '../api_client.dart';
import '../models/alert.dart';
import 'api_provider.dart';

/// Alerts plus the loading/error state needed for a clean first paint.
class AlertsState {
  const AlertsState({this.items = const [], this.loading = false, this.error});
  final List<Alert> items;
  final bool loading;
  final String? error;

  List<Alert> get active => items.where((a) => a.status != 'resolved').toList();
}

class AlertsNotifier extends StateNotifier<AlertsState> {
  AlertsNotifier(ApiClient api) : _api = api, super(const AlertsState(loading: true)) {
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
      state = AlertsState(items: state.items, loading: true);
    }
    try {
      final items = await _api.listAlerts();
      if (_disposed) return;
      state = AlertsState(items: items);
    } catch (error) {
      if (_disposed) return;
      state = AlertsState(items: state.items, error: apiErrorMessage(error));
    } finally {
      _inFlight = false;
    }
  }
}

final alertsProvider = StateNotifierProvider<AlertsNotifier, AlertsState>(
  (ref) => AlertsNotifier(ref.watch(apiProvider)),
);

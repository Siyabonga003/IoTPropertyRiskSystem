import 'package:flutter_riverpod/flutter_riverpod.dart';

import '../api_client.dart';
import '../models/alert.dart';
import 'api_provider.dart';

/// Active (non-resolved) alerts for the user's properties.
class AlertsNotifier extends StateNotifier<List<Alert>> {
  AlertsNotifier(ApiClient api) : _api = api, super(const []) {
    refresh();
  }
  final ApiClient _api;

  Future<void> refresh() async {
    try {
      state = await _api.listAlerts();
    } catch (_) {
      // Retry on next poll.
    }
  }
}

final alertsProvider = StateNotifierProvider<AlertsNotifier, List<Alert>>(
  (ref) => AlertsNotifier(ref.watch(apiProvider)),
);

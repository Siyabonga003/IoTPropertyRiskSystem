import 'package:iot_property_risk_mobile/core/api_client.dart';
import 'package:iot_property_risk_mobile/core/models/alert.dart';
import 'package:iot_property_risk_mobile/core/models/device.dart';
import 'package:iot_property_risk_mobile/core/models/user.dart';
import 'package:iot_property_risk_mobile/core/providers/alerts_provider.dart';
import 'package:iot_property_risk_mobile/core/providers/auth_provider.dart';
import 'package:iot_property_risk_mobile/core/providers/devices_provider.dart';
import 'package:iot_property_risk_mobile/core/token_store.dart';

/// Fake ApiClient returning canned data; records calls.
class FakeApiClient implements ApiClient {
  FakeApiClient({this.devices = const [], this.alerts = const [], this.claimResult = const {}, this.loginError = false});
  @override
  final String baseUrl = '';
  @override
  final TokenStore tokenStore = FakeTokenStore();
  final List<Device> devices;
  final List<Alert> alerts;
  final Map<String, dynamic> claimResult;
  final bool loginError;
  final List<String> claimedTokens = [];
  final List<String> ackedAlerts = [];

  @override
  Future<Map<String, dynamic>> login(String email, String password) async {
    if (loginError) throw ApiError(401, '{"detail":"UNAUTHORIZED"}');
    return {'access_token': 'fake-token', 'token_type': 'bearer'};
  }

  @override
  Future<Map<String, dynamic>> register(String name, String email, String password) async {
    return {'access_token': 'fake-token', 'token_type': 'bearer'};
  }

  @override
  Future<User> me() async => User(
        id: 'usr_test',
        name: 'Test User',
        email: 'test@example.com',
        properties: const [Property(id: 'prp_test', name: 'Home', riskLevel: 0, role: 'owner')],
      );

  @override
  Future<List<Device>> listDevices() async => devices;

  @override
  Future<DeviceStatus> fetchDeviceStatus(String deviceId) async {
    final found = devices.firstWhere((d) => d.deviceId == deviceId, orElse: () => Device(deviceId: deviceId));
    return DeviceStatus(device: found);
  }

  @override
  Future<List<Alert>> listAlerts() async => alerts;

  @override
  Future<Map<String, dynamic>> claimPairing(String token) async {
    claimedTokens.add(token);
    return claimResult;
  }

  @override
  Future<void> ackAlert(String alertId) async => ackedAlerts.add(alertId);

  @override
  Future<void> revokeDevice(String deviceId) async {}
}

/// In-memory TokenStore.
class FakeTokenStore implements TokenStore {
  String? token;
  @override
  Future<String?> read() async => token;
  @override
  Future<void> write(String value) async => token = value;
  @override
  Future<void> clear() async => token = null;
}

class FakeAuthNotifier extends AuthNotifier {
  FakeAuthNotifier(super.api, super.tokens, this.user) {
    if (user != null) state = AuthState(user: user);
  }
  final User? user;
}

class FakeDevicesNotifier extends DevicesNotifier {
  FakeDevicesNotifier(super.api, this.devices) {
    state = devices;
  }
  final List<Device> devices;
}

class FakeAlertsNotifier extends AlertsNotifier {
  FakeAlertsNotifier(super.api, this.alerts) {
    state = alerts;
  }
  final List<Alert> alerts;
}

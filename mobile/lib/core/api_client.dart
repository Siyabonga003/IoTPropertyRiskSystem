import 'dart:convert';

import 'package:http/http.dart' as http;

import 'models/alert.dart';
import 'models/device.dart';
import 'models/user.dart';
import 'token_store.dart';

class ApiError implements Exception {
  ApiError(this.statusCode, this.body);
  final int statusCode;
  final String body;

  @override
  String toString() => 'ApiError($statusCode): $body';
}

/// Minimal REST client for the backend (§5, docs/SPEC.md).
class ApiClient {
  ApiClient({required this.baseUrl, required this.tokenStore});
  final String baseUrl;
  final TokenStore tokenStore;

  Future<dynamic> _request(String method, String path, {Map<String, dynamic>? body}) async {
    final uri = Uri.parse('$baseUrl$path');
    final headers = <String, String>{'Content-Type': 'application/json'};
    final token = await tokenStore.read();
    if (token != null && token.isNotEmpty) headers['Authorization'] = 'Bearer $token';
    final client = http.Client();
    try {
      http.Response res;
      if (method == 'GET') {
        res = await client.get(uri, headers: headers);
      } else if (method == 'DELETE') {
        res = await client.delete(uri, headers: headers);
      } else {
        res = await client.post(uri, headers: headers, body: body == null ? null : jsonEncode(body));
      }
      if (res.statusCode >= 400) throw ApiError(res.statusCode, res.body);
      return res.body.isEmpty ? null : jsonDecode(res.body);
    } finally {
      client.close();
    }
  }

  Future<Map<String, dynamic>> login(String email, String password) async {
    final res = await _request('POST', '/api/v1/auth/login', body: {'email': email, 'password': password});
    return Map<String, dynamic>.from(res);
  }

  Future<Map<String, dynamic>> register(String name, String email, String password) async {
    final res = await _request('POST', '/api/v1/users', body: {'name': name, 'email': email, 'password': password});
    return Map<String, dynamic>.from(res);
  }

  Future<User> me() async => User.fromJson(await _request('GET', '/api/v1/me'));

  Future<List<Device>> listDevices() async {
    final res = await _request('GET', '/api/v1/devices');
    return (res as List<dynamic>).map((e) => Device.fromJson(e as Map<String, dynamic>)).toList();
  }

  Future<DeviceStatus> fetchDeviceStatus(String deviceId) async =>
      DeviceStatus.fromJson(await _request('GET', '/api/v1/devices/$deviceId/status') as Map<String, dynamic>);

  Future<List<Alert>> listAlerts() async {
    final res = await _request('GET', '/api/v1/alerts');
    final items = (res as Map<String, dynamic>)['items'] as List<dynamic>? ?? const <dynamic>[];
    return items.map((e) => Alert.fromJson(e as Map<String, dynamic>)).toList();
  }

  /// Claims a pairing token (§4.2, docs/SPEC.md).
  Future<Map<String, dynamic>> claimPairing(String token) async {
    final res = await _request('POST', '/api/v1/pair', body: {'token': token});
    return Map<String, dynamic>.from(res);
  }

  Future<void> ackAlert(String alertId) => _request('POST', '/api/v1/alerts/$alertId/ack');

  Future<void> revokeDevice(String deviceId) => _request('DELETE', '/api/v1/devices/$deviceId');
}

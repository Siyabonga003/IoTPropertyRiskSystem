import 'dart:async';
import 'dart:convert';

import 'package:http/http.dart' as http;

import 'models/alert.dart';
import 'models/device.dart';
import 'models/system_mode.dart';
import 'models/user.dart';
import 'token_store.dart';

/// Error returned by the backend, normalized for display in the UI.
class ApiError implements Exception {
  ApiError(this.statusCode, this.body) {
    final parsed = _parseError(body, statusCode);
    code = parsed.$1;
    message = parsed.$2;
  }

  final int statusCode;
  final String body;
  late final String? code;
  late final String message;

  static (String?, String) _parseError(String body, int statusCode) {
    String? code;
    String? message;
    try {
      final data = jsonDecode(body);
      if (data is Map<String, dynamic>) {
        final error = data['error'];
        if (error is Map<String, dynamic>) {
          code = error['code'] as String?;
          message = error['message'] as String?;
        } else if (data['detail'] is String) {
          message = data['detail'] as String;
        }
      }
    } catch (_) {
      // Non-JSON body (proxy error, etc.) — fall back to the status message.
    }
    if (message == null || message.isEmpty || _looksLikeCode(message)) {
      message = _defaultMessage(code, statusCode);
    }
    return (code, message);
  }

  static bool _looksLikeCode(String value) =>
      RegExp(r'^[A-Z][A-Z0-9_]*$').hasMatch(value);

  static String _defaultMessage(String? code, int statusCode) {
    return switch (code) {
      'UNAUTHORIZED' => 'Your session has expired. Please sign in again.',
      'FORBIDDEN' => 'You do not have permission to do that.',
      'NOT_FOUND' => 'That item could not be found.',
      'EMAIL_TAKEN' => 'An account with that email already exists.',
      'TOKEN_INVALID' => 'That pairing token is invalid or has expired.',
      'DEVICE_ACTIVE' => 'This device is already paired.',
      'PAIRING_UNAVAILABLE' => 'This device is no longer available for pairing.',
      'RATE_LIMITED' => 'Too many attempts. Please wait a minute and try again.',
      'INVALID' => 'Please check the details and try again.',
      _ => switch (statusCode) {
          401 => 'Your session has expired. Please sign in again.',
          403 => 'You do not have permission to do that.',
          404 => 'That item could not be found.',
          409 => 'That action conflicts with the current state.',
          422 => 'Please check the details and try again.',
          429 => 'Too many attempts. Please wait a minute and try again.',
          >= 500 => 'The server had a problem. Please try again.',
          _ => 'Request failed. Please try again.',
        },
    };
  }

  @override
  String toString() => 'ApiError($statusCode): $message';
}

/// Turn any client/network error into a short message suitable for a snackbar.
String apiErrorMessage(Object error) {
  if (error is ApiError) return error.message;
  if (error is TimeoutException) return 'The request timed out. Check the server and try again.';
  if (error is http.ClientException) return 'Could not reach the server. Check your connection.';
  return 'Something went wrong. Please try again.';
}

/// Minimal REST client for the backend (§4, docs/SPEC.md).
class ApiClient {
  ApiClient({required this.baseUrl, required this.tokenStore});
  final String baseUrl;
  final TokenStore tokenStore;

  static const Duration _timeout = Duration(seconds: 12);

  Future<dynamic> _request(String method, String path, {Map<String, dynamic>? body}) async {
    final uri = Uri.parse('${baseUrl.replaceFirst(RegExp(r'/$'), '')}$path');
    final headers = <String, String>{'Content-Type': 'application/json'};
    final token = await tokenStore.read();
    if (token != null && token.isNotEmpty) headers['Authorization'] = 'Bearer $token';
    final client = http.Client();
    try {
      http.Response res;
      if (method == 'GET') {
        res = await client.get(uri, headers: headers).timeout(_timeout);
      } else if (method == 'DELETE') {
        res = await client.delete(uri, headers: headers).timeout(_timeout);
      } else if (method == 'PUT') {
        res = await client
            .put(uri, headers: headers, body: body == null ? null : jsonEncode(body))
            .timeout(_timeout);
      } else {
        res = await client
            .post(uri, headers: headers, body: body == null ? null : jsonEncode(body))
            .timeout(_timeout);
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

  /// Claims a pairing token (§3, docs/SPEC.md).
  Future<Map<String, dynamic>> claimPairing(String token) async {
    final res = await _request('POST', '/api/v1/pair', body: {'token': token});
    return Map<String, dynamic>.from(res);
  }

  /// Current system modes per property (SPEC §4 — system modes).
  Future<List<SystemMode>> getSystemModes() async {
    final res = await _request('GET', '/api/v1/system/modes');
    return (res as List<dynamic>).map((e) => SystemMode.fromJson(e as Map<String, dynamic>)).toList();
  }

  /// Set the system mode for a property (owner/admin).
  Future<SystemMode> setSystemMode(String propertyId, String mode) async {
    final res = await _request('PUT', '/api/v1/system/modes/$propertyId', body: {'mode': mode});
    return SystemMode.fromJson(res as Map<String, dynamic>);
  }

  Future<void> ackAlert(String alertId) async {
    await _request('POST', '/api/v1/alerts/$alertId/ack');
  }

  Future<void> revokeDevice(String deviceId) async {
    await _request('DELETE', '/api/v1/devices/$deviceId');
  }
}

import 'package:flutter_riverpod/flutter_riverpod.dart';

import '../api_client.dart';
import '../models/user.dart';
import '../token_store.dart';
import 'api_provider.dart';

class AuthState {
  const AuthState({this.user, this.loading = false, this.error});
  final User? user;
  final bool loading;
  final String? error;
}

class AuthNotifier extends StateNotifier<AuthState> {
  AuthNotifier(this._api, this._tokens) : super(const AuthState()) {
    _loadUser();
  }
  final ApiClient _api;
  final TokenStore _tokens;

  Future<void> _loadUser() async {
    final token = await _tokens.read();
    if (token == null) return;
    try {
      state = AuthState(user: await _api.me());
    } catch (e) {
      state = AuthState(error: e.toString());
    }
  }

  Future<bool> login(String email, String password) async {
    state = const AuthState(loading: true);
    try {
      final res = await _api.login(email, password);
      final token = res['access_token'] as String?;
      if (token == null) throw StateError('Missing access_token');
      await _tokens.write(token);
      state = AuthState(user: await _api.me());
      return true;
    } catch (e) {
      state = AuthState(error: e.toString());
      return false;
    }
  }

  Future<bool> register(String name, String email, String password) async {
    state = const AuthState(loading: true);
    try {
      final res = await _api.register(name, email, password);
      final token = res['access_token'] as String?;
      if (token == null) throw StateError('Missing access_token');
      await _tokens.write(token);
      state = AuthState(user: await _api.me());
      return true;
    } catch (e) {
      state = AuthState(error: e.toString());
      return false;
    }
  }

  Future<void> logout() async {
    await _tokens.clear();
    state = const AuthState();
  }
}

final authProvider = StateNotifierProvider<AuthNotifier, AuthState>(
  (ref) => AuthNotifier(ref.watch(apiProvider), ref.watch(tokenStoreProvider)),
);

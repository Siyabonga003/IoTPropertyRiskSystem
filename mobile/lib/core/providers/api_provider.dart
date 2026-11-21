import 'package:flutter_riverpod/flutter_riverpod.dart';

import '../../config/api_config.dart';
import '../api_client.dart';
import '../token_store.dart';

final tokenStoreProvider = Provider<TokenStore>((_) => TokenStore());

final apiProvider = Provider<ApiClient>((ref) {
  return ApiClient(baseUrl: apiBaseUrl, tokenStore: ref.watch(tokenStoreProvider));
});

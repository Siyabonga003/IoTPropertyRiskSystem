import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';

import '../core/providers/auth_provider.dart';
import 'app_theme.dart';
import 'screens/home_screen.dart';
import 'screens/login_screen.dart';

/// App root: authenticated users see [HomeScreen], everyone else [LoginScreen].
class App extends ConsumerWidget {
  const App({super.key});

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    final auth = ref.watch(authProvider);
    return MaterialApp(
      title: 'IoT Property Risk',
      theme: appTheme,
      debugShowCheckedModeBanner: false,
      home: auth.user != null ? const HomeScreen() : const LoginScreen(),
    );
  }
}

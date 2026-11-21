import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';

import '../../core/providers/auth_provider.dart';

/// Login screen (§5.1, docs/SPEC.md).
class LoginScreen extends ConsumerStatefulWidget {
  const LoginScreen({super.key});
  @override
  ConsumerState<LoginScreen> createState() => _LoginScreenState();
}

class _LoginScreenState extends ConsumerState<LoginScreen> {
  final _email = TextEditingController();
  final _password = TextEditingController();

  @override
  Widget build(BuildContext context) {
    final auth = ref.watch(authProvider);
    return Scaffold(
      body: Padding(
        padding: const EdgeInsets.symmetric(horizontal: 24, vertical: 48),
        child: Column(
          mainAxisAlignment: MainAxisAlignment.center,
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            Text('IoT Property Risk', style: Theme.of(context).textTheme.displayMedium),
            const SizedBox(height: 8),
            Text('Mobile client', style: Theme.of(context).textTheme.titleSmall),
            const SizedBox(height: 32),
            TextField(
              controller: _email,
              keyboardType: TextInputType.emailAddress,
              decoration: const InputDecoration(labelText: 'Email', border: OutlineInputBorder()),
            ),
            const SizedBox(height: 12),
            TextField(
              controller: _password,
              obscureText: true,
              decoration: const InputDecoration(labelText: 'Password', border: OutlineInputBorder()),
            ),
            const SizedBox(height: 16),
            if (auth.error != null) Text(auth.error!, style: const TextStyle(color: Colors.red)),
            TextButton(onPressed: _login, child: const Text('Log In')),
            TextButton(
              onPressed: () => Navigator.of(context).push(MaterialPageRoute(builder: (_) => const RegisterScreen())),
              child: const Text('Create account'),
            ),
          ],
        ),
      ),
    );
  }

  Future<void> _login() async => await ref.read(authProvider.notifier).login(_email.text, _password.text);
}

/// Registration screen.
class RegisterScreen extends ConsumerStatefulWidget {
  const RegisterScreen({super.key});
  @override
  ConsumerState<RegisterScreen> createState() => _RegisterScreenState();
}

class _RegisterScreenState extends ConsumerState<RegisterScreen> {
  final _name = TextEditingController();
  final _email = TextEditingController();
  final _password = TextEditingController();

  @override
  Widget build(BuildContext context) {
    final auth = ref.watch(authProvider);
    return Scaffold(
      body: Padding(
        padding: const EdgeInsets.symmetric(horizontal: 24, vertical: 48),
        child: Column(
          mainAxisAlignment: MainAxisAlignment.center,
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            Text('Create Account', style: Theme.of(context).textTheme.displayMedium),
            const SizedBox(height: 32),
            TextField(controller: _name, decoration: const InputDecoration(labelText: 'Name', border: OutlineInputBorder())),
            const SizedBox(height: 12),
            TextField(
              controller: _email,
              keyboardType: TextInputType.emailAddress,
              decoration: const InputDecoration(labelText: 'Email', border: OutlineInputBorder()),
            ),
            const SizedBox(height: 12),
            TextField(
              controller: _password,
              obscureText: true,
              decoration: const InputDecoration(labelText: 'Password (6+ chars)', border: OutlineInputBorder()),
            ),
            const SizedBox(height: 16),
            if (auth.error != null) Text(auth.error!, style: const TextStyle(color: Colors.red)),
            TextButton(onPressed: _register, child: const Text('Create account')),
            TextButton(onPressed: () => Navigator.of(context).pop(), child: const Text('Back to login')),
          ],
        ),
      ),
    );
  }

  Future<void> _register() async => await ref.read(authProvider.notifier).register(_name.text, _email.text, _password.text);
}

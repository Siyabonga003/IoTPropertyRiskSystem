import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:mobile_scanner/mobile_scanner.dart';

import '../../core/api_client.dart';
import '../../core/providers/api_provider.dart';
import '../../core/providers/devices_provider.dart';

/// Full-screen QR scanner; calls [onScanned] with the scanned token.
class QrScannerScreen extends StatefulWidget {
  const QrScannerScreen({super.key, required this.onScanned});
  final void Function(String token) onScanned;

  @override
  State<QrScannerScreen> createState() => _QrScannerScreenState();
}

class _QrScannerScreenState extends State<QrScannerScreen> {
  bool _handled = false;

  static String? _firstRaw(BarcodeCapture capture) {
    for (final barcode in capture.barcodes) {
      final value = barcode.rawValue;
      if (value != null && value.isNotEmpty) return value;
    }
    return null;
  }

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      appBar: AppBar(title: const Text('Scan QR code')),
      body: MobileScanner(
        onDetect: (capture) {
          if (_handled) return; // one scan per screen visit
          final token = _firstRaw(capture);
          if (token == null) return;
          _handled = true;
          widget.onScanned(token);
          if (mounted) Navigator.of(context).pop();
        },
      ),
    );
  }
}

/// Pairing screen (§4.2, docs/SPEC.md): QR scan or manual token entry.
class PairingScreen extends ConsumerStatefulWidget {
  const PairingScreen({super.key});

  /// Extracts the token from a QR string or a plain pairing token.
  static String extractToken(String input) {
    final uri = Uri.tryParse(input);
    if (uri != null) {
      final token = uri.queryParameters['token'] ?? uri.queryParameters['t'];
      if (token != null && token.isNotEmpty) return token;
    }
    return input.trim();
  }

  @override
  ConsumerState<PairingScreen> createState() => _PairingScreenState();
}

class _PairingScreenState extends ConsumerState<PairingScreen> {
  final _tokenController = TextEditingController();
  bool _claiming = false;
  String? _error;

  @override
  void dispose() {
    _tokenController.dispose();
    super.dispose();
  }

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      appBar: AppBar(title: const Text('Device Pairing')),
      body: Center(
        child: SingleChildScrollView(
          padding: const EdgeInsets.symmetric(horizontal: 24, vertical: 32),
          child: ConstrainedBox(
            constraints: const BoxConstraints(maxWidth: 460),
            child: Column(
              crossAxisAlignment: CrossAxisAlignment.stretch,
              children: [
                Icon(Icons.qr_code_2, size: 56, color: Theme.of(context).colorScheme.primary),
                const SizedBox(height: 12),
                Text(
                  'Pair a new device',
                  textAlign: TextAlign.center,
                  style: Theme.of(context).textTheme.titleMedium,
                ),
                const SizedBox(height: 4),
                Text(
                  'Scan the QR code shown by the device or paste its pairing token.',
                  textAlign: TextAlign.center,
                  style: Theme.of(context).textTheme.bodySmall,
                ),
                const SizedBox(height: 24),
                TextField(
                  controller: _tokenController,
                  enabled: !_claiming,
                  textInputAction: TextInputAction.done,
                  onSubmitted: (_) => _claim(),
                  decoration: const InputDecoration(
                    labelText: 'Pairing token',
                    hintText: 'pt_...',
                    border: OutlineInputBorder(),
                  ),
                ),
                const SizedBox(height: 8),
                if (_error != null)
                  Padding(
                    padding: const EdgeInsets.symmetric(vertical: 4),
                    child: Text(
                      _error!,
                      style: TextStyle(color: Theme.of(context).colorScheme.error),
                    ),
                  ),
                const SizedBox(height: 8),
                OutlinedButton.icon(
                  onPressed: _claiming ? null : _scanQr,
                  icon: const Icon(Icons.qr_code_scanner),
                  label: const Text('Scan QR code'),
                ),
                const SizedBox(height: 8),
                FilledButton.icon(
                  onPressed: _claiming ? null : _claim,
                  icon: _claiming
                      ? const SizedBox(width: 16, height: 16, child: CircularProgressIndicator(strokeWidth: 2))
                      : const Icon(Icons.link),
                  label: Text(_claiming ? 'Pairing…' : 'Claim Device'),
                ),
              ],
            ),
          ),
        ),
      ),
    );
  }

  Future<void> _scanQr() async {
    await Navigator.of(context).push<void>(
      MaterialPageRoute<void>(
        builder: (_) => QrScannerScreen(
          onScanned: (token) {
            if (!mounted) return;
            final parsed = PairingScreen.extractToken(token);
            if (parsed.isNotEmpty) {
              _tokenController.text = parsed;
              _claim();
            }
          },
        ),
      ),
    );
  }

  Future<void> _claim() async {
    if (_claiming) return;
    final token = _tokenController.text.trim();
    if (token.isEmpty) {
      setState(() => _error = 'Enter a pairing token or scan the QR code');
      return;
    }
    if (!token.startsWith('pt_') || token.length < 6) {
      setState(() => _error = 'That does not look like a pairing token (expected pt_…)');
      return;
    }
    setState(() {
      _claiming = true;
      _error = null;
    });
    try {
      final res = await ref.read(apiProvider).claimPairing(token);
      if (!mounted) return;
      await ref.read(devicesProvider.notifier).refresh();
      if (!mounted) return;
      final deviceId = res['device_id'] as String?;
      ScaffoldMessenger.of(context)
          .showSnackBar(SnackBar(content: Text('Paired with device ${deviceId ?? token}')));
      if (Navigator.of(context).canPop()) Navigator.of(context).pop();
    } catch (error) {
      if (!mounted) return;
      final message = apiErrorMessage(error);
      setState(() => _error = message);
      ScaffoldMessenger.of(context).showSnackBar(SnackBar(content: Text(message)));
    } finally {
      if (mounted) setState(() => _claiming = false);
    }
  }
}

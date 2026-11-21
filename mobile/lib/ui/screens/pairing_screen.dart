import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:mobile_scanner/mobile_scanner.dart';

import '../../core/providers/api_provider.dart';
import '../../core/providers/devices_provider.dart';

/// Full-screen QR scanner; calls [onScanned] with the scanned token and pops back.
class QrScannerScreen extends StatelessWidget {
  const QrScannerScreen({super.key, required this.onScanned});
  final void Function(String token) onScanned;

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
        onDetect: (barcodes) {
          final token = _firstRaw(barcodes);
          if (token == null) return;
          onScanned.call(token);
          Navigator.of(context).pop();
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

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      appBar: AppBar(title: const Text('Device Pairing')),
      body: Padding(
        padding: const EdgeInsets.symmetric(horizontal: 24, vertical: 48),
        child: Column(
          mainAxisAlignment: MainAxisAlignment.center,
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            TextField(
              controller: _tokenController,
              decoration: const InputDecoration(labelText: 'Pairing token', hintText: 'pt_...'),
            ),
            const SizedBox(height: 16),
            TextButton(onPressed: _scanQr, child: const Text('Scan QR code')),
            const SizedBox(height: 16),
            TextButton(onPressed: _claim, child: const Text('Claim Device')),
          ],
        ),
      ),
    );
  }

  Future<void> _scanQr() async {
    await Navigator.of(context).push<void>(
      MaterialPageRoute<void>(
        builder: (_) => QrScannerScreen(
          onScanned: (token) {
            if (token.isNotEmpty) _tokenController.text = PairingScreen.extractToken(token);
            Navigator.of(context).pop();
          },
        ),
      ),
    );
    if (!mounted) return;
    if (_tokenController.text.isNotEmpty) await _claim();
  }

  Future<void> _claim() async {
    final token = _tokenController.text.trim();
    if (token.isEmpty) {
      if (!mounted) return;
      ScaffoldMessenger.of(context)
          .showSnackBar(const SnackBar(content: Text('Enter a pairing token or scan the QR code')));
      return;
    }
    try {
      final res = await ref.read(apiProvider).claimPairing(token);
      if (!mounted) return;
      ref.read(devicesProvider.notifier).refresh();
      final deviceId = res['device_id'] as String?;
      ScaffoldMessenger.of(context)
          .showSnackBar(SnackBar(content: Text('Paired with device ${deviceId ?? token}')));
      if (Navigator.of(context).canPop()) Navigator.of(context).pop();
    } catch (e) {
      if (!mounted) return;
      ScaffoldMessenger.of(context).showSnackBar(SnackBar(content: Text('Pairing failed: $e')));
    }
  }
}

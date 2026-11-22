import 'dart:async';

import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';

import '../../core/api_client.dart';
import '../../core/models/system_mode.dart';
import '../../core/models/user.dart';
import '../../core/providers/api_provider.dart';
import '../../core/providers/auth_provider.dart';

/// Mode picker for a property: system-mode selection with a current-mode
/// indicator, role-gated switching, saving state, and error feedback
/// (SPEC §2 — system arming modes).
class ModePicker extends ConsumerStatefulWidget {
  const ModePicker({super.key, required this.property});
  final Property property;

  @override
  ConsumerState<ModePicker> createState() => _ModePickerState();
}

class _ModePickerState extends ConsumerState<ModePicker> {
  Timer? _timer;
  String? _mode;
  bool _loading = true;
  bool _saving = false;
  bool _refreshing = false;
  String? _error;

  @override
  void initState() {
    super.initState();
    _refresh();
    _timer = Timer.periodic(const Duration(seconds: 5), (_) => _refresh());
  }

  @override
  void dispose() {
    _timer?.cancel();
    super.dispose();
  }

  Future<void> _refresh() async {
    if (_refreshing || _saving) return;
    _refreshing = true;
    try {
      final modes = await ref.read(apiProvider).getSystemModes();
      if (!mounted) return;
      final match = modes.firstWhere(
        (m) => m.propertyId == widget.property.id,
        orElse: () => const SystemMode(propertyId: '', mode: unarmedMode),
      );
      if (match.mode != _mode) setState(() => _mode = match.mode);
      if (_error != null) setState(() => _error = null);
    } catch (error) {
      // Keep showing the last known mode; only surface the error before the
      // first successful load so polling failures don't spam the UI.
      if (mounted && _mode == null) setState(() => _error = apiErrorMessage(error));
    } finally {
      _refreshing = false;
      if (mounted && _loading) setState(() => _loading = false);
    }
  }

  Future<void> _set(String mode) async {
    if (_saving || mode == _mode) return;
    final previous = _mode;
    setState(() {
      _saving = true;
      _mode = mode;
      _error = null;
    });
    try {
      final updated = await ref.read(apiProvider).setSystemMode(widget.property.id, mode);
      if (!mounted) return;
      setState(() => _mode = updated.mode);
      ScaffoldMessenger.of(context).showSnackBar(
        SnackBar(content: Text('System mode set to ${modeLabel(updated.mode)}')),
      );
    } catch (error) {
      if (!mounted) return;
      final message = apiErrorMessage(error);
      setState(() {
        _mode = previous;
        _error = message;
      });
      ScaffoldMessenger.of(context).showSnackBar(SnackBar(content: Text(message)));
    } finally {
      if (mounted) setState(() => _saving = false);
    }
  }

  @override
  Widget build(BuildContext context) {
    final canSet = {'owner', 'admin'}.contains(ref.watch(authProvider).user?.roleOf(widget.property.id) ?? '');
    final current = _mode ?? unarmedMode;
    return Column(
      crossAxisAlignment: CrossAxisAlignment.start,
      children: [
        Row(
          children: [
            Text('System mode', style: Theme.of(context).textTheme.titleSmall?.copyWith(fontWeight: FontWeight.bold)),
            const SizedBox(width: 8),
            if (_saving || _loading)
              const SizedBox(width: 14, height: 14, child: CircularProgressIndicator(strokeWidth: 2)),
            const Spacer(),
            Text(modeLabel(current), style: Theme.of(context).textTheme.labelLarge),
          ],
        ),
        const SizedBox(height: 8),
        SizedBox(
          width: double.infinity,
          child: SegmentedButton<String>(
            showSelectedIcon: false,
            segments: [
              for (final m in systemModes) ButtonSegment(value: m, label: Text(modeLabel(m))),
            ],
            selected: {current},
            onSelectionChanged: canSet && !_saving ? (selection) => _set(selection.first) : null,
          ),
        ),
        const SizedBox(height: 6),
        Text(
          canSet
              ? modeDescription(current)
              : 'Only owners and admins can change the system mode.',
          style: Theme.of(context).textTheme.bodySmall,
        ),
        if (_error != null) ...[
          const SizedBox(height: 4),
          Text(_error!, style: TextStyle(color: Theme.of(context).colorScheme.error, fontSize: 12)),
        ],
      ],
    );
  }
}

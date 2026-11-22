import '../utils.dart';

/// System modes (SPEC §2 — system arming modes).
const String unarmedMode = 'unarmed';

/// Valid modes, in order.
const List<String> systemModes = [unarmedMode, 'armed', 'armed_away'];

/// Display label for a mode.
String modeLabel(String mode) => switch (mode) {
      unarmedMode => 'Unarmed',
      'armed' => 'Armed',
      'armed_away' => 'Armed Away',
      _ => mode,
    };

/// Short explanation of how motion is handled in [mode].
String modeDescription(String mode) => switch (mode) {
      unarmedMode => 'Motion is logged but does not create alerts.',
      'armed' => 'Motion creates a notice alert.',
      'armed_away' => 'Away mode: motion creates a notice alert.',
      _ => '',
    };

/// One property's current mode + metadata, as returned by the backend.
class SystemMode {
  const SystemMode({required this.propertyId, required this.mode, this.updatedAt, this.updatedBy});
  final String propertyId;
  final String mode;
  final DateTime? updatedAt;
  final String? updatedBy;

  factory SystemMode.fromJson(Map<String, dynamic> j) => SystemMode(
        propertyId: j['property_id'] as String? ?? '',
        mode: j['mode'] as String? ?? unarmedMode,
        updatedAt: parseDateTime(j['updated_at']),
        updatedBy: j['updated_by'] as String?,
      );
}

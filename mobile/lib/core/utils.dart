/// Shared JSON parsing helpers for backend (snake_case) payloads.
int intOf(dynamic value) => value is num ? value.toInt() : 0;

/// Nullable integer helper for optional telemetry fields.
int? intOrNull(dynamic value) => value is num ? value.toInt() : null;

double? doubleOf(dynamic value) => value is num ? value.toDouble() : null;

DateTime? parseDateTime(dynamic value) {
  if (value is DateTime) return value;
  if (value is String) return DateTime.tryParse(value);
  if (value is num) return DateTime.fromMillisecondsSinceEpoch(value.toInt(), isUtc: true);
  return null;
}

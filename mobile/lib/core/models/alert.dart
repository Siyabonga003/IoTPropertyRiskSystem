import '../utils.dart';

/// Alert model (§3.3, docs/SPEC.md).
class Alert {
  const Alert({
    required this.id,
    required this.propertyId,
    required this.deviceId,
    required this.signal,
    required this.severity,
    required this.status,
    this.notes = '',
    this.firstSeenAt,
    this.lastSeenAt,
    this.acknowledgedAt,
    this.resolvedAt,
  });
  final String id;
  final String propertyId;
  final String deviceId;
  final String signal;
  final String severity;
  final String status;
  final String notes;
  final DateTime? firstSeenAt;
  final DateTime? lastSeenAt;
  final DateTime? acknowledgedAt;
  final DateTime? resolvedAt;

  bool get isOpen => status == 'open';

  factory Alert.fromJson(Map<String, dynamic> j) => Alert(
        id: j['id'] as String? ?? '',
        propertyId: j['property_id'] as String? ?? '',
        deviceId: j['device_id'] as String? ?? '',
        signal: j['signal'] as String? ?? '',
        severity: j['severity'] as String? ?? '',
        status: j['status'] as String? ?? 'open',
        notes: j['notes'] as String? ?? '',
        firstSeenAt: parseDateTime(j['first_seen_at']),
        lastSeenAt: parseDateTime(j['last_seen_at']),
        acknowledgedAt: parseDateTime(j['acknowledged_at']),
        resolvedAt: parseDateTime(j['resolved_at']),
      );
}

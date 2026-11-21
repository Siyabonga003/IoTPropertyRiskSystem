import 'package:flutter/material.dart';

enum RiskLevel {
  ok(0, 'ok', Colors.green),
  notice(1, 'notice', Colors.blue),
  warning(2, 'warning', Colors.amber),
  alert(3, 'alert', Colors.orange),
  critical(4, 'critical', Colors.red);

  const RiskLevel(this.value, this.label, this.color);

  final int value;
  final String label;
  final Color color;

  static RiskLevel fromSeverity(String? severity) => switch (severity) {
        'ok' => RiskLevel.ok,
        'notice' => RiskLevel.notice,
        'warning' => RiskLevel.warning,
        'alert' => RiskLevel.alert,
        'critical' => RiskLevel.critical,
        _ => RiskLevel.ok,
      };
}

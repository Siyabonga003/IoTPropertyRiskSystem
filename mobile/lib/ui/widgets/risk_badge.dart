import 'package:flutter/material.dart';

import '../../core/models/risk.dart';

/// Colored risk badge (e.g. "warning", "critical").
class RiskBadge extends StatelessWidget {
  const RiskBadge({super.key, required this.level, this.label});
  final RiskLevel level;
  final String? label;

  @override
  Widget build(BuildContext context) {
    return Container(
      padding: const EdgeInsets.symmetric(horizontal: 8, vertical: 4),
      decoration: BoxDecoration(color: level.color, borderRadius: BorderRadius.circular(12)),
      child: Text(
        label ?? level.label,
        style: const TextStyle(color: Colors.white, fontSize: 12, fontWeight: FontWeight.bold),
      ),
    );
  }
}

import 'package:flutter/material.dart';

import '../../core/models/risk.dart';
import 'risk_badge.dart';

/// One sensor card on the device detail screen (§1, docs/SPEC.md).
class SensorCard extends StatelessWidget {
  const SensorCard({
    super.key,
    required this.title,
    required this.risk,
    required this.details,
    this.faults = const [],
  });
  final String title;
  final RiskLevel risk;
  final String details;
  final List<String> faults;

  @override
  Widget build(BuildContext context) {
    return Card(
      elevation: 1,
      margin: const EdgeInsets.fromLTRB(16, 4, 16, 4),
      child: Padding(
        padding: const EdgeInsets.all(14),
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            Row(
              children: [
                Text(title, style: Theme.of(context).textTheme.titleSmall?.copyWith(fontWeight: FontWeight.bold)),
                const Spacer(),
                RiskBadge(level: risk),
              ],
            ),
            const SizedBox(height: 4),
            Text(details, style: Theme.of(context).textTheme.bodySmall),
            for (final f in faults) Text('• $f', style: const TextStyle(color: Colors.red, fontSize: 11)),
          ],
        ),
      ),
    );
  }
}

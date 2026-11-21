import 'package:flutter/material.dart';

import '../../core/models/alert.dart';
import '../../core/models/risk.dart';
import '../signal_labels.dart';
import '../utils.dart';
import 'risk_badge.dart';

/// One row in the alerts list / detail view.
class AlertTile extends StatelessWidget {
  const AlertTile({
    super.key,
    required this.alert,
    this.canAck = false,
    this.onTap,
    this.onAck,
  });
  final Alert alert;
  final bool canAck;
  final VoidCallback? onTap;
  final VoidCallback? onAck;

  @override
  Widget build(BuildContext context) {
    return InkWell(
      onTap: onTap,
      child: Card(
        elevation: 1,
        child: Padding(
          padding: const EdgeInsets.symmetric(horizontal: 12, vertical: 8),
          child: Row(
            children: [
              Expanded(
                child: Column(
                  crossAxisAlignment: CrossAxisAlignment.start,
                  children: [
                    Text(
                      signalLabel(alert.signal),
                      style: Theme.of(context).textTheme.titleSmall?.copyWith(
                            fontWeight: FontWeight.bold,
                            color: RiskLevel.fromSeverity(alert.severity).color,
                          ),
                    ),
                    Text(
                      'Device: ${alert.deviceId} · first seen ${formatTime(alert.firstSeenAt)}',
                      style: Theme.of(context).textTheme.bodySmall,
                    ),
                  ],
                ),
              ),
              RiskBadge(level: RiskLevel.fromSeverity(alert.severity)),
              if (canAck && alert.isOpen)
                TextButton(
                  onPressed: onAck,
                  child: const Text('Ack'),
                ),
            ],
          ),
        ),
      ),
    );
  }
}

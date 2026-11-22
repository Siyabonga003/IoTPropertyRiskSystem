import 'package:flutter/material.dart';

import '../../core/models/alert.dart';
import '../../core/models/risk.dart';
import '../../core/models/system_mode.dart';
import '../signal_labels.dart';
import '../utils.dart';
import 'risk_badge.dart';

/// One row in the alerts list / detail view.
class AlertTile extends StatelessWidget {
  const AlertTile({
    super.key,
    required this.alert,
    this.canAck = false,
    this.busy = false,
    this.onTap,
    this.onAck,
  });
  final Alert alert;
  final bool canAck;
  final bool busy;
  final VoidCallback? onTap;
  final VoidCallback? onAck;

  @override
  Widget build(BuildContext context) {
    final acknowledged = alert.status == 'acknowledged';
    return Card(
      elevation: 1,
      margin: const EdgeInsets.fromLTRB(16, 4, 16, 4),
      child: InkWell(
        borderRadius: BorderRadius.circular(12),
        onTap: onTap,
        child: Padding(
          padding: const EdgeInsets.symmetric(horizontal: 12, vertical: 10),
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
                    const SizedBox(height: 2),
                    Text(
                      'Device: ${alert.deviceId} · ${formatTime(alert.firstSeenAt)}',
                      style: Theme.of(context).textTheme.bodySmall,
                    ),
                    const SizedBox(height: 4),
                    Row(
                      children: [
                        Icon(Icons.shield_outlined, size: 13, color: Theme.of(context).colorScheme.outline),
                        const SizedBox(width: 4),
                        Text(
                          modeLabel(alert.systemMode),
                          style: Theme.of(context).textTheme.labelSmall?.copyWith(
                                color: Theme.of(context).colorScheme.outline,
                              ),
                        ),
                        if (acknowledged) ...[
                          const SizedBox(width: 8),
                          Text(
                            'Acknowledged',
                            style: Theme.of(context).textTheme.labelSmall?.copyWith(
                                  color: Theme.of(context).colorScheme.primary,
                                ),
                          ),
                        ],
                      ],
                    ),
                  ],
                ),
              ),
              const SizedBox(width: 8),
              Column(
                crossAxisAlignment: CrossAxisAlignment.end,
                children: [
                  RiskBadge(level: RiskLevel.fromSeverity(alert.severity)),
                  if (canAck && alert.isOpen)
                    busy
                        ? const Padding(
                            padding: EdgeInsets.all(8),
                            child: SizedBox(width: 18, height: 18, child: CircularProgressIndicator(strokeWidth: 2)),
                          )
                        : TextButton(onPressed: onAck, child: const Text('Ack')),
                ],
              ),
            ],
          ),
        ),
      ),
    );
  }
}

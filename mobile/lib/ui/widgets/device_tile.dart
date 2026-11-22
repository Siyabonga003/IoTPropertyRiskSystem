import 'package:flutter/material.dart';

import '../../core/models/device.dart';
import '../../core/models/system_mode.dart';
import '../utils.dart';
import 'risk_badge.dart';

/// Summary card on the home screen.
class DeviceTile extends StatelessWidget {
  const DeviceTile({super.key, required this.device, required this.onTap});
  final Device device;
  final VoidCallback onTap;

  @override
  Widget build(BuildContext context) {
    final connected = device.status == 'active';
    return Card(
      elevation: 1,
      margin: const EdgeInsets.fromLTRB(16, 4, 16, 4),
      child: InkWell(
        borderRadius: BorderRadius.circular(12),
        onTap: onTap,
        child: Padding(
          padding: const EdgeInsets.all(12),
          child: Row(
            children: [
              Icon(
                connected ? Icons.sensors : Icons.sensors_off,
                size: 28,
                color: connected ? Theme.of(context).colorScheme.primary : Theme.of(context).colorScheme.outline,
              ),
              const SizedBox(width: 12),
              Expanded(
                child: Column(
                  crossAxisAlignment: CrossAxisAlignment.start,
                  children: [
                    Text(
                      device.name.isEmpty ? device.deviceId : device.name,
                      style: const TextStyle(fontWeight: FontWeight.bold),
                    ),
                    Text(
                      '${device.status} · ${modeLabel(device.systemMode)} · ${formatTime(device.lastSeenAt)}',
                      style: Theme.of(context).textTheme.bodySmall,
                    ),
                  ],
                ),
              ),
              const SizedBox(width: 8),
              RiskBadge(level: riskOf(device)),
            ],
          ),
        ),
      ),
    );
  }
}

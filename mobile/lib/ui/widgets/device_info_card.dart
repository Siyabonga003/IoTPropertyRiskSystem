import 'package:flutter/material.dart';

import '../../core/models/device.dart';
import '../../core/models/system_mode.dart';
import '../utils.dart';
import 'risk_badge.dart';

/// One device info card on the device detail screen.
class DeviceInfoCard extends StatelessWidget {
  const DeviceInfoCard({super.key, required this.device});
  final Device device;

  @override
  Widget build(BuildContext context) {
    return Card(
      elevation: 1,
      margin: const EdgeInsets.fromLTRB(16, 8, 16, 8),
      child: Padding(
        padding: const EdgeInsets.all(14),
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            Row(
              children: [
                Expanded(
                  child: Text(
                    device.name.isEmpty ? device.deviceId : device.name,
                    style: Theme.of(context).textTheme.titleMedium?.copyWith(fontWeight: FontWeight.bold),
                  ),
                ),
                RiskBadge(level: riskOf(device)),
              ],
            ),
            const SizedBox(height: 6),
            Text('ID: ${device.deviceId}', style: Theme.of(context).textTheme.bodySmall),
            Text('Status: ${device.status} · Health: ${device.deviceHealth}', style: Theme.of(context).textTheme.bodySmall),
            if (device.firmwareVersion != null && device.firmwareVersion!.isNotEmpty)
              Text('Firmware: ${device.firmwareVersion}', style: Theme.of(context).textTheme.bodySmall),
            if (device.lastSeenAt != null)
              Text('Last seen: ${formatTime(device.lastSeenAt)}', style: Theme.of(context).textTheme.bodySmall),
            const SizedBox(height: 8),
            Container(
              width: double.infinity,
              padding: const EdgeInsets.symmetric(horizontal: 10, vertical: 8),
              decoration: BoxDecoration(
                color: Theme.of(context).colorScheme.surfaceContainerHighest,
                borderRadius: BorderRadius.circular(8),
              ),
              child: Row(
                children: [
                  const Icon(Icons.shield_outlined, size: 16),
                  const SizedBox(width: 6),
                  Expanded(
                    child: Text(
                      '${modeLabel(device.systemMode)} — ${modeDescription(device.systemMode)}',
                      style: Theme.of(context).textTheme.bodySmall,
                    ),
                  ),
                ],
              ),
            ),
            if (device.batteryPct != null || device.rssiDbm != null) ...[
              const SizedBox(height: 8),
              Row(
                children: [
                  if (device.batteryPct != null) ...[
                    const Icon(Icons.battery_full, size: 16),
                    const SizedBox(width: 4),
                    Text('${device.batteryPct}%', style: Theme.of(context).textTheme.bodySmall),
                    const SizedBox(width: 12),
                  ],
                  if (device.rssiDbm != null) ...[
                    const Icon(Icons.wifi, size: 16),
                    const SizedBox(width: 4),
                    Text('${device.rssiDbm} dBm', style: Theme.of(context).textTheme.bodySmall),
                  ],
                ],
              ),
            ],
            if (device.faults.isNotEmpty) ...[
              const SizedBox(height: 8),
              Text('Faults: ${device.faults.join(', ')}', style: TextStyle(color: Theme.of(context).colorScheme.error, fontSize: 12)),
            ],
          ],
        ),
      ),
    );
  }
}

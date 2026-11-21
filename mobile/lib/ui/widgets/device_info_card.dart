import 'package:flutter/material.dart';

import '../../core/models/device.dart';
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
      child: Padding(
        padding: const EdgeInsets.all(12),
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            Row(
              children: [
                Text(device.name.isEmpty ? device.deviceId : device.name,
                    style: Theme.of(context).textTheme.titleMedium?.copyWith(fontWeight: FontWeight.bold)),
                const Spacer(),
                RiskBadge(level: riskOf(device)),
              ],
            ),
            const SizedBox(height: 4),
            Text('ID: ${device.deviceId}'),
            Text('Status: ${device.status}'),
            if (device.lastSeenAt != null) Text('Last seen: ${formatTime(device.lastSeenAt)}'),
            if (device.batteryPct != null) Text('Battery: ${device.batteryPct}%'),
            if (device.rssiDbm != null) Text('RSSI: ${device.rssiDbm} dBm'),
          ],
        ),
      ),
    );
  }
}

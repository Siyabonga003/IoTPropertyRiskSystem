import 'package:flutter/material.dart';

import '../../core/models/device.dart';
import '../utils.dart';
import 'risk_badge.dart';

/// Summary card on the home screen.
class DeviceTile extends StatelessWidget {
  const DeviceTile({super.key, required this.device, required this.onTap});
  final Device device;
  final VoidCallback onTap;

  @override
  Widget build(BuildContext context) {
    return InkWell(
      onTap: onTap,
      child: Card(
        elevation: 1,
        child: Padding(
          padding: const EdgeInsets.all(10),
          child: Row(
            children: [
              const Icon(Icons.sensors_off, size: 28),
              const SizedBox(width: 10),
              Expanded(
                child: Column(
                  crossAxisAlignment: CrossAxisAlignment.start,
                  children: [
                    Text(device.name.isEmpty ? device.deviceId : device.name,
                        style: const TextStyle(fontWeight: FontWeight.bold)),
                    Text('${device.status} · ${formatTime(device.lastSeenAt)}',
                        style: Theme.of(context).textTheme.bodySmall),
                  ],
                ),
              ),
              RiskBadge(level: riskOf(device)),
            ],
          ),
        ),
      ),
    );
  }
}

/// Human-readable labels for signal types (§2, docs/SPEC.md).
const Map<String, String> signalLabels = {
  'smoke_gas': 'Smoke / Gas',
  'flame': 'Flame',
  'water_leak': 'Water Leak',
  'motion': 'Motion',
  'device_disconnected': 'Device Disconnected',
  'sensor_fault': 'Sensor Fault',
};

String signalLabel(String signal) => signalLabels[signal] ?? signal;

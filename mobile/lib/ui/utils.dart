import '../core/models/device.dart';
import '../core/models/risk.dart';

RiskLevel riskOf(Device d) => RiskLevel.values[d.riskLevel.clamp(0, RiskLevel.values.length - 1).toInt()];

RiskLevel signalRisk(Device d, String signal) =>
    RiskLevel.values[(d.sensorLevels[signal] ?? 0).clamp(0, RiskLevel.values.length - 1).toInt()];

String formatTime(DateTime? dt) {
  if (dt == null) return '-';
  String pad(int n) => n.toString().padLeft(2, '0');
  return '${pad(dt.hour)}:${pad(dt.minute)}';
}

String ppmOf(double? v) => v == null ? 'n/a' : '${v.toStringAsFixed(1)} ppm';

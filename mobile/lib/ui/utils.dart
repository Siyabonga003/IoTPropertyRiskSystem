import '../core/models/device.dart';
import '../core/models/risk.dart';

RiskLevel riskLevelOf(int value) =>
    RiskLevel.values[value.clamp(0, RiskLevel.values.length - 1).toInt()];

RiskLevel riskOf(Device d) => riskLevelOf(d.riskLevel);

RiskLevel signalRisk(Device d, String signal) => riskLevelOf(d.sensorLevels[signal] ?? 0);

String formatTime(DateTime? dt) {
  if (dt == null) return '-';
  String pad(int n) => n.toString().padLeft(2, '0');
  return '${pad(dt.hour)}:${pad(dt.minute)}';
}

String ppmOf(double? v) => v == null ? 'n/a' : '${v.toStringAsFixed(1)} ppm';

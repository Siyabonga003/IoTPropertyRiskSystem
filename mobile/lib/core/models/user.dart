import '../utils.dart';

class Property {
  const Property({required this.id, required this.name, this.riskLevel = 0, this.role = ''});
  final String id;
  final String name;
  final int riskLevel;
  final String role;

  factory Property.fromJson(Map<String, dynamic> json) => Property(
        id: json['id'] as String? ?? '',
        name: json['name'] as String? ?? '',
        riskLevel: intOf(json['risk_level']),
        role: json['role'] as String? ?? '',
      );
}

class User {
  const User({
    required this.id,
    required this.name,
    this.email = '',
    this.phone = '',
    this.createdAt,
    this.properties = const [],
  });
  final String id;
  final String name;
  final String email;
  final String phone;
  final DateTime? createdAt;
  final List<Property> properties;

  /// Role of this user within [propertyId]; empty string if not a member.
  String roleOf(String propertyId) {
    for (final p in properties) {
      if (p.id == propertyId) return p.role;
    }
    return '';
  }

  factory User.fromJson(Map<String, dynamic> json) => User(
        id: json['id'] as String? ?? '',
        name: json['name'] as String? ?? '',
        email: json['email'] as String? ?? '',
        phone: json['phone'] as String? ?? '',
        createdAt: parseDateTime(json['created_at']),
        properties: ((json['properties'] as List<dynamic>?) ?? const [])
            .map((e) => Property.fromJson(e as Map<String, dynamic>))
            .toList(),
      );
}

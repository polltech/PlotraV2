import 'package:hive/hive.dart';

part 'user.g.dart';

@HiveType(typeId: 0)
class User {
  @HiveField(0)
  final String id;
  
  @HiveField(1)
  final String email;
  
  @HiveField(2)
  final String name;
  
  @HiveField(3)
  final String role; // farmer, officer, admin, reviewer
  
  @HiveField(4)
  final String? phone;
  
  @HiveField(5)
  final String? farmCount;
  
  @HiveField(6)
  final String? avatar;
  
  @HiveField(7)
  final DateTime? createdAt;
  
  @HiveField(8)
  final String? accessToken;

  User({
    required this.id,
    required this.email,
    required this.name,
    required this.role,
    this.phone,
    this.farmCount,
    this.avatar,
    this.createdAt,
    this.accessToken,
  });

  factory User.fromJson(Map<String, dynamic> json) {
    return User(
      id: json['id'] ?? '',
      email: json['email'] ?? '',
      name: json['name'] ?? json.get('full_name', ''),
      role: json['role'] ?? 'farmer',
      phone: json['phone'],
      farmCount: json['farm_count']?.toString(),
      avatar: json['avatar_url'],
      createdAt: json['created_at'] != null 
          ? DateTime.parse(json['created_at'])
          : null,
      accessToken: json['access_token'],
    );
  }

  Map<String, dynamic> toJson() {
    return {
      'id': id,
      'email': email,
      'name': name,
      'role': role,
      'phone': phone,
      'farm_count': farmCount,
      'avatar_url': avatar,
      'created_at': createdAt?.toIso8601String(),
    };
  }

  // Copy with method for updates
  User copyWith({
    String? id,
    String? email,
    String? name,
    String? role,
    String? phone,
    String? farmCount,
    String? avatar,
    DateTime? createdAt,
    String? accessToken,
  }) {
    return User(
      id: id ?? this.id,
      email: email ?? this.email,
      name: name ?? this.name,
      role: role ?? this.role,
      phone: phone ?? this.phone,
      farmCount: farmCount ?? this.farmCount,
      avatar: avatar ?? this.avatar,
      createdAt: createdAt ?? this.createdAt,
      accessToken: accessToken ?? this.accessToken,
    );
  }
}

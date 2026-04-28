import 'package:hive/hive.dart';
import 'latlng_data.dart';

part 'farm.g.dart';

@HiveType(typeId: 1)
class Farm {
  @HiveField(0)
  final String id;
  
  @HiveField(1)
  final String name;
  
  @HiveField(2)
  final List<LatLngData> polygon;
  
  @HiveField(3)
  final double area; // in hectares
  
  @HiveField(4)
  final String? cropType;
  
  @HiveField(5)
  final String status; // draft, submitted, cooperative_approved, admin_approved, eudr_submitted, certified
  
  @HiveField(6)
  final DateTime createdAt;
  
  @HiveField(7)
  final DateTime? updatedAt;
  
  @HiveField(8)
  final String? cooperativeId;
  
  @HiveField(9)
  final String? verificationLevel;

  Farm({
    required this.id,
    required this.name,
    required this.polygon,
    required this.area,
    this.cropType,
    this.status = 'draft',
    required this.createdAt,
    this.updatedAt,
    this.cooperativeId,
    this.verificationLevel,
  });

  factory Farm.fromJson(Map<String, dynamic> json) {
    return Farm(
      id: json['id'] ?? '',
      name: json['name'] ?? 'Unnamed Farm',
      polygon: (json['polygon'] as List?)
          ?.map((p) => LatLngData.fromJson(p))
          .toList() ?? [],
      area: (json['area'] as num?)?.toDouble() ?? 0.0,
      cropType: json['crop_type'],
      status: json['status'] ?? 'draft',
      createdAt: DateTime.parse(json['created_at'] ?? DateTime.now().toIso8601String()),
      updatedAt: json['updated_at'] != null 
          ? DateTime.parse(json['updated_at'])
          : null,
      cooperativeId: json['cooperative_id'],
      verificationLevel: json['verification_level'],
    );
  }

  Map<String, dynamic> toJson() {
    return {
      'id': id,
      'name': name,
      'polygon': polygon.map((p) => p.toJson()).toList(),
      'area': area,
      'crop_type': cropType,
      'status': status,
      'created_at': createdAt.toIso8601String(),
      'updated_at': updatedAt?.toIso8601String(),
      'cooperative_id': cooperativeId,
      'verification_level': verificationLevel,
    };
  }

  Farm copyWith({
    String? id,
    String? name,
    List<LatLngData>? polygon,
    double? area,
    String? cropType,
    String? status,
    DateTime? createdAt,
    DateTime? updatedAt,
    String? cooperativeId,
    String? verificationLevel,
  }) {
    return Farm(
      id: id ?? this.id,
      name: name ?? this.name,
      polygon: polygon ?? this.polygon,
      area: area ?? this.area,
      cropType: cropType ?? this.cropType,
      status: status ?? this.status,
      createdAt: createdAt ?? this.createdAt,
      updatedAt: updatedAt ?? this.updatedAt,
      cooperativeId: cooperativeId ?? this.cooperativeId,
      verificationLevel: verificationLevel ?? this.verificationLevel,
    );
  }

  // Helper methods
  bool get isVerified => status == 'certified';
  bool get isDraft => status == 'draft';
  bool get isPending => status == 'submitted' || status == 'cooperative_approved';
  
  String get statusDisplay {
    switch (status) {
      case 'draft': return 'Draft';
      case 'submitted': return 'Submitted';
      case 'cooperative_approved': return 'Coop Approved';
      case 'admin_approved': return 'Admin Approved';
      case 'eudr_submitted': return 'EUDR Submitted';
      case 'certified': return 'Certified';
      default: return status.toUpperCase();
    }
  }
  
  Color get statusColor {
    switch (status) {
      case 'draft': return Colors.grey;
      case 'submitted': return Colors.orange;
      case 'cooperative_approved': return Colors.blue;
      case 'admin_approved': return Colors.purple;
      case 'eudr_submitted': return Colors.yellow;
      case 'certified': return Colors.green;
      default: return Colors.grey;
    }
  }
}

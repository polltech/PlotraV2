import 'package:hive/hive.dart';

part 'latlng_data.g.dart';

@HiveType(typeId: 2)
class LatLngData {
  @HiveField(0)
  final double latitude;
  
  @HiveField(1)
  final double longitude;

  LatLngData({
    required this.latitude,
    required this.longitude,
  });

  factory LatLngData.fromJson(Map<String, dynamic> json) {
    return LatLngData(
      latitude: (json['lat'] as num?)?.toDouble() ?? 0.0,
      longitude: (json['lng'] as num?)?.toDouble() ?? 0.0,
    );
  }

  Map<String, dynamic> toJson() {
    return {
      'lat': latitude,
      'lng': longitude,
    };
  }

  @override
  String toString() => 'LatLng($latitude, $longitude)';
}

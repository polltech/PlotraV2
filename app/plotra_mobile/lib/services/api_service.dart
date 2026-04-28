import 'package:dio/dio.dart';
import 'package:flutter_secure_storage/flutter_secure_storage.dart';
import '../models/user.dart';
import '../models/farm.dart';

class ApiService {
  // Change this to your deployed server URL
  // For DigitalOcean: http://your-domain.com:8000
  // For local testing: http://10.0.2.2:8000 (Android emulator) or http://localhost:8000
  static const String baseUrl = String.fromEnvironment('API_BASE_URL', 
    defaultValue: 'http://10.0.2.2:8000/api/v1');
  
  final Dio _dio;
  final FlutterSecureStorage _storage;
  
  ApiService({
    Dio? dio,
    FlutterSecureStorage? storage,
  }) : _dio = dio ?? Dio(BaseOptions(
          baseUrl: baseUrl,
          connectTimeout: const Duration(seconds: 30),
          receiveTimeout: const Duration(seconds: 30),
          headers: {
            'Content-Type': 'application/json',
            'Accept': 'application/json',
          },
        )),
        _storage = storage ?? const FlutterSecureStorage();

  /// Initialize with stored token
  Future<void> init() async {
    final token = await _storage.read(key: 'auth_token');
    if (token != null) {
      _dio.options.headers['Authorization'] = 'Bearer $token';
    }
  }

  /// AUTHENTICATION
  Future<Map<String, dynamic>> login(String email, String password) async {
    try {
      final response = await _dio.post(
        '/auth/token-form',
        data: {
          'username': email,
          'password': password,
        },
        options: Options(
          contentType: 'application/x-www-form-urlencoded',
        ),
      );
      
      return response.data;
    } on DioException catch (e) {
      throw _handleError(e);
    }
  }

  Future<void> logout() async {
    await _storage.delete(key: 'auth_token');
    _dio.options.headers.remove('Authorization');
  }

  /// FARMS
  Future<List<Farm>> getFarms() async {
    try {
      final response = await _dio.get('/farms/');
      final List<dynamic> data = response.data as List<dynamic>;
      return data.map((json) => Farm.fromJson(json)).toList();
    } on DioException catch (e) {
      throw _handleError(e);
    }
  }

  Future<Farm> getFarm(String id) async {
    try {
      final response = await _dio.get('/farms/$id');
      return Farm.fromJson(response.data);
    } on DioException catch (e) {
      throw _handleError(e);
    }
  }

  Future<Farm> createFarm(Farm farm) async {
    try {
      final response = await _dio.post(
        '/farms/',
        data: farm.toJson(),
      );
      return Farm.fromJson(response.data);
    } on DioException catch (e) {
      throw _handleError(e);
    }
  }

  Future<Farm> updateFarm(String id, Farm farm) async {
    try {
      final response = await _dio.put(
        '/farms/$id',
        data: farm.toJson(),
      );
      return Farm.fromJson(response.data);
    } on DioException catch (e) {
      throw _handleError(e);
    }
  }

  Future<void> deleteFarm(String id) async {
    try {
      await _dio.delete('/farms/$id');
    } on DioException catch (e) {
      throw _handleError(e);
    }
  }

  /// USER
  Future<User> getCurrentUser() async {
    try {
      final response = await _dio.get('/users/me');
      return User.fromJson(response.data);
    } on DioException catch (e) {
      throw _handleError(e);
    }
  }

  Future<User> updateUser(User user) async {
    try {
      final response = await _dio.put(
        '/users/${user.id}',
        data: user.toJson(),
      );
      return User.fromJson(response.data);
    } on DioException catch (e) {
      throw _handleError(e);
    }
  }

  /// COOPERATIVES
  Future<List<dynamic>> getCooperatives() async {
    try {
      final response = await _dio.get('/cooperatives/');
      return response.data as List<dynamic>;
    } on DioException catch (e) {
      throw _handleError(e);
    }
  }

  /// SATELLITE ANALYSIS (Admin only)
  Future<Map<String, dynamic>> analyzeSatellite(List<String> parcelIds) async {
    try {
      final response = await _dio.post(
        '/admin/satellite/analyze',
        data: {'parcel_ids': parcelIds},
      );
      return response.data as Map<String, dynamic>;
    } on DioException catch (e) {
      throw _handleError(e);
    }
  }

  /// DASHBOARD STATS
  Future<Map<String, dynamic>> getDashboardStats() async {
    try {
      final response = await _dio.get('/admin/dashboard/stats');
      return response.data as Map<String, dynamic>;
    } on DioException catch (e) {
      throw _handleError(e);
    }
  }

  /// HELPER: Error handling
  Exception _handleError(DioException e) {
    switch (e.type) {
      case DioExceptionType.connectionTimeout:
      case DioExceptionType.sendTimeout:
      case DioExceptionType.receiveTimeout:
        return Exception('Connection timeout. Please check your internet.');
      
      case DioExceptionType.badResponse:
        final statusCode = e.response?.statusCode;
        final message = e.response?.data?['detail'] ?? e.message;
        
        if (statusCode == 401) {
          return Exception('Unauthorized. Please login again.');
        } else if (statusCode == 403) {
          return Exception('Access denied.');
        } else if (statusCode == 404) {
          return Exception('Resource not found.');
        } else if (statusCode == 422) {
          return Exception('Validation error: ${e.response?.data}');
        }
        return Exception('Server error ($statusCode): $message');
      
      case DioExceptionType.cancel:
        return Exception('Request cancelled.');
      
      case DioExceptionType.connectionError:
        return Exception('No internet connection.');
      
      default:
        return Exception('Unexpected error: ${e.message}');
    }
  }
}

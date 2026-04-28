import 'package:flutter/foundation.dart';
import 'package:flutter_secure_storage/flutter_secure_storage.dart';
import '../models/user.dart';
import 'api_service.dart';

class AuthService extends ChangeNotifier {
  final ApiService _api;
  final FlutterSecureStorage _storage;
  
  User? _user;
  bool _isLoading = false;
  String? _error;
  bool _isInitialized = false;

  AuthService({
    ApiService? api,
    FlutterSecureStorage? storage,
  }) : _api = api ?? ApiService(),
        _storage = storage ?? const FlutterSecureStorage();

  User? get user => _user;
  bool get isAuthenticated => _user != null;
  bool get isLoading => _isLoading;
  String? get error => _error;
  bool get isInitialized => _isInitialized;

  Future<void> init() async {
    await _api.init();
    final token = await _storage.read(key: 'auth_token');
    
    if (token != null) {
      try {
        _user = await _api.getCurrentUser();
      } catch (e) {
        // Token invalid, clear it
        await logout();
      }
    }
    
    _isInitialized = true;
    notifyListeners();
  }

  Future<bool> login(String email, String password) async {
    _isLoading = true;
    _error = null;
    notifyListeners();

    try {
      final response = await _api.login(email, password);
      
      final token = response['access_token'] as String?;
      if (token == null) {
        throw Exception('No token received from server');
      }

      // Save token securely
      await _storage.write(key: 'auth_token', value: token);
      
      // Update API service header
      _api._dio.options.headers['Authorization'] = 'Bearer $token';
      
      // Get user data
      _user = await _api.getCurrentUser();
      
      // Save user to local cache
      await _saveUserToCache(_user!);
      
      _isLoading = false;
      notifyListeners();
      return true;
    } catch (e) {
      _error = e.toString();
      _isLoading = false;
      notifyListeners();
      return false;
    }
  }

  Future<void> logout() async {
    try {
      await _api.logout();
    } finally {
      await _storage.delete(key: 'auth_token');
      await _storage.delete(key: 'user_data');
      _user = null;
      notifyListeners();
    }
  }

  Future<void> _saveUserToCache(User user) async {
    final box = await Hive.openBox('plotra_cache');
    await box.put('current_user', user.toJson());
  }

  Future<void> loadFromCache() async {
    final box = await Hive.openBox('plotra_cache');
    final userData = box.get('current_user');
    if (userData != null) {
      _user = User.fromJson(Map<String, dynamic>.from(userData));
      notifyListeners();
    }
  }

  Future<void> refreshUser() async {
    if (_user != null) {
      try {
        _user = await _api.getCurrentUser();
        await _saveUserToCache(_user!);
        notifyListeners();
      } catch (e) {
        // Silently fail, keep cached data
      }
    }
  }

  void clearError() {
    _error = null;
    notifyListeners();
  }
}

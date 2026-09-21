import 'package:flutter/foundation.dart';
import '../models/user.dart';
import '../models/teacher_profile.dart';
import '../services/auth_service.dart';

class AuthProvider extends ChangeNotifier {
  final AuthService _authService = AuthService();

  User? _user;
  TeacherProfile? _profile;
  bool _isLoading = false;
  String? _errorMessage;

  User? get user => _user;
  TeacherProfile? get profile => _profile;
  bool get isLoading => _isLoading;
  String? get errorMessage => _errorMessage;
  bool get isAuthenticated => _user != null;

  Future<bool> checkAuthStatus() async {
    _isLoading = true;
    notifyListeners();

    try {
      final hasToken = await _authService.isLoggedIn();
      if (!hasToken) {
        _isLoading = false;
        notifyListeners();
        return false;
      }

      _user = await _authService.getCachedUser();
      _profile = await _authService.getCachedTeacherProfile();

      // Refresh teacher profile from API
      try {
        _profile = await _authService.getTeacherProfile();
      } catch (_) {}

      _isLoading = false;
      notifyListeners();
      return _user != null;
    } catch (_) {
      _isLoading = false;
      notifyListeners();
      return false;
    }
  }

  Future<bool> login(String username, String password) async {
    _isLoading = true;
    _errorMessage = null;
    notifyListeners();

    try {
      final res = await _authService.login(username, password);
      _user = res['user'];
      _profile = res['teacher_profile'];
      _isLoading = false;
      notifyListeners();
      return true;
    } catch (e) {
      _errorMessage = e.toString();
      _isLoading = false;
      notifyListeners();
      return false;
    }
  }

  Future<bool> changePassword(String currentPassword, String newPassword) async {
    _isLoading = true;
    _errorMessage = null;
    notifyListeners();

    try {
      await _authService.changePassword(currentPassword, newPassword);
      _isLoading = false;
      notifyListeners();
      return true;
    } catch (e) {
      _errorMessage = e.toString();
      _isLoading = false;
      notifyListeners();
      return false;
    }
  }

  Future<void> logout() async {
    await _authService.logout();
    _user = null;
    _profile = null;
    _errorMessage = null;
    notifyListeners();
  }
}

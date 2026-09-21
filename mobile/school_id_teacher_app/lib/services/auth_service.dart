import 'dart:convert';
import 'package:shared_preferences/shared_preferences.dart';
import '../models/user.dart';
import '../models/teacher_profile.dart';
import '../constants/api_constants.dart';
import 'api_client.dart';

class AuthService {
  final ApiClient _client = ApiClient();

  Future<Map<String, dynamic>> login(String username, String password) async {
    final response = await _client.post(
      ApiConstants.loginEndpoint,
      {
        'username': username.trim(),
        'password': password,
      },
    );

    final prefs = await SharedPreferences.getInstance();
    await prefs.setString('access_token', response['access'] ?? '');
    await prefs.setString('refresh_token', response['refresh'] ?? '');

    if (response['user'] != null) {
      await prefs.setString('cached_user', jsonEncode(response['user']));
    }
    if (response['teacher_profile'] != null) {
      await prefs.setString(
          'cached_teacher_profile', jsonEncode(response['teacher_profile']));
    }

    final user = User.fromJson(response['user']);
    final profile = response['teacher_profile'] != null
        ? TeacherProfile.fromJson(response['teacher_profile'])
        : null;

    return {
      'user': user,
      'teacher_profile': profile,
    };
  }

  Future<void> changePassword(String currentPassword, String newPassword) async {
    await _client.post(
      ApiConstants.changePasswordEndpoint,
      {
        'current_password': currentPassword,
        'new_password': newPassword,
      },
    );
  }

  Future<TeacherProfile> getTeacherProfile() async {
    final response = await _client.get(ApiConstants.teacherProfileEndpoint);
    final profile = TeacherProfile.fromJson(response);

    final prefs = await SharedPreferences.getInstance();
    await prefs.setString('cached_teacher_profile', jsonEncode(response));
    return profile;
  }

  Future<bool> isLoggedIn() async {
    final prefs = await SharedPreferences.getInstance();
    final token = prefs.getString('access_token');
    return token != null && token.isNotEmpty;
  }

  Future<User?> getCachedUser() async {
    final prefs = await SharedPreferences.getInstance();
    final str = prefs.getString('cached_user');
    if (str != null) {
      return User.fromJson(jsonDecode(str));
    }
    return null;
  }

  Future<TeacherProfile?> getCachedTeacherProfile() async {
    final prefs = await SharedPreferences.getInstance();
    final str = prefs.getString('cached_teacher_profile');
    if (str != null) {
      return TeacherProfile.fromJson(jsonDecode(str));
    }
    return null;
  }

  Future<void> logout() async {
    final prefs = await SharedPreferences.getInstance();
    await prefs.remove('access_token');
    await prefs.remove('refresh_token');
    await prefs.remove('cached_user');
    await prefs.remove('cached_teacher_profile');
  }
}

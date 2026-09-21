import 'dart:io';
import '../models/student.dart';
import '../models/dashboard_stats.dart';
import '../models/class_level.dart';
import '../constants/api_constants.dart';
import 'api_client.dart';

class StudentService {
  final ApiClient _client = ApiClient();

  Future<DashboardStats> getDashboardStats() async {
    final response = await _client.get(ApiConstants.dashboardStatsEndpoint);
    return DashboardStats.fromJson(response);
  }

  Future<List<Student>> getStudents({String search = '', String status = ''}) async {
    String query = '';
    final params = <String>[];
    if (search.trim().isNotEmpty) {
      params.add("search=${Uri.encodeComponent(search.trim())}");
    }
    if (status.trim().isNotEmpty) {
      params.add("status=${Uri.encodeComponent(status.trim())}");
    }
    if (params.isNotEmpty) {
      query = "?${params.join('&')}";
    }

    final response = await _client.get("${ApiConstants.studentListEndpoint}$query");
    final list = (response['results'] as List? ?? response as List? ?? []);
    return list.map((json) => Student.fromJson(json)).toList();
  }

  Future<Student> getStudentDetail(int studentId) async {
    final response = await _client.get("${ApiConstants.studentListEndpoint}$studentId/");
    return Student.fromJson(response);
  }

  Future<List<ClassLevelOption>> getClassesAndSections() async {
    final response = await _client.get(ApiConstants.classesSectionsEndpoint);
    final list = (response is List ? response : (response['results'] as List? ?? []));
    return list.map((json) => ClassLevelOption.fromJson(json as Map<String, dynamic>)).toList();
  }

  Future<void> updatePermittedFields(int studentId, Map<String, dynamic> data) async {
    await _client.patch("${ApiConstants.studentListEndpoint}$studentId/update/", data);
  }

  Future<Student> createStudent(Map<String, dynamic> data) async {
    final response = await _client.post("${ApiConstants.studentListEndpoint}create/", data);
    return Student.fromJson(response);
  }

  Future<String> uploadStudentPhoto(int studentId, File imageFile) async {
    final response = await _client.uploadMultipart(
      "${ApiConstants.studentListEndpoint}$studentId/photo/",
      'photo',
      imageFile,
    );
    return response['photo_url'] ?? '';
  }

  Future<void> submitForVerification(int studentId, {String notes = ''}) async {
    await _client.post(
      "${ApiConstants.studentListEndpoint}$studentId/submit-verification/",
      {'notes': notes},
    );
  }
}

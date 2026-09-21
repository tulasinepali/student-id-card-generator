import 'dart:io';
import 'package:flutter/foundation.dart';
import '../models/student.dart';
import '../models/class_level.dart';
import '../services/student_service.dart';

class StudentProvider extends ChangeNotifier {
  final StudentService _studentService = StudentService();

  List<Student> _students = [];
  bool _isLoading = false;
  String? _errorMessage;
  String _searchQuery = '';
  String _statusFilter = '';

  List<Student> get students => _students;
  bool get isLoading => _isLoading;
  String? get errorMessage => _errorMessage;
  String get searchQuery => _searchQuery;
  String get statusFilter => _statusFilter;

  Future<void> fetchStudents({bool refresh = false}) async {
    _isLoading = true;
    _errorMessage = null;
    if (refresh) notifyListeners();

    try {
      _students = await _studentService.getStudents(
        search: _searchQuery,
        status: _statusFilter,
      );
      _isLoading = false;
      notifyListeners();
    } catch (e) {
      _errorMessage = e.toString();
      _isLoading = false;
      notifyListeners();
    }
  }

  void setSearchQuery(String query) {
    _searchQuery = query;
    fetchStudents();
  }

  void setStatusFilter(String status) {
    _statusFilter = status;
    fetchStudents();
  }

  void clearFilters() {
    _searchQuery = '';
    _statusFilter = '';
    fetchStudents();
  }

  Future<Student> getStudentDetail(int studentId) async {
    return await _studentService.getStudentDetail(studentId);
  }

  Future<bool> updatePermittedFields(int studentId, Map<String, dynamic> data) async {
    try {
      await _studentService.updatePermittedFields(studentId, data);
      await fetchStudents();
      return true;
    } catch (e) {
      _errorMessage = e.toString();
      notifyListeners();
      return false;
    }
  }

  Future<Student?> createStudent(Map<String, dynamic> data) async {
    try {
      final newStudent = await _studentService.createStudent(data);
      await fetchStudents();
      return newStudent;
    } catch (e) {
      _errorMessage = e.toString();
      notifyListeners();
      return null;
    }
  }

  Future<String?> uploadPhoto(int studentId, File imageFile) async {
    try {
      final photoUrl = await _studentService.uploadStudentPhoto(studentId, imageFile);
      await fetchStudents();
      return photoUrl;
    } catch (e) {
      _errorMessage = e.toString();
      notifyListeners();
      return null;
    }
  }

  Future<List<ClassLevelOption>> getClassesAndSections() async {
    return await _studentService.getClassesAndSections();
  }

  Future<bool> submitVerification(int studentId, {String notes = ''}) async {
    try {
      await _studentService.submitForVerification(studentId, notes: notes);
      await fetchStudents();
      return true;
    } catch (e) {
      _errorMessage = e.toString();
      notifyListeners();
      return false;
    }
  }
}

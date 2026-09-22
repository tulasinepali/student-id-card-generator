import 'dart:convert';
import 'dart:io';
import 'package:http/http.dart' as http;
import 'package:shared_preferences/shared_preferences.dart';
import '../constants/api_constants.dart';

class ApiException implements Exception {
  final String message;
  final int? statusCode;
  ApiException(this.message, {this.statusCode});

  @override
  String toString() => message;
}

class ApiClient {
  static final ApiClient _instance = ApiClient._internal();
  factory ApiClient() => _instance;
  ApiClient._internal();

  String? _baseUrl;

  Future<String> get baseUrl async {
    if (_baseUrl != null) return _baseUrl!;
    final prefs = await SharedPreferences.getInstance();
    final custom = prefs.getString('custom_base_url');
    if (custom != null && !custom.contains('192.168.') && !custom.contains('127.0.0.1') && !custom.contains('10.0.2.2')) {
      _baseUrl = custom;
    } else {
      _baseUrl = ApiConstants.defaultBaseUrl;
      await prefs.setString('custom_base_url', _baseUrl!);
    }
    return _baseUrl!;
  }


  Future<void> setCustomBaseUrl(String url) async {
    _baseUrl = url.trim().replaceAll(RegExp(r'/+$'), '');
    final prefs = await SharedPreferences.getInstance();
    await prefs.setString('custom_base_url', _baseUrl!);
  }

  Future<void> resetToDefaultBaseUrl() async {
    _baseUrl = ApiConstants.defaultBaseUrl;
    final prefs = await SharedPreferences.getInstance();
    await prefs.remove('custom_base_url');
  }

  Future<Map<String, dynamic>> testConnection(String candidateUrl) async {
    String cleanUrl = candidateUrl.trim().replaceAll(RegExp(r'/+$'), '');
    if (!cleanUrl.endsWith('/api')) {
      cleanUrl = '$cleanUrl/api';
    }
    final uri = Uri.parse('$cleanUrl${ApiConstants.appConfigEndpoint}');
    try {
      final response = await http
          .get(uri, headers: {'Accept': 'application/json'})
          .timeout(const Duration(seconds: 4));
      if (response.statusCode >= 200 && response.statusCode < 300) {
        final body = jsonDecode(response.body);
        return {
          'success': true,
          'message': 'Connected! ${body['app_name'] ?? 'Server'} (v${body['version'] ?? '1.0'})',
        };
      } else {
        return {
          'success': false,
          'message': 'Server responded with HTTP ${response.statusCode}',
        };
      }
    } on SocketException {
      return {
        'success': false,
        'message': 'Connection refused. Ensure server is running on $cleanUrl and device is on same network.',
      };
    } catch (e) {
      return {
        'success': false,
        'message': 'Error: ${e.toString().replaceAll('Exception: ', '')}',
      };
    }
  }


  Future<Map<String, String>> _getHeaders({bool isMultipart = false}) async {
    final prefs = await SharedPreferences.getInstance();
    final token = prefs.getString('access_token');

    final headers = <String, String>{
      'Accept': 'application/json',
    };
    if (!isMultipart) {
      headers['Content-Type'] = 'application/json';
    }
    if (token != null && token.isNotEmpty) {
      headers['Authorization'] = 'Bearer $token';
    }
    return headers;
  }

  Future<dynamic> get(String endpoint) async {
    final base = await baseUrl;
    final uri = Uri.parse('$base$endpoint');

    try {
      final headers = await _getHeaders();
      final response = await http
          .get(uri, headers: headers)
          .timeout(ApiConstants.timeoutDuration);
      return _processResponse(response);
    } on SocketException {
      throw ApiException(
          "Unable to connect to organization server. Please verify your network connection.");
    } on http.ClientException {
      throw ApiException("Network client error. Please check server status.");
    } catch (e) {
      if (e is ApiException) rethrow;
      throw ApiException("Request failed: ${e.toString()}");
    }
  }

  Future<dynamic> post(String endpoint, Map<String, dynamic> body) async {
    final base = await baseUrl;
    final uri = Uri.parse('$base$endpoint');

    try {
      final headers = await _getHeaders();
      final response = await http
          .post(uri, headers: headers, body: jsonEncode(body))
          .timeout(ApiConstants.timeoutDuration);
      return _processResponse(response);
    } on SocketException {
      throw ApiException("Unable to connect to server. Check connection.");
    } catch (e) {
      if (e is ApiException) rethrow;
      throw ApiException("Request failed: ${e.toString()}");
    }
  }

  Future<dynamic> patch(String endpoint, Map<String, dynamic> body) async {
    final base = await baseUrl;
    final uri = Uri.parse('$base$endpoint');

    try {
      final headers = await _getHeaders();
      final response = await http
          .patch(uri, headers: headers, body: jsonEncode(body))
          .timeout(ApiConstants.timeoutDuration);
      return _processResponse(response);
    } on SocketException {
      throw ApiException("Unable to connect to server. Check connection.");
    } catch (e) {
      if (e is ApiException) rethrow;
      throw ApiException("Request failed: ${e.toString()}");
    }
  }

  Future<dynamic> uploadMultipart(
      String endpoint, String fieldName, File file) async {
    final base = await baseUrl;
    final uri = Uri.parse('$base$endpoint');

    try {
      final request = http.MultipartRequest('POST', uri);
      final headers = await _getHeaders(isMultipart: true);
      request.headers.addAll(headers);

      request.files.add(
        await http.MultipartFile.fromPath(fieldName, file.path),
      );

      final streamedResponse =
          await request.send().timeout(const Duration(seconds: 40));
      final response = await http.Response.fromStream(streamedResponse);
      return _processResponse(response);
    } on SocketException {
      throw ApiException("Network error during photo upload. Please retry.");
    } catch (e) {
      if (e is ApiException) rethrow;
      throw ApiException("Photo upload failed: ${e.toString()}");
    }
  }

  dynamic _processResponse(http.Response response) {
    dynamic body;
    try {
      body = jsonDecode(response.body);
    } catch (_) {
      body = response.body;
    }

    if (response.statusCode >= 200 && response.statusCode < 300) {
      return body;
    }

    String errorMsg = "An error occurred.";
    if (body is Map) {
      if (body.containsKey('error')) {
        errorMsg = body['error'].toString();
      } else if (body.containsKey('detail')) {
        errorMsg = body['detail'].toString();
      } else if (body.containsKey('message')) {
        errorMsg = body['message'].toString();
      } else {
        errorMsg = body.entries.map((e) => "${e.key}: ${e.value}").join('\n');
      }
    }

    if (response.statusCode == 401) {
      throw ApiException("Session expired or unauthorized. Please sign in again.",
          statusCode: 401);
    } else if (response.statusCode == 403) {
      throw ApiException(
          errorMsg.isNotEmpty ? errorMsg : "You do not have permission to access this student.",
          statusCode: 403);
    } else if (response.statusCode == 404) {
      throw ApiException(errorMsg.isNotEmpty ? errorMsg : "Resource not found.",
          statusCode: 404);
    }

    throw ApiException(errorMsg, statusCode: response.statusCode);
  }
}

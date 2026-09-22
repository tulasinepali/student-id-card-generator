class ApiConstants {

  // Production Server API Base URL
  static const String defaultBaseUrl = "http://id.tulasinepali.com.np/api";


  // Endpoints
  static const String loginEndpoint = "/auth/login/";
  static const String refreshTokenEndpoint = "/auth/refresh/";
  static const String teacherProfileEndpoint = "/teacher/profile/";
  static const String changePasswordEndpoint = "/teacher/change-password/";
  static const String dashboardStatsEndpoint = "/teacher/dashboard/";
  static const String studentListEndpoint = "/teacher/students/";
  static const String qrVerificationEndpoint = "/verify-qr/";
  static const String appConfigEndpoint = "/app-config/";
  static const String classesSectionsEndpoint = "/academic/classes-sections/";

  static const Duration timeoutDuration = Duration(seconds: 15);
}

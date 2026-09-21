import 'dart:io';
import 'package:flutter/foundation.dart';

class ApiConstants {
  // Local development host coordinates
  static const String localWifiHost = "192.168.1.72";
  static const String emulatorHost = "10.0.2.2";
  static const String localhost = "127.0.0.1";
  static const String defaultPort = "8000";

  // Default development URLs
  static String get defaultBaseUrl {
    if (kIsWeb) {
      return "http://$localhost:$defaultPort/api";
    }
    try {
      if (Platform.isAndroid || Platform.isIOS) {
        // Default to Wi-Fi IP so real phones on same Wi-Fi connect seamlessly
        return "http://$localWifiHost:$defaultPort/api";
      }
    } catch (_) {}
    return "http://$localWifiHost:$defaultPort/api";
  }

  // Preset development URLs for quick switching in UI
  static List<Map<String, String>> get serverPresets => [
    {
      'label': 'Wi-Fi Phone (Real Device)',
      'url': 'http://$localWifiHost:$defaultPort/api',
      'desc': 'Phone & PC on same Wi-Fi network ($localWifiHost)',
    },
    {
      'label': 'Android Emulator',
      'url': 'http://$emulatorHost:$defaultPort/api',
      'desc': 'Standard Android Studio Emulator host loopback',
    },
    {
      'label': 'Localhost / USB ADB',
      'url': 'http://$localhost:$defaultPort/api',
      'desc': 'Web, Desktop, or USB with adb reverse tcp:8000',
    },
  ];

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

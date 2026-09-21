import '../models/qr_result.dart';
import '../constants/api_constants.dart';
import 'api_client.dart';

class QRService {
  final ApiClient _client = ApiClient();

  Future<QRResult> verifyToken(String rawToken) async {
    String token = rawToken.trim();
    // Handle full verification URLs like http://.../verify/<uuid>/
    if (token.contains("/verify/")) {
      final parts = token.split("/verify/");
      if (parts.length > 1) {
        token = parts[1].replaceAll('/', '').trim();
      }
    }

    try {
      final response = await _client.get("${ApiConstants.qrVerificationEndpoint}$token/");
      return QRResult.fromJson(response);
    } on ApiException catch (e) {
      if (e.statusCode == 404) {
        return QRResult(
          status: 'INVALID',
          statusDisplay: 'INVALID ID CARD',
          message: 'The scanned QR code is invalid or counterfeit.',
        );
      }
      rethrow;
    }
  }
}

import 'package:flutter/material.dart';
import '../models/qr_result.dart';
import '../services/qr_service.dart';
import '../services/api_client.dart';
import '../constants/app_colors.dart';
import 'qr_scanner_screen.dart';

class QRResultScreen extends StatefulWidget {
  final String rawToken;

  const QRResultScreen({super.key, required this.rawToken});

  @override
  State<QRResultScreen> createState() => _QRResultScreenState();
}

class _QRResultScreenState extends State<QRResultScreen> {
  final QRService _qrService = QRService();
  QRResult? _result;
  bool _isLoading = true;
  String? _networkError;

  @override
  void initState() {
    super.initState();
    _verify();
  }

  Future<void> _verify() async {
    setState(() {
      _isLoading = true;
      _networkError = null;
    });

    try {
      final res = await _qrService.verifyToken(widget.rawToken);
      setState(() {
        _result = res;
        _isLoading = false;
      });
    } on ApiException catch (e) {
      setState(() {
        _networkError = e.message;
        _isLoading = false;
      });
    } catch (e) {
      setState(() {
        _networkError = "Network error: Unable to verify QR code with organization server. Check internet connection.";
        _isLoading = false;
      });
    }
  }

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      backgroundColor: AppColors.background,
      appBar: AppBar(
        title: const Text("Scan Verification Result", style: TextStyle(fontWeight: FontWeight.bold, fontSize: 17)),
        backgroundColor: AppColors.primary,
        foregroundColor: Colors.white,
        elevation: 0,
      ),
      body: _isLoading
          ? const Center(
              child: Column(
                mainAxisAlignment: MainAxisAlignment.center,
                children: [
                  CircularProgressIndicator(),
                  SizedBox(height: 16),
                  Text("Validating digital signature...", style: TextStyle(color: AppColors.textMuted)),
                ],
              ),
            )
          : _networkError != null
              // Requirement 37: "If network is unavailable, show a clear error rather than fake verification."
              ? Center(
                  child: Padding(
                    padding: const EdgeInsets.all(24.0),
                    child: Column(
                      mainAxisAlignment: MainAxisAlignment.center,
                      children: [
                        const Icon(Icons.signal_wifi_connected_no_internet_4, size: 56, color: Colors.orange),
                        const SizedBox(height: 16),
                        const Text(
                          "Verification Offline",
                          style: TextStyle(fontSize: 18, fontWeight: FontWeight.bold, color: AppColors.textDark),
                        ),
                        const SizedBox(height: 8),
                        Text(
                          _networkError!,
                          textAlign: TextAlign.center,
                          style: const TextStyle(fontSize: 13, color: AppColors.textMuted),
                        ),
                        const SizedBox(height: 24),
                        Row(
                          mainAxisAlignment: MainAxisAlignment.center,
                          children: [
                            OutlinedButton.icon(
                              onPressed: () => Navigator.pushReplacement(
                                context,
                                MaterialPageRoute(builder: (_) => const QRScannerScreen()),
                              ),
                              icon: const Icon(Icons.qr_code_scanner),
                              label: const Text("Scan Another"),
                            ),
                            const SizedBox(width: 12),
                            ElevatedButton.icon(
                              onPressed: _verify,
                              icon: const Icon(Icons.refresh),
                              label: const Text("Retry"),
                              style: ElevatedButton.styleFrom(backgroundColor: AppColors.primary, foregroundColor: Colors.white),
                            ),
                          ],
                        ),
                      ],
                    ),
                  ),
                )
              : _result == null
                  ? const Center(child: Text("Verification result unavailable."))
                  : SingleChildScrollView(
                      padding: const EdgeInsets.all(16),
                      child: Column(
                        crossAxisAlignment: CrossAxisAlignment.stretch,
                        children: [
                          // Result Header Card
                          Card(
                            elevation: 0,
                            shape: RoundedRectangleBorder(
                              borderRadius: BorderRadius.circular(16),
                              side: BorderSide(
                                color: _result!.isValid
                                    ? Colors.green.shade400
                                    : _result!.isExpired
                                        ? Colors.orange.shade400
                                        : Colors.red.shade400,
                                width: 2,
                              ),
                            ),
                            child: Padding(
                              padding: const EdgeInsets.all(20),
                              child: Column(
                                children: [
                                  Icon(
                                    _result!.isValid
                                        ? Icons.verified
                                        : _result!.isExpired
                                            ? Icons.warning_amber_rounded
                                            : Icons.cancel,
                                    size: 64,
                                    color: _result!.isValid
                                        ? Colors.green
                                        : _result!.isExpired
                                            ? Colors.orange
                                            : Colors.red,
                                  ),
                                  const SizedBox(height: 12),
                                  Text(
                                    _result!.statusDisplay,
                                    style: TextStyle(
                                      fontSize: 20,
                                      fontWeight: FontWeight.bold,
                                      color: _result!.isValid
                                          ? Colors.green.shade800
                                          : _result!.isExpired
                                              ? Colors.orange.shade800
                                              : Colors.red.shade800,
                                    ),
                                  ),
                                  const SizedBox(height: 6),
                                  Text(
                                    _result!.message,
                                    textAlign: TextAlign.center,
                                    style: const TextStyle(fontSize: 13, color: AppColors.textMuted),
                                  ),
                                ],
                              ),
                            ),
                          ),
                          const SizedBox(height: 16),

                          // Student Details (if recognized)
                          if (_result!.studentName != null)
                            Card(
                              elevation: 0,
                              color: Colors.white,
                              shape: RoundedRectangleBorder(
                                borderRadius: BorderRadius.circular(12),
                                side: const BorderSide(color: AppColors.border),
                              ),
                              child: Padding(
                                padding: const EdgeInsets.all(16),
                                child: Column(
                                  children: [
                                    if (_result!.photoUrl != null) ...[
                                      ClipRRect(
                                        borderRadius: BorderRadius.circular(10),
                                        child: Image.network(
                                          _result!.photoUrl!,
                                          width: 90,
                                          height: 120,
                                          fit: BoxFit.cover,
                                          errorBuilder: (context, error, stackTrace) => const Icon(Icons.person, size: 64),
                                        ),
                                      ),
                                      const SizedBox(height: 12),
                                    ],
                                    Text(
                                      _result!.studentName!,
                                      style: const TextStyle(fontSize: 17, fontWeight: FontWeight.bold),
                                    ),
                                    Text(
                                      "Student ID: ${_result!.studentId}",
                                      style: const TextStyle(fontSize: 13, color: AppColors.primaryLight, fontWeight: FontWeight.bold),
                                    ),
                                    const Divider(height: 24),
                                    _buildDetailRow("Organization", _result!.schoolName ?? "Organization"),
                                    _buildDetailRow("Class & Section", "${_result!.className} - Sec ${_result!.sectionName}"),
                                    _buildDetailRow("Card Number", _result!.cardNumber ?? "-"),
                                    _buildDetailRow("Valid Until", _result!.validUntil ?? "-"),
                                  ],
                                ),
                              ),
                            ),
                          const SizedBox(height: 24),

                          ElevatedButton.icon(
                            onPressed: () => Navigator.pushReplacement(
                              context,
                              MaterialPageRoute(builder: (_) => const QRScannerScreen()),
                            ),
                            icon: const Icon(Icons.qr_code_scanner),
                            label: const Text("Scan Next Card"),
                            style: ElevatedButton.styleFrom(
                              backgroundColor: AppColors.primary,
                              foregroundColor: Colors.white,
                              padding: const EdgeInsets.symmetric(vertical: 14),
                              shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(10)),
                            ),
                          ),
                        ],
                      ),
                    ),
    );
  }

  Widget _buildDetailRow(String label, String value) {
    return Padding(
      padding: const EdgeInsets.symmetric(vertical: 4),
      child: Row(
        mainAxisAlignment: MainAxisAlignment.spaceBetween,
        children: [
          Text(label, style: const TextStyle(fontSize: 13, color: AppColors.textMuted)),
          Text(value, style: const TextStyle(fontSize: 13, fontWeight: FontWeight.w600, color: AppColors.textDark)),
        ],
      ),
    );
  }
}

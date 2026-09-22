import 'package:flutter/material.dart';
import 'package:url_launcher/url_launcher.dart';
import '../constants/app_colors.dart';
import '../constants/app_config.dart';
import '../constants/api_constants.dart';
import '../services/api_client.dart';

class AboutScreen extends StatefulWidget {
  const AboutScreen({super.key});

  @override
  State<AboutScreen> createState() => _AboutScreenState();
}

class _AboutScreenState extends State<AboutScreen> {
  String _appName = AppConfig.appName;
  String _appVersion = AppConfig.appVersion;
  String _appDescription = AppConfig.appDescription;
  String? _logoUrl;
  String _designerName = AppConfig.designerName;
  String _designerRole = AppConfig.designerRole;
  String _contactPhone = AppConfig.contactPhone;
  String _contactEmail = AppConfig.contactEmail;
  String _website = AppConfig.website;
  String _copyrightYear = AppConfig.copyrightYear;

  @override
  void initState() {
    super.initState();
    _fetchAppConfig();
  }

  Future<void> _fetchAppConfig() async {
    try {
      final response = await ApiClient().get(ApiConstants.appConfigEndpoint);
      if (response != null && response is Map<String, dynamic>) {
        if (mounted) {
          setState(() {
            _appName = (response['app_name'] != null && response['app_name'].toString().isNotEmpty)
                ? response['app_name']
                : AppConfig.appName;
            _appVersion = (response['version'] != null && response['version'].toString().isNotEmpty)
                ? response['version']
                : AppConfig.appVersion;
            _appDescription = (response['description'] != null && response['description'].toString().isNotEmpty)
                ? response['description']
                : AppConfig.appDescription;
            _logoUrl = response['logo_url'];
            _designerName = (response['designer_name'] != null && response['designer_name'].toString().isNotEmpty)
                ? response['designer_name']
                : AppConfig.designerName;
            _designerRole = (response['designer_role'] != null && response['designer_role'].toString().isNotEmpty)
                ? response['designer_role']
                : AppConfig.designerRole;
            _contactPhone = (response['contact_phone'] != null && response['contact_phone'].toString().isNotEmpty)
                ? response['contact_phone']
                : AppConfig.contactPhone;
            _contactEmail = (response['contact_email'] != null && response['contact_email'].toString().isNotEmpty)
                ? response['contact_email']
                : AppConfig.contactEmail;
            _website = (response['website'] != null && response['website'].toString().isNotEmpty)
                ? response['website']
                : AppConfig.website;
            _copyrightYear = (response['copyright_year'] != null && response['copyright_year'].toString().isNotEmpty)
                ? response['copyright_year']
                : AppConfig.copyrightYear;
          });
        }
      }
    } catch (_) {
      // Offline fallback: retains defaults from AppConfig
    }
  }

  Future<void> _launchUrl(String urlString) async {
    final uri = Uri.parse(urlString);
    try {
      if (await canLaunchUrl(uri)) {
        await launchUrl(uri, mode: LaunchMode.externalApplication);
      }
    } catch (_) {}
  }

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      backgroundColor: AppColors.background,
      appBar: AppBar(
        title: const Text("About the App", style: TextStyle(fontWeight: FontWeight.bold, fontSize: 17)),
        backgroundColor: AppColors.primary,
        foregroundColor: Colors.white,
        elevation: 0,
      ),
      body: SingleChildScrollView(
        padding: const EdgeInsets.all(20),
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.stretch,
          children: [
            // App Emblem / Logo
            Center(
              child: Container(
                width: 80,
                height: 80,
                decoration: BoxDecoration(
                  color: Colors.white,
                  borderRadius: BorderRadius.circular(20),
                  border: Border.all(color: AppColors.border),
                  boxShadow: [
                    BoxShadow(
                      color: AppColors.primary.withValues(alpha: 0.15),
                      blurRadius: 15,
                      offset: const Offset(0, 5),
                    )
                  ],
                ),
                child: ClipRRect(
                  borderRadius: BorderRadius.circular(20),
                  child: (_logoUrl != null && _logoUrl!.isNotEmpty)
                      ? Image.network(
                          _logoUrl!,
                          width: 80,
                          height: 80,
                          fit: BoxFit.contain,
                          errorBuilder: (ctx, error, stackTrace) => Container(
                            color: AppColors.primary,
                            child: const Icon(Icons.badge_rounded, size: 48, color: Colors.white),
                          ),
                        )
                      : Container(
                          color: AppColors.primary,
                          child: const Icon(Icons.badge_rounded, size: 48, color: Colors.white),
                        ),
                ),
              ),
            ),
            const SizedBox(height: 16),

            // Application Name & Version
            Text(
              _appName,
              textAlign: TextAlign.center,
              style: const TextStyle(fontSize: 20, fontWeight: FontWeight.bold, color: AppColors.textDark),
            ),
            const SizedBox(height: 4),
            Text(
              "Version: $_appVersion",
              textAlign: TextAlign.center,
              style: const TextStyle(fontSize: 13, color: AppColors.primaryLight, fontWeight: FontWeight.w600),
            ),
            const SizedBox(height: 12),

            // Description
            Card(
              elevation: 0,
              color: Colors.white,
              shape: RoundedRectangleBorder(
                borderRadius: BorderRadius.circular(12),
                side: const BorderSide(color: AppColors.border),
              ),
              child: Padding(
                padding: const EdgeInsets.all(16),
                child: Text(
                  _appDescription,
                  textAlign: TextAlign.center,
                  style: const TextStyle(fontSize: 13, color: AppColors.textDark, height: 1.4),
                ),
              ),
            ),
            const SizedBox(height: 20),

            // Designed & Developed By Card
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
                  crossAxisAlignment: CrossAxisAlignment.start,
                  children: [
                    const Row(
                      children: [
                        Icon(Icons.code_rounded, color: AppColors.primary, size: 20),
                        SizedBox(width: 8),
                        Text(
                          "Designed & Developed By",
                          style: TextStyle(fontSize: 14, fontWeight: FontWeight.bold, color: AppColors.textDark),
                        ),
                      ],
                    ),
                    const Divider(height: 20),
                    _buildFieldRow("Name", _designerName),
                    _buildFieldRow("Role", _designerRole),
                  ],
                ),
              ),
            ),
            const SizedBox(height: 16),

            // Contact Information (Tappable links)
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
                  crossAxisAlignment: CrossAxisAlignment.start,
                  children: [
                    const Row(
                      children: [
                        Icon(Icons.contact_support_outlined, color: AppColors.primary, size: 20),
                        SizedBox(width: 8),
                        Text(
                          "Contact",
                          style: TextStyle(fontSize: 14, fontWeight: FontWeight.bold, color: AppColors.textDark),
                        ),
                      ],
                    ),
                    const Divider(height: 20),

                    // Phone (Tappable tel:)
                    ListTile(
                      contentPadding: EdgeInsets.zero,
                      leading: const Icon(Icons.phone_outlined, color: AppColors.primaryLight, size: 20),
                      title: const Text("Phone", style: TextStyle(fontSize: 12, color: AppColors.textMuted)),
                      subtitle: Text(
                        _contactPhone,
                        style: const TextStyle(fontSize: 14, fontWeight: FontWeight.w600, color: AppColors.primaryLight),
                      ),
                      trailing: const Icon(Icons.open_in_new, size: 16, color: AppColors.textMuted),
                      onTap: () => _launchUrl("tel:$_contactPhone"),
                    ),
                    const Divider(height: 1),

                    // Email (Tappable mailto:)
                    ListTile(
                      contentPadding: EdgeInsets.zero,
                      leading: const Icon(Icons.email_outlined, color: AppColors.primaryLight, size: 20),
                      title: const Text("Email", style: TextStyle(fontSize: 12, color: AppColors.textMuted)),
                      subtitle: Text(
                        _contactEmail,
                        style: const TextStyle(fontSize: 14, fontWeight: FontWeight.w600, color: AppColors.primaryLight),
                      ),
                      trailing: const Icon(Icons.open_in_new, size: 16, color: AppColors.textMuted),
                      onTap: () => _launchUrl("mailto:$_contactEmail?subject=Organization%20ID%20App%20Inquiry"),
                    ),
                    const Divider(height: 1),

                    // Website (Tappable web url)
                    ListTile(
                      contentPadding: EdgeInsets.zero,
                      leading: const Icon(Icons.language_outlined, color: AppColors.primaryLight, size: 20),
                      title: const Text("Website", style: TextStyle(fontSize: 12, color: AppColors.textMuted)),
                      subtitle: Text(
                        _website,
                        style: const TextStyle(fontSize: 14, fontWeight: FontWeight.w600, color: AppColors.primaryLight),
                      ),
                      trailing: const Icon(Icons.open_in_new, size: 16, color: AppColors.textMuted),
                      onTap: () {
                        String url = _website;
                        if (!url.startsWith("http://") && !url.startsWith("https://")) {
                          url = "https://$url";
                        }
                        _launchUrl(url);
                      },
                    ),
                  ],
                ),
              ),
            ),
            const SizedBox(height: 32),

            // Copyright footer
            Center(
              child: Text(
                "© $_copyrightYear $_designerName",
                textAlign: TextAlign.center,
                style: const TextStyle(fontSize: 12, color: AppColors.textMuted, fontWeight: FontWeight.w500),
              ),
            ),
          ],
        ),
      ),
    );
  }

  Widget _buildFieldRow(String label, String value) {
    return Padding(
      padding: const EdgeInsets.symmetric(vertical: 6),
      child: Row(
        mainAxisAlignment: MainAxisAlignment.spaceBetween,
        children: [
          Text(label, style: const TextStyle(fontSize: 13, color: AppColors.textMuted)),
          Text(value, style: const TextStyle(fontSize: 13, fontWeight: FontWeight.bold, color: AppColors.textDark)),
        ],
      ),
    );
  }
}

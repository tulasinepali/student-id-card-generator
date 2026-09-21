import 'package:flutter/material.dart';
import 'package:provider/provider.dart';
import '../models/student.dart';
import '../providers/student_provider.dart';
import '../constants/app_colors.dart';
import '../widgets/status_badge.dart';
import 'student_edit_screen.dart';
import 'photo_upload_screen.dart';

class StudentDetailScreen extends StatefulWidget {
  final int studentId;

  const StudentDetailScreen({super.key, required this.studentId});

  @override
  State<StudentDetailScreen> createState() => _StudentDetailScreenState();
}

class _StudentDetailScreenState extends State<StudentDetailScreen> {
  Student? _student;
  bool _isLoading = true;
  String? _errorMessage;

  @override
  void initState() {
    super.initState();
    _loadDetail();
  }

  Future<void> _loadDetail() async {
    setState(() {
      _isLoading = true;
      _errorMessage = null;
    });

    try {
      final provider = Provider.of<StudentProvider>(context, listen: false);
      final s = await provider.getStudentDetail(widget.studentId);
      setState(() {
        _student = s;
        _isLoading = false;
      });
    } catch (e) {
      setState(() {
        _errorMessage = e.toString();
        _isLoading = false;
      });
    }
  }

  Future<void> _submitForVerification() async {
    if (_student == null) return;

    if (!_student!.hasPhoto) {
      ScaffoldMessenger.of(context).showSnackBar(
        const SnackBar(
          content: Text("A student photo is mandatory before submitting for verification."),
          backgroundColor: Colors.orange,
        ),
      );
      return;
    }

    final confirmed = await showDialog<bool>(
      context: context,
      builder: (ctx) => AlertDialog(
        title: const Text("Submit for Verification?", style: TextStyle(fontSize: 16, fontWeight: FontWeight.bold)),
        content: Text(
          "Submit ${_student!.fullName}'s profile to the administration for final ID-card approval?",
          style: const TextStyle(fontSize: 13),
        ),
        actions: [
          TextButton(onPressed: () => Navigator.pop(ctx, false), child: const Text("Cancel")),
          ElevatedButton(
            onPressed: () => Navigator.pop(ctx, true),
            style: ElevatedButton.styleFrom(backgroundColor: AppColors.primary, foregroundColor: Colors.white),
            child: const Text("Confirm Submit"),
          ),
        ],
      ),
    );

    if (confirmed != true) return;
    if (!mounted) return;

    final provider = Provider.of<StudentProvider>(context, listen: false);
    final success = await provider.submitVerification(_student!.id);

    if (!mounted) return;

    if (success) {
      ScaffoldMessenger.of(context).showSnackBar(
        const SnackBar(
          content: Text("Submitted to administrator for verification."),
          backgroundColor: Colors.green,
        ),
      );
      _loadDetail();
    } else {
      ScaffoldMessenger.of(context).showSnackBar(
        SnackBar(
          content: Text(provider.errorMessage ?? "Submission failed."),
          backgroundColor: Colors.red,
        ),
      );
    }
  }

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      backgroundColor: AppColors.background,
      appBar: AppBar(
        title: const Text("Student Information", style: TextStyle(fontWeight: FontWeight.bold, fontSize: 17)),
        backgroundColor: AppColors.primary,
        foregroundColor: Colors.white,
        elevation: 0,
        actions: [
          if (_student != null)
            IconButton(
              icon: const Icon(Icons.edit_outlined),
              tooltip: "Edit Student Details",
              onPressed: () async {
                final updated = await Navigator.push<bool>(
                  context,
                  MaterialPageRoute(
                    builder: (_) => StudentEditScreen(student: _student!),
                  ),
                );
                if (updated == true) _loadDetail();
              },
            ),
        ],
      ),
      body: _isLoading
          ? const Center(child: CircularProgressIndicator())
          : _errorMessage != null
              ? Center(
                  child: Padding(
                    padding: const EdgeInsets.all(24.0),
                    child: Column(
                      mainAxisAlignment: MainAxisAlignment.center,
                      children: [
                        const Icon(Icons.error_outline, size: 48, color: Colors.red),
                        const SizedBox(height: 12),
                        Text(_errorMessage!, textAlign: TextAlign.center),
                        const SizedBox(height: 16),
                        ElevatedButton(onPressed: _loadDetail, child: const Text("Retry")),
                      ],
                    ),
                  ),
                )
              : _student == null
                  ? const Center(child: Text("Student not found"))
                  : SingleChildScrollView(
                      padding: const EdgeInsets.all(16),
                      child: Column(
                        crossAxisAlignment: CrossAxisAlignment.stretch,
                        children: [
                          // Header Profile Card
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
                                  // Photo with Change Photo Badge
                                  Stack(
                                    alignment: Alignment.bottomRight,
                                    children: [
                                      ClipRRect(
                                        borderRadius: BorderRadius.circular(12),
                                        child: _student!.hasPhoto && _student!.photo != null
                                            ? Image.network(
                                                _student!.photo!,
                                                width: 110,
                                                height: 140,
                                                fit: BoxFit.cover,
                                                errorBuilder: (context, error, stackTrace) => Container(
                                                  width: 110,
                                                  height: 140,
                                                  color: Colors.grey.shade200,
                                                  child: const Icon(Icons.person, size: 48, color: Colors.grey),
                                                ),
                                              )
                                            : Container(
                                                width: 110,
                                                height: 140,
                                                color: Colors.grey.shade100,
                                                child: const Icon(Icons.person_outline, size: 48, color: Colors.grey),
                                              ),
                                      ),
                                      GestureDetector(
                                        onTap: () async {
                                          final updated = await Navigator.push<bool>(
                                            context,
                                            MaterialPageRoute(
                                              builder: (_) => PhotoUploadScreen(student: _student!),
                                            ),
                                          );
                                          if (updated == true) _loadDetail();
                                        },
                                        child: Container(
                                          padding: const EdgeInsets.all(6),
                                          decoration: BoxDecoration(
                                            color: AppColors.primary,
                                            shape: BoxShape.circle,
                                            border: Border.all(color: Colors.white, width: 2),
                                          ),
                                          child: const Icon(Icons.camera_alt, color: Colors.white, size: 16),
                                        ),
                                      ),
                                    ],
                                  ),
                                  const SizedBox(height: 12),
                                  Text(
                                    _student!.fullName,
                                    textAlign: TextAlign.center,
                                    style: const TextStyle(fontSize: 18, fontWeight: FontWeight.bold),
                                  ),
                                  const SizedBox(height: 4),
                                  Text(
                                    "Student ID: ${_student!.studentId}",
                                    style: const TextStyle(
                                      fontSize: 13,
                                      fontWeight: FontWeight.w600,
                                      color: AppColors.primaryLight,
                                    ),
                                  ),
                                  const SizedBox(height: 8),
                                  StatusBadge(status: _student!.verificationStatus),
                                  if (_student!.rejectionReason != null && _student!.rejectionReason!.isNotEmpty) ...[
                                    const SizedBox(height: 12),
                                    Container(
                                      padding: const EdgeInsets.all(10),
                                      decoration: BoxDecoration(
                                        color: Colors.red.shade50,
                                        borderRadius: BorderRadius.circular(8),
                                        border: Border.all(color: Colors.red.shade200),
                                      ),
                                      child: Row(
                                        children: [
                                          Icon(Icons.info_outline, color: Colors.red.shade700, size: 18),
                                          const SizedBox(width: 8),
                                          Expanded(
                                            child: Text(
                                              "Rejection Note: ${_student!.rejectionReason!}",
                                              style: TextStyle(fontSize: 12, color: Colors.red.shade800),
                                            ),
                                          ),
                                        ],
                                      ),
                                    ),
                                  ],
                                ],
                              ),
                            ),
                          ),
                          const SizedBox(height: 16),

                          // Academic Information
                          _buildSectionCard(
                            title: "Academic Enrollment",
                            icon: Icons.school_outlined,
                            trailing: TextButton.icon(
                              onPressed: () async {
                                final updated = await Navigator.push<bool>(
                                  context,
                                  MaterialPageRoute(
                                    builder: (_) => StudentEditScreen(student: _student!),
                                  ),
                                );
                                if (updated == true) _loadDetail();
                              },
                              icon: const Icon(Icons.edit, size: 14),
                              label: const Text("Edit", style: TextStyle(fontSize: 12)),
                              style: TextButton.styleFrom(
                                visualDensity: VisualDensity.compact,
                                foregroundColor: AppColors.primary,
                              ),
                            ),
                            children: [
                              _buildDataRow("Student ID", _student!.studentId),
                              _buildDataRow("Class Level", _student!.className),
                              _buildDataRow("Section", _student!.sectionName),
                              _buildDataRow("Roll Number", "#${_student!.rollNumber}"),
                              _buildDataRow("Academic Session", _student!.academicYearName ?? "Current"),
                              _buildDataRow("Enrollment Status", _student!.status),
                            ],
                          ),
                          const SizedBox(height: 16),

                          // Personal & Guardian Information
                          _buildSectionCard(
                            title: "Personal & Guardian Data",
                            icon: Icons.person_pin_outlined,
                            trailing: TextButton.icon(
                              onPressed: () async {
                                final updated = await Navigator.push<bool>(
                                  context,
                                  MaterialPageRoute(
                                    builder: (_) => StudentEditScreen(student: _student!),
                                  ),
                                );
                                if (updated == true) _loadDetail();
                              },
                              icon: const Icon(Icons.edit, size: 14),
                              label: const Text("Edit", style: TextStyle(fontSize: 12)),
                              style: TextButton.styleFrom(
                                visualDensity: VisualDensity.compact,
                                foregroundColor: AppColors.primary,
                              ),
                            ),
                            children: [
                              _buildDataRow("Date of Birth", _student!.dateOfBirth ?? "Not specified"),
                              _buildDataRow("Gender", _student!.gender),
                              _buildDataRow("Blood Group", _student!.bloodGroup.isNotEmpty ? _student!.bloodGroup : "Not specified"),
                              _buildDataRow("Guardian Name", _student!.guardianName.isNotEmpty ? _student!.guardianName : "Not specified"),
                              _buildDataRow("Guardian Contact", _student!.guardianPhone.isNotEmpty ? _student!.guardianPhone : "Not specified"),
                              _buildDataRow("Residential Address", _student!.address.isNotEmpty ? _student!.address : "Not specified"),
                              _buildDataRow("Emergency Contact", _student!.emergencyContact.isNotEmpty ? _student!.emergencyContact : "Not specified"),
                            ],
                          ),
                          const SizedBox(height: 24),

                          // Bottom Action Buttons
                          Row(
                            children: [
                              Expanded(
                                child: OutlinedButton.icon(
                                  onPressed: () async {
                                    final updated = await Navigator.push<bool>(
                                      context,
                                      MaterialPageRoute(
                                        builder: (_) => PhotoUploadScreen(student: _student!),
                                      ),
                                    );
                                    if (updated == true) _loadDetail();
                                  },
                                  icon: const Icon(Icons.add_a_photo_outlined),
                                  label: const Text("Change Photo"),
                                  style: OutlinedButton.styleFrom(
                                    padding: const EdgeInsets.symmetric(vertical: 14),
                                    side: const BorderSide(color: AppColors.primary),
                                  ),
                                ),
                              ),
                              const SizedBox(width: 12),
                              Expanded(
                                child: ElevatedButton.icon(
                                  onPressed: _student!.isVerified || _student!.isSubmitted
                                      ? null
                                      : _submitForVerification,
                                  icon: const Icon(Icons.send_rounded),
                                  label: Text(_student!.isVerified
                                      ? "Already Verified"
                                      : _student!.isSubmitted
                                          ? "Under Review"
                                          : "Submit for Verify"),
                                  style: ElevatedButton.styleFrom(
                                    backgroundColor: AppColors.primary,
                                    foregroundColor: Colors.white,
                                    padding: const EdgeInsets.symmetric(vertical: 14),
                                  ),
                                ),
                              ),
                            ],
                          ),
                          const SizedBox(height: 16),
                        ],
                      ),
                    ),
    );
  }

  Widget _buildSectionCard({
    required String title,
    required IconData icon,
    Widget? trailing,
    required List<Widget> children,
  }) {
    return Card(
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
            Row(
              children: [
                Icon(icon, size: 18, color: AppColors.primary),
                const SizedBox(width: 8),
                Expanded(
                  child: Text(title, style: const TextStyle(fontSize: 14, fontWeight: FontWeight.bold, color: AppColors.textDark)),
                ),
                ?trailing,
              ],
            ),
            const Divider(height: 20),
            ...children,
          ],
        ),
      ),
    );
  }

  Widget _buildDataRow(String label, String value) {
    return Padding(
      padding: const EdgeInsets.symmetric(vertical: 4),
      child: Row(
        mainAxisAlignment: MainAxisAlignment.spaceBetween,
        children: [
          Text(label, style: const TextStyle(fontSize: 13, color: AppColors.textMuted)),
          Flexible(
            child: Text(
              value,
              textAlign: TextAlign.right,
              style: const TextStyle(fontSize: 13, fontWeight: FontWeight.w600, color: AppColors.textDark),
            ),
          ),
        ],
      ),
    );
  }
}

import 'package:flutter/material.dart';
import 'package:provider/provider.dart';
import '../providers/student_provider.dart';
import '../constants/app_colors.dart';
import '../widgets/status_badge.dart';
import '../widgets/error_view.dart';
import 'student_detail_screen.dart';
import 'student_add_screen.dart';

class StudentListScreen extends StatefulWidget {
  const StudentListScreen({super.key});

  @override
  State<StudentListScreen> createState() => _StudentListScreenState();
}

class _StudentListScreenState extends State<StudentListScreen> {
  final _searchController = TextEditingController();

  @override
  void initState() {
    super.initState();
    WidgetsBinding.instance.addPostFrameCallback((_) {
      Provider.of<StudentProvider>(context, listen: false).fetchStudents();
    });
  }

  @override
  void dispose() {
    _searchController.dispose();
    super.dispose();
  }

  @override
  Widget build(BuildContext context) {
    final studentProvider = Provider.of<StudentProvider>(context);

    return Scaffold(
      backgroundColor: AppColors.background,
      appBar: AppBar(
        title: const Text("Assigned Class Roster", style: TextStyle(fontWeight: FontWeight.bold, fontSize: 17)),
        backgroundColor: AppColors.primary,
        foregroundColor: Colors.white,
        elevation: 0,
      ),
      body: Column(
        children: [
          // Search & Filter Bar
          Container(
            padding: const EdgeInsets.all(12),
            color: Colors.white,
            child: Column(
              children: [
                TextField(
                  controller: _searchController,
                  decoration: InputDecoration(
                    hintText: "Search name, ID, or roll number...",
                    prefixIcon: const Icon(Icons.search, size: 20),
                    suffixIcon: _searchController.text.isNotEmpty
                        ? IconButton(
                            icon: const Icon(Icons.clear, size: 18),
                            onPressed: () {
                              _searchController.clear();
                              studentProvider.setSearchQuery('');
                            },
                          )
                        : null,
                    contentPadding: const EdgeInsets.symmetric(vertical: 0, horizontal: 12),
                    border: OutlineInputBorder(
                      borderRadius: BorderRadius.circular(8),
                      borderSide: const BorderSide(color: AppColors.border),
                    ),
                    filled: true,
                    fillColor: AppColors.background,
                  ),
                  onChanged: (val) => studentProvider.setSearchQuery(val),
                ),
                const SizedBox(height: 8),
                // Status Filter Chips
                SingleChildScrollView(
                  scrollDirection: Axis.horizontal,
                  child: Row(
                    children: [
                      _buildFilterChip("All", "", studentProvider),
                      const SizedBox(width: 6),
                      _buildFilterChip("Verified", "VERIFIED", studentProvider),
                      const SizedBox(width: 6),
                      _buildFilterChip("Submitted", "SUBMITTED", studentProvider),
                      const SizedBox(width: 6),
                      _buildFilterChip("Pending", "PENDING", studentProvider),
                      const SizedBox(width: 6),
                      _buildFilterChip("Rejected", "REJECTED", studentProvider),
                    ],
                  ),
                ),
              ],
            ),
          ),

          // Student List
          Expanded(
            child: studentProvider.isLoading
                ? const Center(child: CircularProgressIndicator())
                : studentProvider.errorMessage != null
                    ? ErrorView(
                        message: studentProvider.errorMessage!,
                        onRetry: () => studentProvider.fetchStudents(),
                      )
                    : studentProvider.students.isEmpty
                        ? Center(
                            child: Padding(
                              padding: const EdgeInsets.all(24.0),
                              child: Column(
                                mainAxisAlignment: MainAxisAlignment.center,
                                children: [
                                  Icon(Icons.person_search, size: 56, color: Colors.grey.shade400),
                                  const SizedBox(height: 12),
                                  const Text(
                                    "No students found",
                                    style: TextStyle(fontSize: 16, fontWeight: FontWeight.bold, color: AppColors.textDark),
                                  ),
                                  const SizedBox(height: 6),
                                  const Text(
                                    "Try adjusting your search criteria or filter.",
                                    style: TextStyle(fontSize: 13, color: AppColors.textMuted),
                                  ),
                                ],
                              ),
                            ),
                          )
                        : RefreshIndicator(
                            onRefresh: () => studentProvider.fetchStudents(refresh: true),
                            child: ListView.separated(
                              padding: const EdgeInsets.all(12),
                              itemCount: studentProvider.students.length,
                              separatorBuilder: (context, index) => const SizedBox(height: 8),
                              itemBuilder: (context, index) {
                                final s = studentProvider.students[index];
                                return Card(
                                  elevation: 0,
                                  color: Colors.white,
                                  shape: RoundedRectangleBorder(
                                    borderRadius: BorderRadius.circular(10),
                                    side: const BorderSide(color: AppColors.border),
                                  ),
                                  child: ListTile(
                                    contentPadding: const EdgeInsets.symmetric(horizontal: 12, vertical: 6),
                                    leading: ClipRRect(
                                      borderRadius: BorderRadius.circular(8),
                                      child: s.hasPhoto && s.photo != null
                                          ? Image.network(
                                              s.photo!,
                                              width: 44,
                                              height: 55,
                                              fit: BoxFit.cover,
                                              errorBuilder: (context, error, stackTrace) => Container(
                                                width: 44,
                                                height: 55,
                                                color: Colors.grey.shade200,
                                                child: const Icon(Icons.person, color: Colors.grey),
                                              ),
                                            )
                                          : Container(
                                              width: 44,
                                              height: 55,
                                              color: Colors.grey.shade100,
                                              child: const Icon(Icons.person_outline, color: Colors.grey),
                                            ),
                                    ),
                                    title: Text(
                                      s.fullName,
                                      style: const TextStyle(fontWeight: FontWeight.bold, fontSize: 14),
                                    ),
                                    subtitle: Column(
                                      crossAxisAlignment: CrossAxisAlignment.start,
                                      children: [
                                        const SizedBox(height: 2),
                                        Text(
                                          "ID: ${s.studentId}  |  Roll #${s.rollNumber}",
                                          style: const TextStyle(fontSize: 12, color: AppColors.textMuted),
                                        ),
                                        const SizedBox(height: 4),
                                        StatusBadge(status: s.verificationStatus),
                                      ],
                                    ),
                                    trailing: const Icon(Icons.chevron_right, color: AppColors.textMuted),
                                    onTap: () {
                                      Navigator.push(
                                        context,
                                        MaterialPageRoute(
                                          builder: (_) => StudentDetailScreen(studentId: s.id),
                                        ),
                                      );
                                    },
                                  ),
                                );
                              },
                            ),
                          ),
          ),
        ],
      ),
      floatingActionButton: FloatingActionButton.extended(
        onPressed: () async {
          final enrolled = await Navigator.push<bool>(
            context,
            MaterialPageRoute(builder: (_) => const StudentAddScreen()),
          );
          if (!context.mounted) return;
          if (enrolled == true) {
            Provider.of<StudentProvider>(context, listen: false).fetchStudents(refresh: true);
          }
        },
        backgroundColor: AppColors.primary,
        foregroundColor: Colors.white,
        icon: const Icon(Icons.person_add),
        label: const Text("Enroll Student", style: TextStyle(fontWeight: FontWeight.bold)),
      ),
    );
  }

  Widget _buildFilterChip(String label, String value, StudentProvider provider) {
    final isSelected = provider.statusFilter == value;
    return ChoiceChip(
      label: Text(label),
      labelStyle: TextStyle(
        fontSize: 11,
        fontWeight: isSelected ? FontWeight.bold : FontWeight.normal,
        color: isSelected ? Colors.white : AppColors.textDark,
      ),
      selected: isSelected,
      selectedColor: AppColors.primary,
      backgroundColor: Colors.grey.shade100,
      showCheckmark: false,
      padding: const EdgeInsets.symmetric(horizontal: 4, vertical: 0),
      onSelected: (_) => provider.setStatusFilter(value),
    );
  }
}

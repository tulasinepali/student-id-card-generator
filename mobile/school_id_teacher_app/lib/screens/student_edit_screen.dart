import 'package:flutter/material.dart';
import 'package:provider/provider.dart';
import '../models/student.dart';
import '../models/class_level.dart';
import '../providers/student_provider.dart';
import '../constants/app_colors.dart';

class StudentEditScreen extends StatefulWidget {
  final Student student;

  const StudentEditScreen({super.key, required this.student});

  @override
  State<StudentEditScreen> createState() => _StudentEditScreenState();
}

class _StudentEditScreenState extends State<StudentEditScreen> {
  final _formKey = GlobalKey<FormState>();
  late TextEditingController _studentIdController;
  late TextEditingController _rollNumberController;
  late TextEditingController _fullNameController;
  late TextEditingController _dobController;
  late TextEditingController _addressController;
  late TextEditingController _guardianNameController;
  late TextEditingController _guardianPhoneController;
  late TextEditingController _bloodGroupController;
  late TextEditingController _emergencyContactController;
  late String _gender;

  int? _selectedClassLevelId;
  int? _selectedSectionId;
  List<ClassLevelOption> _availableClasses = [];
  bool _isLoadingClasses = true;
  bool _isSaving = false;

  @override
  void initState() {
    super.initState();
    _studentIdController = TextEditingController(text: widget.student.studentId);
    _rollNumberController = TextEditingController(text: widget.student.rollNumber.toString());
    _fullNameController = TextEditingController(text: widget.student.fullName);
    _dobController = TextEditingController(text: widget.student.dateOfBirth ?? '');
    _addressController = TextEditingController(text: widget.student.address);
    _guardianNameController = TextEditingController(text: widget.student.guardianName);
    _guardianPhoneController = TextEditingController(text: widget.student.guardianPhone);
    _bloodGroupController = TextEditingController(text: widget.student.bloodGroup);
    _emergencyContactController = TextEditingController(text: widget.student.emergencyContact);
    _gender = widget.student.gender;

    _selectedClassLevelId = widget.student.classLevelId > 0 ? widget.student.classLevelId : null;
    _selectedSectionId = widget.student.sectionId > 0 ? widget.student.sectionId : null;

    WidgetsBinding.instance.addPostFrameCallback((_) {
      _loadClasses();
    });
  }

  Future<void> _loadClasses() async {
    final provider = Provider.of<StudentProvider>(context, listen: false);
    try {
      final classes = await provider.getClassesAndSections();
      if (!mounted) return;
      setState(() {
        _availableClasses = classes;
        _isLoadingClasses = false;

        // Match or initialize selected class
        if (_selectedClassLevelId != null && !_availableClasses.any((c) => c.id == _selectedClassLevelId)) {
          final matchedClass = _availableClasses.firstWhere(
            (c) => c.name.toLowerCase().trim() == widget.student.className.toLowerCase().trim(),
            orElse: () => _availableClasses.isNotEmpty
                ? _availableClasses.first
                : ClassLevelOption(id: 0, name: '', numericOrder: 0, sections: []),
          );
          if (matchedClass.id != 0) {
            _selectedClassLevelId = matchedClass.id;
          }
        } else if (_selectedClassLevelId == null && _availableClasses.isNotEmpty) {
          _selectedClassLevelId = _availableClasses.first.id;
        }

        // Match or initialize selected section within the class
        final currentClass = _availableClasses.firstWhere(
          (c) => c.id == _selectedClassLevelId,
          orElse: () => ClassLevelOption(id: 0, name: '', numericOrder: 0, sections: []),
        );

        if (_selectedSectionId != null && !currentClass.sections.any((s) => s.id == _selectedSectionId)) {
          final matchedSec = currentClass.sections.firstWhere(
            (s) => s.name.toLowerCase().trim() == widget.student.sectionName.toLowerCase().trim(),
            orElse: () => currentClass.sections.isNotEmpty
                ? currentClass.sections.first
                : SectionOption(id: 0, name: '', classLevelId: 0),
          );
          if (matchedSec.id != 0) {
            _selectedSectionId = matchedSec.id;
          } else {
            _selectedSectionId = currentClass.sections.isNotEmpty ? currentClass.sections.first.id : null;
          }
        } else if (_selectedSectionId == null && currentClass.sections.isNotEmpty) {
          _selectedSectionId = currentClass.sections.first.id;
        }
      });
    } catch (e) {
      if (!mounted) return;
      setState(() {
        _isLoadingClasses = false;
      });
    }
  }

  @override
  void dispose() {
    _studentIdController.dispose();
    _rollNumberController.dispose();
    _fullNameController.dispose();
    _dobController.dispose();
    _addressController.dispose();
    _guardianNameController.dispose();
    _guardianPhoneController.dispose();
    _bloodGroupController.dispose();
    _emergencyContactController.dispose();
    super.dispose();
  }

  Future<void> _pickDate() async {
    DateTime initial = DateTime.tryParse(_dobController.text) ?? DateTime(2010, 1, 1);
    final picked = await showDatePicker(
      context: context,
      initialDate: initial,
      firstDate: DateTime(1995),
      lastDate: DateTime.now(),
    );
    if (picked != null) {
      final y = picked.year.toString().padLeft(4, '0');
      final m = picked.month.toString().padLeft(2, '0');
      final d = picked.day.toString().padLeft(2, '0');
      setState(() {
        _dobController.text = "$y-$m-$d";
      });
    }
  }

  Future<void> _saveChanges() async {
    if (!_formKey.currentState!.validate()) return;

    final roll = int.tryParse(_rollNumberController.text.trim());
    if (roll == null || roll <= 0) {
      ScaffoldMessenger.of(context).showSnackBar(
        const SnackBar(content: Text("Please enter a valid positive roll number."), backgroundColor: Colors.red),
      );
      return;
    }

    final studentId = _studentIdController.text.trim();
    if (studentId.isEmpty) {
      ScaffoldMessenger.of(context).showSnackBar(
        const SnackBar(content: Text("Student ID cannot be empty."), backgroundColor: Colors.red),
      );
      return;
    }

    if (_selectedClassLevelId == null) {
      ScaffoldMessenger.of(context).showSnackBar(
        const SnackBar(content: Text("Please select a class."), backgroundColor: Colors.red),
      );
      return;
    }

    if (_selectedSectionId == null) {
      ScaffoldMessenger.of(context).showSnackBar(
        const SnackBar(content: Text("Please select a section."), backgroundColor: Colors.red),
      );
      return;
    }

    setState(() => _isSaving = true);
    final provider = Provider.of<StudentProvider>(context, listen: false);

    final payload = {
      'student_id': studentId,
      'class_level': _selectedClassLevelId,
      'section': _selectedSectionId,
      'roll_number': roll,
      'full_name': _fullNameController.text.trim(),
      'gender': _gender,
      'date_of_birth': _dobController.text.trim().isNotEmpty ? _dobController.text.trim() : null,
      'address': _addressController.text.trim(),
      'guardian_name': _guardianNameController.text.trim(),
      'guardian_phone': _guardianPhoneController.text.trim(),
      'blood_group': _bloodGroupController.text.trim(),
      'emergency_contact': _emergencyContactController.text.trim(),
    };

    final success = await provider.updatePermittedFields(widget.student.id, payload);

    if (!mounted) return;
    setState(() => _isSaving = false);

    if (success) {
      ScaffoldMessenger.of(context).showSnackBar(
        const SnackBar(content: Text("Student details updated successfully!"), backgroundColor: Colors.green),
      );
      Navigator.pop(context, true);
    } else {
      ScaffoldMessenger.of(context).showSnackBar(
        SnackBar(content: Text(provider.errorMessage ?? "Failed to update details."), backgroundColor: Colors.red),
      );
    }
  }

  @override
  Widget build(BuildContext context) {
    // Current sections based on selected class
    final currentClass = _availableClasses.firstWhere(
      (c) => c.id == _selectedClassLevelId,
      orElse: () => ClassLevelOption(id: 0, name: '', numericOrder: 0, sections: []),
    );
    final availableSections = currentClass.sections;

    return Scaffold(
      backgroundColor: AppColors.background,
      appBar: AppBar(
        title: const Text("Edit Student Details", style: TextStyle(fontWeight: FontWeight.bold, fontSize: 17)),
        backgroundColor: AppColors.primary,
        foregroundColor: Colors.white,
        elevation: 0,
      ),
      body: SingleChildScrollView(
        padding: const EdgeInsets.all(16),
        child: Form(
          key: _formKey,
          child: Column(
            crossAxisAlignment: CrossAxisAlignment.stretch,
            children: [
              // Academic Identification & Assignment Card (Fully Editable)
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
                      Row(
                        children: [
                          Container(
                            padding: const EdgeInsets.all(8),
                            decoration: BoxDecoration(
                              color: AppColors.primary.withValues(alpha: 0.1),
                              borderRadius: BorderRadius.circular(8),
                            ),
                            child: const Icon(Icons.school, color: AppColors.primary, size: 20),
                          ),
                          const SizedBox(width: 10),
                          const Expanded(
                            child: Column(
                              crossAxisAlignment: CrossAxisAlignment.start,
                              children: [
                                Text(
                                  "Academic Information",
                                  style: TextStyle(fontSize: 15, fontWeight: FontWeight.bold, color: AppColors.textDark),
                                ),
                                Text(
                                  "Student ID, Class, Section and Roll are editable",
                                  style: TextStyle(fontSize: 12, color: AppColors.textMuted),
                                ),
                              ],
                            ),
                          ),
                        ],
                      ),
                      const SizedBox(height: 16),

                      // Student ID (Editable)
                      TextFormField(
                        controller: _studentIdController,
                        decoration: const InputDecoration(
                          labelText: "Student ID *",
                          prefixIcon: Icon(Icons.badge_outlined),
                          border: OutlineInputBorder(),
                          helperText: "Unique institutional identifier (e.g. STU-001)",
                        ),
                        validator: (v) {
                          if (v == null || v.trim().isEmpty) return "Student ID is required";
                          return null;
                        },
                      ),
                      const SizedBox(height: 16),

                      // Class & Section Row
                      if (_isLoadingClasses)
                        const Padding(
                          padding: EdgeInsets.symmetric(vertical: 8.0),
                          child: Center(
                            child: Row(
                              mainAxisAlignment: MainAxisAlignment.center,
                              children: [
                                SizedBox(width: 16, height: 16, child: CircularProgressIndicator(strokeWidth: 2)),
                                SizedBox(width: 10),
                                Text("Loading classes and sections...", style: TextStyle(fontSize: 12, color: AppColors.textMuted)),
                              ],
                            ),
                          ),
                        )
                      else
                        Row(
                          children: [
                            // Class Dropdown
                            Expanded(
                              flex: 3,
                              child: DropdownButtonFormField<int>(
                                initialValue: _selectedClassLevelId != null && _availableClasses.any((c) => c.id == _selectedClassLevelId)
                                    ? _selectedClassLevelId
                                    : null,
                                decoration: const InputDecoration(
                                  labelText: "Class *",
                                  prefixIcon: Icon(Icons.class_outlined, size: 20),
                                  border: OutlineInputBorder(),
                                  contentPadding: EdgeInsets.symmetric(horizontal: 10, vertical: 14),
                                ),
                                items: _availableClasses.map((c) {
                                  return DropdownMenuItem<int>(
                                    value: c.id,
                                    child: Text(c.name, overflow: TextOverflow.ellipsis),
                                  );
                                }).toList(),
                                onChanged: (newClassId) {
                                  if (newClassId != null) {
                                    setState(() {
                                      _selectedClassLevelId = newClassId;
                                      final targetClass = _availableClasses.firstWhere(
                                        (c) => c.id == newClassId,
                                        orElse: () => ClassLevelOption(id: 0, name: '', numericOrder: 0, sections: []),
                                      );
                                      if (targetClass.sections.isNotEmpty) {
                                        _selectedSectionId = targetClass.sections.first.id;
                                      } else {
                                        _selectedSectionId = null;
                                      }
                                    });
                                  }
                                },
                                validator: (v) => v == null ? "Required" : null,
                              ),
                            ),
                            const SizedBox(width: 12),

                            // Section Dropdown
                            Expanded(
                              flex: 2,
                              child: DropdownButtonFormField<int>(
                                initialValue: _selectedSectionId != null && availableSections.any((s) => s.id == _selectedSectionId)
                                    ? _selectedSectionId
                                    : (availableSections.isNotEmpty ? availableSections.first.id : null),
                                decoration: const InputDecoration(
                                  labelText: "Section *",
                                  prefixIcon: Icon(Icons.meeting_room_outlined, size: 20),
                                  border: OutlineInputBorder(),
                                  contentPadding: EdgeInsets.symmetric(horizontal: 10, vertical: 14),
                                ),
                                items: availableSections.map((s) {
                                  return DropdownMenuItem<int>(
                                    value: s.id,
                                    child: Text(s.name),
                                  );
                                }).toList(),
                                onChanged: (newSecId) {
                                  if (newSecId != null) {
                                    setState(() {
                                      _selectedSectionId = newSecId;
                                    });
                                  }
                                },
                                validator: (v) => v == null ? "Required" : null,
                              ),
                            ),
                          ],
                        ),
                      const SizedBox(height: 16),

                      // Roll Number (Editable)
                      TextFormField(
                        controller: _rollNumberController,
                        decoration: const InputDecoration(
                          labelText: "Roll Number *",
                          prefixIcon: Icon(Icons.tag),
                          prefixText: "# ",
                          border: OutlineInputBorder(),
                          helperText: "Unique within this class and section",
                        ),
                        keyboardType: TextInputType.number,
                        validator: (v) {
                          if (v == null || v.trim().isEmpty) return "Roll number is required";
                          final n = int.tryParse(v.trim());
                          if (n == null || n <= 0) return "Enter a valid positive number";
                          return null;
                        },
                      ),
                    ],
                  ),
                ),
              ),
              const SizedBox(height: 16),

              // Student Personal Details Card
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
                      const Text(
                        "Personal Details",
                        style: TextStyle(fontSize: 15, fontWeight: FontWeight.bold, color: AppColors.textDark),
                      ),
                      const SizedBox(height: 16),

                      // Full Legal Name
                      TextFormField(
                        controller: _fullNameController,
                        decoration: const InputDecoration(
                          labelText: "Full Student Name *",
                          prefixIcon: Icon(Icons.person_outline),
                          border: OutlineInputBorder(),
                        ),
                        validator: (v) => v == null || v.trim().isEmpty ? "Full name required" : null,
                      ),
                      const SizedBox(height: 16),

                      // Gender Dropdown
                      DropdownButtonFormField<String>(
                        initialValue: ['MALE', 'FEMALE', 'OTHER'].contains(_gender) ? _gender : 'MALE',
                        decoration: const InputDecoration(
                          labelText: "Gender *",
                          prefixIcon: Icon(Icons.people_outline),
                          border: OutlineInputBorder(),
                        ),
                        items: const [
                          DropdownMenuItem(value: 'MALE', child: Text("Male")),
                          DropdownMenuItem(value: 'FEMALE', child: Text("Female")),
                          DropdownMenuItem(value: 'OTHER', child: Text("Other")),
                        ],
                        onChanged: (val) {
                          if (val != null) setState(() => _gender = val);
                        },
                      ),
                      const SizedBox(height: 16),

                      // Date of Birth
                      TextFormField(
                        controller: _dobController,
                        readOnly: true,
                        onTap: _pickDate,
                        decoration: InputDecoration(
                          labelText: "Date of Birth",
                          hintText: "YYYY-MM-DD",
                          border: const OutlineInputBorder(),
                          prefixIcon: const Icon(Icons.calendar_today_outlined),
                          suffixIcon: IconButton(
                            icon: const Icon(Icons.edit_calendar),
                            onPressed: _pickDate,
                          ),
                        ),
                      ),
                      const SizedBox(height: 16),

                      // Blood Group
                      TextFormField(
                        controller: _bloodGroupController,
                        decoration: const InputDecoration(
                          labelText: "Blood Group (e.g. O+, A+, B-)",
                          prefixIcon: Icon(Icons.water_drop_outlined),
                          border: OutlineInputBorder(),
                        ),
                      ),
                    ],
                  ),
                ),
              ),
              const SizedBox(height: 16),

              // Guardian & Contact Information Card
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
                      const Text(
                        "Guardian & Contact Information",
                        style: TextStyle(fontSize: 15, fontWeight: FontWeight.bold, color: AppColors.textDark),
                      ),
                      const SizedBox(height: 16),

                      TextFormField(
                        controller: _guardianNameController,
                        decoration: const InputDecoration(
                          labelText: "Guardian Full Name",
                          prefixIcon: Icon(Icons.family_restroom_outlined),
                          border: OutlineInputBorder(),
                        ),
                      ),
                      const SizedBox(height: 16),

                      TextFormField(
                        controller: _guardianPhoneController,
                        decoration: const InputDecoration(
                          labelText: "Guardian Phone Number",
                          border: OutlineInputBorder(),
                          prefixIcon: Icon(Icons.phone_outlined),
                        ),
                        keyboardType: TextInputType.phone,
                      ),
                      const SizedBox(height: 16),

                      TextFormField(
                        controller: _emergencyContactController,
                        decoration: const InputDecoration(
                          labelText: "Secondary Emergency Contact",
                          border: OutlineInputBorder(),
                          prefixIcon: Icon(Icons.contact_phone_outlined),
                        ),
                        keyboardType: TextInputType.phone,
                      ),
                      const SizedBox(height: 16),

                      TextFormField(
                        controller: _addressController,
                        decoration: const InputDecoration(
                          labelText: "Residential Address",
                          prefixIcon: Icon(Icons.home_outlined),
                          border: OutlineInputBorder(),
                        ),
                        maxLines: 2,
                      ),
                    ],
                  ),
                ),
              ),
              const SizedBox(height: 24),

              ElevatedButton(
                onPressed: _isSaving ? null : _saveChanges,
                style: ElevatedButton.styleFrom(
                  backgroundColor: AppColors.primary,
                  foregroundColor: Colors.white,
                  padding: const EdgeInsets.symmetric(vertical: 14),
                  shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(10)),
                ),
                child: _isSaving
                    ? const SizedBox(width: 20, height: 20, child: CircularProgressIndicator(color: Colors.white, strokeWidth: 2))
                    : const Text("Save Student Details", style: TextStyle(fontWeight: FontWeight.bold, fontSize: 15)),
              ),
            ],
          ),
        ),
      ),
    );
  }
}

class TeacherProfile {
  final int id;
  final String employeeId;
  final int? assignedClassId;
  final String assignedClassName;
  final int? assignedSectionId;
  final String assignedSectionName;
  final String status;
  final String? profilePhoto;

  TeacherProfile({
    required this.id,
    required this.employeeId,
    this.assignedClassId,
    required this.assignedClassName,
    this.assignedSectionId,
    required this.assignedSectionName,
    required this.status,
    this.profilePhoto,
  });

  bool get hasAssignment =>
      assignedClassId != null && assignedSectionId != null;

  String get assignmentText {
    if (hasAssignment) {
      return "$assignedClassName - Section $assignedSectionName";
    }
    return "No Class Assigned";
  }

  factory TeacherProfile.fromJson(Map<String, dynamic> json) {
    return TeacherProfile(
      id: json['id'] ?? 0,
      employeeId: json['employee_id'] ?? '',
      assignedClassId: json['assigned_class'],
      assignedClassName: json['assigned_class_name'] ?? '',
      assignedSectionId: json['assigned_section'],
      assignedSectionName: json['assigned_section_name'] ?? '',
      status: json['status'] ?? 'ACTIVE',
      profilePhoto: json['profile_photo'],
    );
  }

  Map<String, dynamic> toJson() => {
        'id': id,
        'employee_id': employeeId,
        'assigned_class': assignedClassId,
        'assigned_class_name': assignedClassName,
        'assigned_section': assignedSectionId,
        'assigned_section_name': assignedSectionName,
        'status': status,
        'profile_photo': profilePhoto,
      };
}

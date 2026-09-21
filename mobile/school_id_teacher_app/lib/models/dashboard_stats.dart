class DashboardStats {
  final bool hasAssignedClass;
  final String assignedClassName;
  final String assignedSectionName;
  final String teacherName;
  final int totalStudents;
  final int verifiedCount;
  final int submittedCount;
  final int pendingCount;
  final int rejectedCount;
  final int missingPhotosCount;

  DashboardStats({
    required this.hasAssignedClass,
    required this.assignedClassName,
    required this.assignedSectionName,
    required this.teacherName,
    required this.totalStudents,
    required this.verifiedCount,
    required this.submittedCount,
    required this.pendingCount,
    required this.rejectedCount,
    required this.missingPhotosCount,
  });

  String get assignedClassTitle {
    if (hasAssignedClass && assignedClassName.isNotEmpty) {
      return "$assignedClassName - Section $assignedSectionName";
    }
    return "No Class Assigned";
  }

  factory DashboardStats.fromJson(Map<String, dynamic> json) {
    return DashboardStats(
      hasAssignedClass: json['has_assigned_class'] ?? false,
      assignedClassName: json['assigned_class_name'] ?? '',
      assignedSectionName: json['assigned_section_name'] ?? '',
      teacherName: json['teacher_name'] ?? '',
      totalStudents: json['total_students'] ?? 0,
      verifiedCount: json['verified_count'] ?? 0,
      submittedCount: json['submitted_count'] ?? 0,
      pendingCount: json['pending_count'] ?? 0,
      rejectedCount: json['rejected_count'] ?? 0,
      missingPhotosCount: json['missing_photos_count'] ?? 0,
    );
  }
}

class QRResult {
  final String status; // ACTIVE, EXPIRED, REVOKED, INVALID
  final String statusDisplay;
  final String message;
  final String? studentId;
  final String? studentName;
  final String? className;
  final String? sectionName;
  final String? photoUrl;
  final String? schoolName;
  final String? validUntil;
  final String? cardNumber;

  QRResult({
    required this.status,
    required this.statusDisplay,
    required this.message,
    this.studentId,
    this.studentName,
    this.className,
    this.sectionName,
    this.photoUrl,
    this.schoolName,
    this.validUntil,
    this.cardNumber,
  });

  bool get isValid => status == 'ACTIVE';
  bool get isExpired => status == 'EXPIRED';
  bool get isRevoked => status == 'REVOKED';
  bool get isInvalid => status == 'INVALID';

  factory QRResult.fromJson(Map<String, dynamic> json) {
    return QRResult(
      status: json['status'] ?? 'INVALID',
      statusDisplay: json['status_display'] ?? 'INVALID ID CARD',
      message: json['message'] ?? '',
      studentId: json['student_id'],
      studentName: json['student_name'],
      className: json['class_name'],
      sectionName: json['section_name'],
      photoUrl: json['photo_url'],
      schoolName: json['school_name'],
      validUntil: json['valid_until'],
      cardNumber: json['card_number'],
    );
  }
}

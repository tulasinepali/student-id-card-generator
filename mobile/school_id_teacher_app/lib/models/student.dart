class Student {
  final int id;
  final String studentId;
  final int rollNumber;
  final String fullName;
  final String gender;
  final String? dateOfBirth;
  final int classLevelId;
  final String className;
  final int sectionId;
  final String sectionName;
  final String? academicYearName;
  final String address;
  final String guardianName;
  final String guardianPhone;
  final String bloodGroup;
  final String emergencyContact;
  final String? photo;
  final bool hasPhoto;
  final String verificationStatus; // PENDING, SUBMITTED, VERIFIED, REJECTED
  final String? rejectionReason;
  final String status; // ACTIVE, INACTIVE, etc.

  Student({
    required this.id,
    required this.studentId,
    required this.rollNumber,
    required this.fullName,
    required this.gender,
    this.dateOfBirth,
    required this.classLevelId,
    required this.className,
    required this.sectionId,
    required this.sectionName,
    this.academicYearName,
    this.address = '',
    this.guardianName = '',
    this.guardianPhone = '',
    this.bloodGroup = '',
    this.emergencyContact = '',
    this.photo,
    required this.hasPhoto,
    required this.verificationStatus,
    this.rejectionReason,
    this.status = 'ACTIVE',
  });

  bool get isVerified => verificationStatus == 'VERIFIED';
  bool get isSubmitted => verificationStatus == 'SUBMITTED';
  bool get isPending => verificationStatus == 'PENDING';
  bool get isRejected => verificationStatus == 'REJECTED';

  factory Student.fromJson(Map<String, dynamic> json) {
    return Student(
      id: json['id'] ?? 0,
      studentId: json['student_id'] ?? '',
      rollNumber: json['roll_number'] ?? 0,
      fullName: json['full_name'] ?? '',
      gender: json['gender'] ?? 'MALE',
      dateOfBirth: json['date_of_birth'],
      classLevelId: json['class_level'] ?? 0,
      className: json['class_name'] ?? '',
      sectionId: json['section'] ?? 0,
      sectionName: json['section_name'] ?? '',
      academicYearName: json['academic_year_name'],
      address: json['address'] ?? '',
      guardianName: json['guardian_name'] ?? '',
      guardianPhone: json['guardian_phone'] ?? '',
      bloodGroup: json['blood_group'] ?? '',
      emergencyContact: json['emergency_contact'] ?? '',
      photo: json['photo'],
      hasPhoto: json['has_photo'] ?? (json['photo'] != null && json['photo'] != ''),
      verificationStatus: json['verification_status'] ?? 'PENDING',
      rejectionReason: json['rejection_reason'],
      status: json['status'] ?? 'ACTIVE',
    );
  }
}

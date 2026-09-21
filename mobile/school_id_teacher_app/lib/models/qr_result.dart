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

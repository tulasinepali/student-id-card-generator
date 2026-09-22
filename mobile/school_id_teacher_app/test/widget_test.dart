import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:shared_preferences/shared_preferences.dart';
import 'package:school_id_teacher_app/main.dart';
import 'package:school_id_teacher_app/constants/app_config.dart';
import 'package:school_id_teacher_app/models/student.dart';
import 'package:school_id_teacher_app/models/user.dart';
import 'package:school_id_teacher_app/widgets/status_badge.dart';

void main() {
  setUp(() {
    SharedPreferences.setMockInitialValues({});
  });

  group('AppConfig & Placeholder Tests', () {
    test('AppConfig has expected developer placeholder values', () {
      expect(AppConfig.appName, equals('CardFlow - Teacher Portal'));
      expect(AppConfig.designerName, equals('[YOUR FULL NAME]'));
      expect(AppConfig.designerRole, equals('Designer & Developer'));
      expect(AppConfig.contactPhone, equals('[YOUR PHONE]'));
      expect(AppConfig.contactEmail, equals('[YOUR EMAIL]'));
      expect(AppConfig.website, equals('[YOUR WEBSITE]'));
      expect(AppConfig.copyrightYear, equals('2026'));
    });
  });

  group('Data Models Tests', () {
    test('Student.fromJson correctly parses student payload', () {
      final json = {
        'id': 1,
        'student_id': 'STU-001',
        'roll_number': 12,
        'full_name': 'John Doe',
        'gender': 'M',
        'blood_group': 'O+',
        'guardian_name': 'Jane Doe',
        'guardian_phone': '555-0100',
        'class_level_id': 10,
        'class_name': 'Grade 10',
        'section_id': 1,
        'section_name': 'A',
        'verification_status': 'VERIFIED',
        'status': 'ACTIVE',
        'has_photo': true,
      };

      final student = Student.fromJson(json);
      expect(student.id, equals(1));
      expect(student.studentId, equals('STU-001'));
      expect(student.fullName, equals('John Doe'));
      expect(student.rollNumber, equals(12));
      expect(student.gender, equals('M'));
      expect(student.bloodGroup, equals('O+'));
      expect(student.verificationStatus, equals('VERIFIED'));
      expect(student.status, equals('ACTIVE'));
      expect(student.hasPhoto, isTrue);
      expect(student.isVerified, isTrue);
    });

    test('User.fromJson correctly parses teacher user payload', () {
      final json = {
        'id': 5,
        'username': 'teacher1',
        'first_name': 'Sarah',
        'last_name': 'Smith',
        'email': 'sarah@example.com',
        'role': 'TEACHER',
      };

      final user = User.fromJson(json);
      expect(user.id, equals(5));
      expect(user.username, equals('teacher1'));
      expect(user.fullName, equals('Sarah Smith'));
      expect(user.role, equals('TEACHER'));
    });
  });

  group('StatusBadge Widget Tests', () {
    testWidgets('Renders verified badge', (WidgetTester tester) async {
      await tester.pumpWidget(
        const MaterialApp(
          home: Scaffold(
            body: StatusBadge(status: 'VERIFIED'),
          ),
        ),
      );
      expect(find.text('Verified'), findsOneWidget);
    });

    testWidgets('Renders pending badge', (WidgetTester tester) async {
      await tester.pumpWidget(
        const MaterialApp(
          home: Scaffold(
            body: StatusBadge(status: 'PENDING'),
          ),
        ),
      );
      expect(find.text('Pending'), findsOneWidget);
    });

    testWidgets('Renders rejected badge', (WidgetTester tester) async {
      await tester.pumpWidget(
        const MaterialApp(
          home: Scaffold(
            body: StatusBadge(status: 'REJECTED'),
          ),
        ),
      );
      expect(find.text('Rejected'), findsOneWidget);
    });

    testWidgets('Renders active validity badge', (WidgetTester tester) async {
      await tester.pumpWidget(
        const MaterialApp(
          home: Scaffold(
            body: StatusBadge(status: 'ACTIVE', isVerification: false),
          ),
        ),
      );
      expect(find.text('Active'), findsOneWidget);
    });
  });

  group('SchoolIdTeacherApp Smoke & Navigation Tests', () {
    testWidgets('Launches splash screen and renders AppConfig title', (WidgetTester tester) async {
      await tester.pumpWidget(const SchoolIdTeacherApp());

      // Initial frame renders splash screen with app name
      expect(find.text(AppConfig.appName), findsOneWidget);
      expect(find.text('Class Teacher Portal'), findsOneWidget);

      // Advance through splash delay timer and settle transition
      await tester.pump(const Duration(milliseconds: 1000));
      await tester.pumpAndSettle();

      // Successfully transitioned to login screen
      expect(find.text('Sign in with your assigned teacher credentials'), findsOneWidget);
      expect(find.text('Teacher Username'), findsOneWidget);
      expect(find.text('Password'), findsOneWidget);
    });
  });
}

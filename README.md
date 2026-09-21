# School ID Card Management System

A production-ready, enterprise-grade School ID Card Management System engineered with a **Django Web Admin Panel**, a physical millimeter-accurate **ReportLab PDF Print Engine**, a **Django REST API (JWT)**, and a companion **Flutter Mobile App** for Class Teachers.

---

## 1. System Architecture

```
                                  +---------------------------------------+
                                  |         School Administrator          |
                                  |    (Web Browser / Bootstrap 5 UI)    |
                                  +-------------------+-------------------+
                                                      |
                                                      v
                                        +----------------------------+
                                        |    Django Web Application  |
                                        |      (Admin Web Panel)     |
                                        +--------------+-------------+
                                                       |
         +---------------------------------------------+---------------------------------------------+
         |                                             |                                             |
         v                                             v                                             v
+------------------+                          +------------------+                          +------------------+
|  Excel Importer  |                          |  Physical Engine |                          |  REST API (JWT)  |
| & Bulk Photo ZIP |                          |  ReportLab / PDF |                          |  Class-Scoped    |
+------------------+                          +------------------+                          +--------+---------+
         |                                             |                                             |
         v                                             v                                             |
+------------------+                          +------------------+                                   v
| Pillow 3:4 Crop  |                          | CR80 / Duplex    |                          +------------------+
| & Normalization  |                          | Auto-Arrangement |                          |  Flutter App     |
+------------------+                          +------------------+                          | (Teacher Portal) |
         |                                             |                                    +------------------+
         +---------------------------------------------+                                             |
                                                       |                                             |
                                                       v                                             v
                                        +----------------------------+              +------------------+
                                        |    Centralized Database    |<-------------+ Roster / Photo / |
                                        | (SQLite / PostgreSQL ACID) |              |  Verify / QR     |
                                        +----------------------------+              +------------------+
```

### Key Technical Pillars:
- **Backend**: Django 5.2+, Django REST Framework, SimpleJWT, Pillow, ReportLab 4.x, openpyxl, qrcode.
- **Mobile**: Flutter 3.44+ (Dart 3.12+), Provider state management, `mobile_scanner`, `image_picker`, `http`, `shared_preferences`.
- **Physical Print Engine**: True physical millimeter precision (`54.0mm x 86.0mm`), duplex front/back horizontal alignment mirroring, external crop marks, 300 DPI rendering.
- **Rule 15 Enforcement**: Unverified students are blocked from default printing. Both verification and validity state machines are strictly decoupled.
- **Class-Scoped Security**: Teachers can strictly access and update only students enrolled in their assigned Class and Section.

---

## 2. Directory Structure

```
school_id_system/
├── .env.example                     # Environment template
├── README.md                        # Master documentation (this file)
├── backend/                         # Django Backend Project
│   ├── manage.py
│   ├── requirements.txt             # Python dependencies
│   ├── config/                      # Core Django configuration
│   │   ├── settings.py              # Environment-backed settings
│   │   ├── urls.py                  # Web Admin & API routing
│   │   ├── wsgi.py
│   │   └── asgi.py
│   ├── apps/                        # Pluggable modular applications
│   │   ├── core/                    # Audit logs, School branding, Public QR verification
│   │   ├── accounts/                # Custom User (Admin & Teacher roles)
│   │   ├── academic/                # AcademicYear, ClassLevel, Section
│   │   ├── students/                # Student profiles, Excel import/export, Bulk photo ZIP
│   │   ├── idcards/                 # IDCardTemplate, ReportLab PDF generator, PrintLayout
│   │   └── api/                     # REST API endpoints & JWT authentication for Teacher app
│   ├── media/                       # Uploaded student photos, school logos, generated PDFs
│   ├── static/                      # CSS, JS, branding assets
│   └── templates/                   # Bootstrap 5 desktop-optimized Web Admin templates
│       ├── base.html
│       ├── core/                    # Dashboard, School Settings, Audit Logs, Public QR
│       ├── accounts/                # Login, Teacher Accounts Management
│       ├── academic/                # Academic Years, Classes & Sections
│       ├── students/                # Roster, Form, Excel Import/Preview, Bulk Photos, Queue
│       └── idcards/                 # Templates, Designer, Print Center, Cards History
└── mobile/
    └── school_id_teacher_app/       # Flutter Mobile Application
        ├── pubspec.yaml             # Flutter dependencies
        ├── lib/
        │   ├── main.dart            # MultiProvider entrypoint & theme
        │   ├── constants/           # AppConfig (placeholders), ApiConstants, AppColors
        │   ├── models/              # Student, User, TeacherProfile, DashboardStats, QRResult
        │   ├── services/            # ApiClient, AuthService, StudentService, QRService
        │   ├── providers/           # AuthProvider, DashboardProvider, StudentProvider
        │   ├── widgets/             # StatusBadge, ErrorView, Custom UI elements
        │   └── screens/             # Splash, Login, Dashboard, Roster, Detail, Edit, Photo, QR, Profile, About
        └── test/
            └── widget_test.dart     # Comprehensive Flutter unit & widget tests
```

---

## 3. Quick Start & Setup Guide

### 3.1 Prerequisites
- Python 3.11, 3.12, 3.13, or 3.14
- Flutter SDK 3.24+ (Tested on Flutter 3.44.6/3.44.9)
- Git

### 3.2 Backend Setup
1. **Navigate to the backend directory**:
   ```bash
   cd school_id_system/backend
   ```

2. **Create and activate a virtual environment**:
   ```bash
   # Windows (PowerShell)
   python -m venv venv
   .\venv\Scripts\Activate.ps1

   # Linux / macOS
   python3 -m venv venv
   source venv/bin/activate
   ```

3. **Install dependencies**:
   ```bash
   pip install -r requirements.txt
   ```

4. **Environment Configuration**:
   Copy `.env.example` to `school_id_system/.env` or rely on the defaults configured in `settings.py`.
   ```bash
   cp ../.env.example ../.env
   ```

5. **Apply Database Migrations**:
   ```bash
   python manage.py migrate
   ```

6. **Seed Realistic Demo Data**:
   Populates Greenwood / Apex Academy branding, Academic Years (2025-2026), Classes (Grade 1 through 10), Sections (A & B), Teachers, 15+ Students with sample photos, default CR80 Template with dynamic field bindings, and standard Print Layouts:
   ```bash
   python manage.py seed_demo_data
   ```

7. **Run Backend Server**:
   ```bash
   python manage.py runserver 0.0.0.0:8000
   ```
   Web Admin Panel will be available at: `http://127.0.0.1:8000/`

---

### 3.3 Default Credentials

| Role | Username | Password | Assigned Scope | Access |
| :--- | :--- | :--- | :--- | :--- |
| **System Admin** | `admin` | `admin123` | Entire School / All Classes | Web Admin Panel (`http://127.0.0.1:8000/`) |
| **Class Teacher** | `teacher1` | `teacher123` | Grade 10 - Section A | Flutter App & Scoped API |
| **Class Teacher** | `teacher2` | `teacher123` | Grade 10 - Section B | Flutter App & Scoped API |

---

### 3.4 Mobile App Setup (Flutter)
1. **Navigate to the mobile app directory**:
   ```bash
   cd school_id_system/mobile/school_id_teacher_app
   ```

2. **Fetch dependencies**:
   ```bash
   flutter pub get
   ```

3. **Configure API Base URL**:
   Inspect `lib/constants/api_constants.dart`. By default:
   - Android Emulator maps to `http://10.0.2.2:8000/api`
   - iOS Simulator / Web / Desktop maps to `http://127.0.0.1:8000/api`
   - Physical device: Update `_physicalBaseUrl` to your machine's LAN IP (e.g., `http://192.168.1.50:8000/api`).

4. **Run the App**:
   ```bash
   # Run on connected device or emulator
   flutter run

   # Or run on Windows desktop for quick testing
   flutter run -d windows
   ```

---

## 4. Physical Print Engine & ReportLab Millimeter Architecture

The ReportLab print engine (`apps/idcards/services/pdf_generator.py`) produces press-ready PDF documents adhering to ISO/IEC 7810 ID-1 standard dimensions:

### 4.1 Dimensional Specifications
- **CR80 Dimensions**: `54.0 mm x 86.0 mm` (Vertical orientation) or `86.0 mm x 54.0 mm` (Horizontal).
- **Physical Coordinates**: Exact conversion using `reportlab.lib.units.mm` (`1 mm = 72 / 25.4 pt = 2.83464567 pt`).
- **Sheet Arrangement**: Automated grid placement on A4 (`210 x 297 mm`), A3, Letter, or Legal with configurable page margins, horizontal spacing, and vertical spacing.

### 4.2 Duplex Alignment & Back-Side Mirroring
When printing double-sided ID cards, front cards are laid out left-to-right:
$$\text{col} \in [0, \dots, N_{\text{cols}} - 1]$$
To ensure perfect physical alignment when flipped on the short or long edge of the sheet, the back page mirrors the columns horizontally:
$$\text{col}_{\text{back}} = (N_{\text{cols}} - 1) - \text{col}$$
This ensures Card 1's back side physically lands directly behind Card 1's front side regardless of paper thickness.

### 4.3 Crop Marks & Bleed
- Corner crop marks are rendered outside the card bounding box (`3mm` tick length, `0.5pt` stroke) to guide physical card guillotines without bleeding into the card artwork.

### 4.4 Strict Rule 15 Print Gate
- **Rule 15**: Students with `verification_status != 'VERIFIED'` or missing photos are excluded from standard print batches. The Print Center UI provides an explicit override checkbox (`include_unverified=True`) with an audit trail if administrative exception is required.

---

## 5. Excel Import & Bulk Photo Upload Engine

### 5.1 Two-Phase Excel Import (Dry Run + Atomic Commit)
- **Phase 1 (Validation)**:
  - Generates downloadable pre-formatted `.xlsx` templates containing dropdowns for Gender and Blood Group.
  - Parses uploaded spreadsheet and runs dry-run checks: duplicate `student_id` in database or spreadsheet, duplicate `roll_number` within the same class/section, non-existent Class/Section names, invalid dates.
  - Displays a clean visual preview table with flagged error rows.
- **Phase 2 (Atomic Execution)**:
  - Runs inside `django.db.transaction.atomic()`. Any database violation aborts the entire transaction to guarantee zero orphaned records.
  - Automatically records an entry in `AuditLog`.

### 5.2 Bulk Photo ZIP Matching & Pillow 3:4 Normalization
- Accepts a `.zip` archive containing student portrait images (`.jpg`, `.jpeg`, `.png`, `.webp`).
- **File Matching Convention**: Filenames are matched against `Student.student_id` (case-insensitive and punctuation-stripped, e.g. `STU001.jpg`, `stu-001.png`, `APX-2025-001.jpeg`).
- **Normalization Pipeline (`apps/students/services/photo_service.py`)**:
  1. Inspects image headers via Pillow to prevent file-extension spoofing.
  2. Applies EXIF rotation normalization (`ImageOps.exif_transpose`).
  3. Center-crops image to exact standard ID portrait ratio: **3:4 aspect ratio**.
  4. Resizes to high-resolution portrait dimensions (`600 x 800 px`) using Lanczos resampling.
  5. Saves as progressive JPEG (`quality=92`) with atomic storage update.

---

## 6. Verification & Validity State Machines

The system strictly decouples **Verification** (data accuracy workflow) from **Validity** (administrative lifecycle):

```
=== Verification State Machine ===
[PENDING] --------(Teacher submits updates)-------> [SUBMITTED]
    ^                                                    |
    |                                        +-----------+-----------+
    |                                        |                       |
(Admin Rejects with reason)                  v                       v
    +--------------------------------- [REJECTED]               [VERIFIED]
                                                                     |
                                                           Eligible for Print

=== Card Validity State Machine ===
[ACTIVE] --------(Student withdraws / lost card)-------> [REVOKED]
```

- **Verification Statuses**:
  - `PENDING`: Initial state upon enrollment or import.
  - `SUBMITTED`: Teacher updated details/photos from mobile app and submitted for review.
  - `VERIFIED`: Admin reviewed and locked data. Eligible for ID generation.
  - `REJECTED`: Admin rejected submission with mandatory feedback reason.
- **Card Validity Statuses**:
  - `ACTIVE`: Valid ID card in circulation.
  - `REVOKED`: Marked invalid by admin. Instant revocation across all QR verification endpoints.

---

## 7. QR Code Engine & Verification Flow

### 7.1 Security Model
- Each student is assigned a secure random UUID token (`verification_token`).
- The QR code does **not** encode sensitive PII (parent phone numbers or residential addresses). Instead, it encodes a secure public URL:
  `https://your-school-domain.com/verify/<uuid-token>/`

### 7.2 Public Web Verification Endpoint (`/verify/<token>/`)
- Accessible by any standard smartphone camera.
- Displays official school verification card:
  - School Name & Official Crest
  - Student Photo & Full Name
  - Student ID & Roll Number
  - Class & Section
  - Card Status (`ACTIVE` green badge or `REVOKED` red warning)
  - Verification Timestamp

### 7.3 Mobile App QR Scanner (`/api/verify-qr/<token>/`)
- Built-in live camera scanner in the Teacher mobile app using `mobile_scanner`.
- Connects to the authenticated REST API endpoint to log verification scans in `VerificationRecord` with scanner IP and device metadata.

---

## 8. Teacher Mobile Application (Flutter)

### 8.1 Strict Server-Side Scoping
- A logged-in teacher is restricted strictly to students enrolled in their assigned Class and Section.
- Attempting to query another student ID returns an HTTP 403 Forbidden.

### 8.2 Permitted Field Editing
Teachers can update non-critical and operational details:
- Student Roll Number
- Blood Group
- Guardian Name & Phone Number
- Emergency Contact
- Residential Address
- Student Photo (Direct camera capture or gallery selection with preview)

*Critical fields such as Student ID, First Name, Last Name, Class, and Section are restricted to Web Admin control.*

### 8.3 Centralized Config & Placeholders
As specified in **Requirements 38 & 66**, developer and designer contact placeholders in the About screen are strictly centralized in `lib/constants/app_config.dart` and `.env.example`:
```dart
class AppConfig {
  static const String appName = "Apex ID - Teacher Portal";
  static const String appVersion = "1.0.0";
  static const String designerName = "[YOUR FULL NAME]";
  static const String designerRole = "Designer & Developer";
  static const String contactPhone = "[YOUR PHONE]";
  static const String contactEmail = "[YOUR EMAIL]";
  static const String website = "[YOUR WEBSITE]";
  static const String copyrightYear = "2026";
}
```

---

## 9. Automated Testing & Verification

### 9.1 Backend Test Suite (Django)
Run 12 comprehensive unit and integration tests covering:
- REST API JWT authentication & scoped student retrieval
- Teacher permitted field updates & unauthorized rejection
- Excel template generator & dry-run validator
- ReportLab physical PDF generation & Rule 15 print gating
- QR token verification & revocation logic

```bash
cd school_id_system/backend
python manage.py test apps
```
**Result**: `Ran 16 tests ... OK (100% Passing)`

### 9.2 Mobile App Test Suite (Flutter)
Run Flutter static analysis and widget/unit tests:
```bash
cd school_id_system/mobile/school_id_teacher_app
flutter analyze
flutter test
```
**Result**:
- `flutter analyze`: `No issues found! (ran in 2.6s)`
- `flutter test`: `All 8 tests passed!`

---

## 10. Production Deployment Manual

A dedicated, comprehensive **Operations & Deployment Guide** is available at [`DEPLOYMENT.md`](DEPLOYMENT.md) detailing:
- Ubuntu Server package setup (PostgreSQL 15+, Python 3, Nginx, Certbot).
- PostgreSQL role, database, and connection pooling configuration.
- Gunicorn systemd daemon service configuration.
- Nginx reverse proxy with SSL termination and Let's Encrypt automated certificate renewals.
- Android production release builds (Keystore, signed `.apk` and `.aab`).
- Windows Desktop release builds (`flutter build windows --release`).
- Automated daily backup scripts (PostgreSQL dumps + student photos archive) and disaster recovery.

---

## 11. License
This system is developed as an enterprise educational management solution. Built for production reliability, strict role-based data integrity, and high-precision physical printing.

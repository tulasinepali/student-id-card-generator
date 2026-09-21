# School ID Card Management System — Master System Documentation

---

## 1. Executive System Overview

The **School ID Card Management System** is a complete, enterprise-grade institutional platform engineered to handle the full lifecycle of student identification:
1. **Academic Enrollment & Data Ingestion**: Individual student data entry, high-speed multi-column Excel spreadsheet import, and automated ZIP photo matching.
2. **Teacher Field Operations**: A Flutter cross-platform mobile application allowing assigned class teachers to verify student profiles, take camera photos, edit academic information, and submit records for administrative review.
3. **Institutional Verification Security**: Decoupled verification and validity state machines ensuring unverified or unapproved students are never printed accidentally (Rule 15 Enforcement).
4. **Visual Drag-and-Drop Template Designer**: Interactive visual card design canvas supporting orientation toggles, background image uploads, dynamic student placeholders, barcode/QR generators, and signature placement.
5. **Physical Print & Export Engine**: Millimeter-accurate vector PDF print engine (ReportLab & PyMuPDF) supporting standard CR80 ID card specs ($54.0 \times 86.0\text{ mm}$), paper grid calculation (A4, A3, Letter, Legal), duplex mirroring, crop marks, **Single-Sided vs. Double-Sided printing switch**, and high-resolution $300\text{ DPI}$ PNG/JPEG image exports.
6. **Public QR Code Validation**: Cryptographically secure QR verification URL embedded on each physical card, allowing parents, law enforcement, or exam invigilators to scan and view real-time card validity.

---

## 2. Page & Screen Inventory Summary

The system comprises **34 distinct functional pages and screens**:
- **22 Web Admin Pages** (Desktop browser interface built with Django 5.2 and Bootstrap 5)
- **12 Mobile App Screens** (Mobile application built with Flutter 3.44+ / Dart 3.12+)

| Category | Page Count | Primary Technology | User Role |
| :--- | :---: | :--- | :--- |
| **Administrative Web Pages** | **22** | Django 5.2, Bootstrap 5, Vanilla JS | School Administrator / Principal |
| **Mobile Teacher App Screens** | **12** | Flutter 3.44+, Provider State, Dart | Class Teacher / Mobile Staff |
| **Total Functional Pages** | **34** | Full-Stack Hybrid Architecture | Admin, Teachers, Public Invigilators |

---

## 3. Web Admin Portal Pages (22 Pages)

### Core Administration & Analytics

#### Page 1: Executive Dashboard
- **File**: `backend/templates/core/dashboard.html`
- **URL**: `/` (Name: `dashboard`)
- **Role**: School Administrator
- **Purpose**: Real-time high-level oversight of school enrollment, card generation progress, and system health.
- **UI Elements**:
  - Summary KPI cards: Total Students, Verified Students, Pending Approvals, Cards Generated, Active Templates.
  - Verification Funnel progress bar (Verified vs. Pending vs. Missing Photo vs. Rejected).
  - Quick-action shortcuts: "Import Excel", "Upload Photos", "Print Center", "Create Student".
  - Recent activity feed showing recent logins, edits, and card generation events.
- **How It Works**:
  Aggregates counts across `Student`, `IDCard`, `AcademicYear`, and `AuditLog` models in single optimized queries. If no academic year is active, displays an alert prompting setup.

#### Page 2: School Settings & Institutional Branding
- **File**: `backend/templates/core/school_settings.html`
- **URL**: `/school-settings/` (Name: `school_settings`)
- **Role**: School Administrator
- **Purpose**: Configure institution-wide branding, contact info, and legal signatures embedded on all printed ID cards.
- **UI Elements**:
  - School Details: Name, Affiliation Number, Established Year, Motto.
  - Contact Details: Official Address, Phone Number, Email, Official Website.
  - Institutional Assets: School Crest/Logo upload (with live preview) and Headmaster/Principal Signature upload.
- **How It Works**:
  Maintains a Singleton `School` database model instance. Uploaded logo and signature images are validated for size and stored in `media/school/`. These assets are dynamically drawn onto ID cards during PDF rendering.

#### Page 3: System Audit & Activity Logs
- **File**: `backend/templates/core/audit_logs.html`
- **URL**: `/audit-logs/` (Name: `audit_logs`)
- **Role**: School Administrator
- **Purpose**: Permanent, tamper-evident security audit trail tracking every action performed in the system.
- **UI Elements**:
  - Search and filter bar: filter by Action Type, User, Date Range, or Object Type.
  - Tabular log listing: Timestamp, Actor, IP Address, Action Type (`STUDENT_EDITED`, `VERIFIED`, `PDF_PRINTED`, etc.), and JSON details modal.
  - Pagination controls (50 logs per page).
- **How It Works**:
  Every mutation in views and services invokes `apps.core.services.audit_logger.log_action()`. The view queries `AuditLog` records with `select_related('user')` for instant chronological inspection.

#### Page 4: Public QR Code Verification Portal
- **File**: `backend/templates/core/public_verify.html`
- **URL**: `/verify/<token>/` (Name: `public_qr_verify`)
- **Role**: Public (Any user scanning an ID card QR code)
- **Purpose**: Verifies card authenticity in real-time when scanned by a smartphone camera.
- **UI Elements**:
  - Green / Red validity banner ("OFFICIALLY VERIFIED ACTIVE CARD" vs "CARD EXPIRED / REVOKED").
  - Official student identity badge: Student Photo, Full Name, Student ID, Class, Section, Roll Number.
  - School authorization stamp, validity period (`Valid From` - `Valid Until`), and unique Card Serial Number.
- **How It Works**:
  The URL is encoded in the QR code drawn on every card. When scanned, it looks up the unique `verification_token` in `IDCard`. If the card has been revoked or expired, a prominent red warning is displayed to prevent fraud.

---

### Academic Structure & Staff Accounts

#### Page 5: Academic Years & Sessions Management
- **File**: `backend/templates/academic/academic_years.html`
- **URL**: `/academic-years/` (Name: `academic_years`)
- **Role**: School Administrator
- **Purpose**: Create and manage academic calendars (e.g. `2026/27` or `2083`), defining valid date spans for all ID cards.
- **UI Elements**:
  - Active session indicator card.
  - Form to add new session: Year Name, Start Date, End Date, "Set as Active Session" checkbox.
  - Table of all historical sessions with action buttons to activate or edit dates.
- **How It Works**:
  Activating a session automatically marks older sessions as `is_active=False`. All new student enrollments and card expiration calculations default to the currently active session.

#### Page 6: Classes & Sections Configuration
- **File**: `backend/templates/academic/classes_sections.html`
- **URL**: `/classes-sections/` (Name: `classes_sections`)
- **Role**: School Administrator
- **Purpose**: Define the grade levels (e.g., Nursery, Grade 1 to 12) and their constituent sections (A, B, C).
- **UI Elements**:
  - Class Level list with numeric ordering drag/inputs.
  - Inline section creator for each class.
  - Student count badge per section.
  - Class Teacher assignment tag showing who manages each section.
- **How It Works**:
  Maintains parent-child `ClassLevel` $\rightarrow$ `Section` relational models. Sections cannot be deleted if active students are assigned to them.

#### Page 7: Teacher Accounts & Class Assignments
- **File**: `backend/templates/accounts/teachers_list.html`
- **URL**: `/teachers/` (Name: `teachers_list`)
- **Role**: School Administrator
- **Purpose**: Manage mobile login credentials and class access scopes for teaching staff.
- **UI Elements**:
  - Create Teacher Modal: Full Name, Username, Email, Password, Assigned Class, Assigned Section.
  - Teacher roster table: Avatar, Name, Email, Assigned Class & Section, Last Login timestamp, Status toggle.
  - Password Reset button and Assignment Editor modal.
- **How It Works**:
  Creates users with `role='TEACHER'`. When teachers log into the mobile app, the backend restricts their access strictly to students enrolled in their assigned `ClassLevel` and `Section`.

#### Page 8: Admin Authentication Login
- **File**: `backend/templates/accounts/login.html`
- **URL**: `/login/` (Name: `admin_login`)
- **Role**: School Administrator
- **Purpose**: Secure administrative entry point with credential verification and session management.
- **UI Elements**: Clean centered card with School Logo, Username input, Password input with toggle, and CSRF protection.

---

### Student Roster & Verification Lifecycle

#### Page 9: Student Master Directory
- **File**: `backend/templates/students/students_list.html`
- **URL**: `/students/` (Name: `students_list`)
- **Role**: School Administrator
- **Purpose**: Central hub for viewing, filtering, batch-printing, and managing all enrolled students.
- **UI Elements**:
  - **Comprehensive Filter Toolbar**: Search query (Name, ID, Roll), Academic Session filter, Class filter, Section filter, Verification Status dropdown, and Missing Photo filter.
  - **Top Action Bar**:
    - **"Print / Export Entire Class Cards"** button (opens Class Print modal).
    - **"Print / Export Selected Cards (X)"** button with live counter (opens Bulk Print modal).
    - "Excel Import", "Bulk Photos", and "Add Student" buttons.
  - **Student Roster Table**:
    - Master checkbox & individual selection checkboxes.
    - Photo thumbnail (with fallback avatar).
    - Student ID (`STU8001`), Full Name, Roll Number, Class & Section.
    - Verification Status pill (`VERIFIED`, `PENDING`, `REJECTED`, `SUBMITTED`).
    - Actions dropdown: View Profile, Edit, Delete, and **Direct 1-Click Print/Export Button** (Printer icon).
  - **Modals Embedded**:
    - `#printClassModal`: Batch class printing with Single-Sided/Double-Sided switch, layout picker, and format selector (PDF, PNG, JPEG).
    - `#bulkPrintModal`: Multi-student printing for checked rows.
    - `#singlePrintModal`: Single card export modal without navigating away from the table.
- **How It Works**:
  Processes GET filters with Django pagination ($25\text{ students/page}$). POST requests handle bulk actions (`print`, `print_class`, `print_single`, `delete_selected`, `mark_verified`).

#### Page 10: Student Profile & History
- **File**: `backend/templates/students/student_detail.html`
- **URL**: `/students/<id>/` (Name: `student_detail`)
- **Role**: School Administrator
- **Purpose**: In-depth individual student identity dossier, card history, and verification audit trail.
- **UI Elements**:
  - Left column: Large high-res student photo, student ID badge, status tags, contact details, emergency phone, and blood group.
  - Academic metadata card: Session, Class, Section, Roll Number, Date of Birth.
  - Card Generation History table: Lists every physical card ever printed for this student with Card Number, Date, Status (`ACTIVE`, `REVOKED`), and Revoke action.
  - Verification Timeline: Chronological audit trail showing who submitted and who verified the student.
  - Direct Action buttons: "Edit Student", "Delete Student", and **"Print / Export ID Card"** (opens Single Card Modal with Single-Sided/Double-Sided switch).
- **How It Works**:
  Fetches student with `select_related` on class, section, session, and `prefetch_related` on `id_cards`. Handles POST `action='print_card'` to download single-card PDF or $300\text{ DPI}$ image.

#### Page 11: Student Enrollment & Edit Form
- **File**: `backend/templates/students/student_form.html`
- **URL**: `/students/new/` and `/students/<id>/edit/` (Names: `student_create`, `student_edit`)
- **Role**: School Administrator
- **Purpose**: Create a new student profile or edit existing information with live photo cropping.
- **UI Elements**:
  - Personal Information: Full Name, Date of Birth, Gender, Blood Group.
  - Academic Assignment: Student ID (auto-generated or manual), Academic Session, Class Level, Section, Roll Number.
  - Guardian / Emergency Contact: Parent/Guardian Name, Phone Number, Residential Address.
  - Photo Uploader: File input with live client-side image preview and automatic $3:4$ aspect ratio cropping guidance.
- **How It Works**:
  Validates uniqueness of `(class_level, section, roll_number, academic_year)` and `student_id`. On save, image is processed by Pillow to ensure maximum dimensions and proper portrait orientation.

#### Page 12: Student Deletion Confirmation
- **File**: `backend/templates/students/student_confirm_delete.html`
- **URL**: `/students/<id>/delete/` (Name: `student_delete`)
- **Role**: School Administrator
- **Purpose**: Safe confirmation barrier before permanently deleting student records.
- **UI Elements**: Warning card showing student name, ID, class, and cards linked, with "Confirm Delete" and "Cancel" buttons.

#### Page 13: Student Verification Queue & Bulk Approvals
- **File**: `backend/templates/students/verification_queue.html`
- **URL**: `/verification-queue/` (Name: `verification_queue`)
- **Role**: School Administrator
- **Purpose**: Specialized workflow for reviewing student data submitted from the mobile app by class teachers.
- **UI Elements**:
  - Pending approval count badge.
  - Split comparison view: Teacher submitted photo, cropped view, student details, and submission notes.
  - Actions per card: **"Approve & Verify"** (green button), **"Reject & Request Revision"** (red button with notes modal).
  - Bulk Action bar: "Approve All Verified on Page".
- **How It Works**:
  Queries students with `verification_status='SUBMITTED'`. Approving changes status to `VERIFIED` and sets `is_print_eligible=True`. Rejecting sets status to `REJECTED` and notifies the class teacher via their mobile app.

---

### Bulk Ingestion Engines

#### Page 14: Excel Student Importer & Column Mapper
- **File**: `backend/templates/students/excel_import.html`
- **URL**: `/excel-import/` (Name: `excel_import`)
- **Role**: School Administrator
- **Purpose**: High-speed bulk onboarding from any `.xlsx` spreadsheet with intelligent column matching.
- **UI Elements**:
  - File upload drop-zone supporting drag-and-drop.
  - "Download Sample Excel Template" link (`/excel-template/`).
  - Target Academic Session selector.
  - "Auto-detect Columns" checkbox.
- **How It Works**:
  Accepts Excel files up to $20\text{ MB}$. Parses headers using `openpyxl` and maps headers like `Name`, `Roll`, `Class`, `Section`, `DOB`, `Blood Group` into internal model fields.

#### Page 15: Excel Import Preview & Validation Grid
- **File**: `backend/templates/students/excel_preview.html`
- **URL**: `/excel-import/` (POST Step 2)
- **Role**: School Administrator
- **Purpose**: Interactive pre-import verification grid showing valid rows, detected warnings, and duplicate conflict resolution.
- **UI Elements**:
  - Validation statistics banner: Total Rows, Valid Rows, Rows with Warnings, Invalid Rows.
  - Column re-mapping dropdowns if headers were unrecognized.
  - Duplicate Handling toggle: "Skip duplicates", "Overwrite existing records", or "Create with new ID".
  - "Proceed with Import" button.
- **How It Works**:
  Validates every row in memory before touching the database. Displays exact row-by-row error messages (e.g. invalid date format in row 14). On confirmation, executes bulk database creation inside a database transaction.

#### Page 16: Bulk Student Photo ZIP Importer
- **File**: `backend/templates/students/bulk_photos.html`
- **URL**: `/bulk-photos/` (Name: `bulk_photos`)
- **Role**: School Administrator
- **Purpose**: Batch attach student portrait photos from a single `.zip` archive.
- **UI Elements**:
  - ZIP file upload zone.
  - Target Class & Section scope selectors.
  - Filename Matching Mode selector:
    - Match by Student ID (e.g., `STU8001.jpg`)
    - Match by Roll Number (e.g., `01.jpg`, `Roll_1.png`)
    - Match by Full Name (e.g., `Aarav_Sharma.jpg`)
- **How It Works**:
  Uploads ZIP archive, extracts images in-memory, normalizes EXIF orientation, applies Pillow $3:4$ portrait crop, and links images to corresponding student records.

#### Page 17: Bulk Photo Processing Results & Matching Report
- **File**: `backend/templates/students/bulk_photos_result.html`
- **URL**: `/bulk-photos/` (POST Result)
- **Role**: School Administrator
- **Purpose**: Detailed visual match report showing which photos succeeded and which files were unmatched.
- **UI Elements**:
  - Matched count vs. Unmatched count cards.
  - Visual grid of matched students with their newly attached photos.
  - List of unmatched filenames with explanations (e.g., `99.jpg` did not match any student roll number in Grade 8).

---

### Card Templates, Designer & Physical Printing

#### Page 18: ID Card Templates Gallery
- **File**: `backend/templates/idcards/templates_list.html`
- **URL**: `/templates/` (Name: `templates_list`)
- **Role**: School Administrator
- **Purpose**: Manage, duplicate, preview, and create card layout templates.
- **UI Elements**:
  - Template cards gallery with visual thumbnails.
  - Details per template: Dimensions ($54 \times 86\text{ mm}$), Orientation (Portrait / Landscape), Duplex Mode (Single / Double sided), Version number.
  - Action buttons: "Open in Designer", "Duplicate", "Create New Version", "Set as School Default".
  - "Create New Template" button with orientation and size presets (CR80 Standard, ID-1).
- **How It Works**:
  Manages `IDCardTemplate` model records. Duplicating clones all connected elements (`TemplateElement`) into a new template version with zero disruption to existing cards.

#### Page 19: Interactive Drag-and-Drop Template Designer
- **File**: `backend/templates/idcards/template_designer.html`
- **URL**: `/templates/<id>/designer/` (Name: `template_designer`)
- **Role**: School Administrator
- **Purpose**: Visual WYSIWYG card design workspace with millimeter-accurate canvas positioning.
- **UI Elements**:
  - **Card Side Switcher**: Toggle between "Front Side" and "Back Side" design canvases.
  - **Interactive Canvas**: Real-time rendering canvas reflecting exact physical millimeter dimensions, grid snap, and millimeter ruler guides.
  - **Toolbox Palette**:
    - Add Dynamic Student Fields: Full Name, Student ID, Class, Section, Roll Number, Date of Birth, Blood Group, Emergency Contact.
    - Add School Elements: School Crest/Logo, School Name, Address, Affiliation Code.
    - Add Legal Elements: Principal Signature placeholder, Expiration Date.
    - Add Security Elements: Barcode (Code128), Public Verification QR Code.
    - Add Static Elements: Custom text labels, headers, lines, rectangles.
  - **Properties Sidebar**: Font Family, Font Size ($pt$), Font Weight, Text Alignment, Color Picker, Element X/Y coordinates ($mm$), Width/Height ($mm$).
  - **Background Manager**: Upload custom high-resolution background artwork for Front and Back sides with Fit/Crop/Fill options and DPI quality inspection.
  - **Live Preview with Real Students**: Select any actual student to preview live dynamic card rendering.
- **How It Works**:
  Saves layout via AJAX POST to `/templates/<id>/designer/` as JSON. Positions are stored in millimeter units (`x_mm`, `y_mm`, `width_mm`, `height_mm`) for identical fidelity across web canvas and ReportLab vector PDF output.

#### Page 20: Print & PDF Export Center
- **File**: `backend/templates/idcards/print_center.html`
- **URL**: `/print-center/` (Name: `print_center`)
- **Role**: School Administrator
- **Purpose**: Centralized industrial printing and high-resolution export workstation.
- **UI Elements**:
  - **Scope Filter**: Class selector, Section selector, Academic Session selector.
  - **Template Selection Carousel**: Visual cards allowing 1-click selection of active card designs.
  - **Eligibility Audit Bar**: Print-eligible count (Verified + Photo), Pending count, Rejected count, and Missing Photo count.
  - **Export Settings Panel**:
    - **Output Format**:
      - 🔘 **PDF Document** (Print Sheet Grid)
      - 🔘 **PNG Images** ($300\text{ DPI}$ ZIP Archive)
      - 🔘 **JPEG Images** ($300\text{ DPI}$ ZIP Archive)
    - **Sides to Print / Export Switch**:
      - 🔘 **Single Sided (Front Only)**: Produces only front pages. No back pages generated.
      - 🔘 **Double Sided (Both Front & Back)**: Produces duplex-aligned back pages.
    - **Print Scope Switch**:
      - 🔘 Print All Students in Scope
      - 🔘 Only Selected Students
    - **Unverified Override Checkbox**: Allows administrative override to print unverified students if needed.
  - **Live Student Selection Roster Table**:
    - Master checkbox & individual student check selection.
    - Photo preview, roll, name, section, and verification badge.
- **How It Works**:
  Invokes `apps.idcards.services.pdf_generator.export_id_cards_batch()`. Applies auto-grid calculation so cards never overflow physical paper bounds, renders vector PDF or $300\text{ DPI}$ rasterized images via PyMuPDF, and updates card print timestamps in the audit database.

#### Page 21: ID Cards Audit & Print History
- **File**: `backend/templates/idcards/cards_history.html`
- **URL**: `/cards-history/` (Name: `cards_history`)
- **Role**: School Administrator
- **Purpose**: Complete audit log of every physical ID card issued by the institution.
- **UI Elements**:
  - Filters: Search Card Number, Filter by Class, Academic Session, or Card Status (`GENERATED`, `PRINTED`, `REVOKED`).
  - Cards Table: Card Number (`ID-2026-STU8001`), Student Name, Class, Template Used, Generated Date, Printed Date, Validity Status (`ACTIVE`, `REVOKED`), and Revoke button.
- **How It Works**:
  Queries `IDCard` model records. Tracks who printed each card and when. Provides legal traceability if a student loses a card or leaves the school.

#### Page 22: Card Revocation Confirmation
- **File**: `backend/templates/idcards/revoke_card_confirm.html`
- **URL**: `/cards/<id>/revoke/` (Name: `revoke_card`)
- **Role**: School Administrator
- **Purpose**: Security modal to formally invalidate and revoke a lost, damaged, or compromised ID card.
- **UI Elements**: Student details, Card Number, Reason for Revocation text input, and "Revoke Card Permanently" confirmation button.
- **How It Works**:
  Updates `validity_status='REVOKED'`. The card's public QR code will immediately return a red "REVOKED / INVALID" warning if scanned anywhere in the world.

---

## 4. Mobile Teacher Application Screens (12 Screens)

Built with Flutter 3 for Android and iOS smartphones, providing class teachers with portable tools to manage student verification in their classrooms.

```
mobile/school_id_teacher_app/lib/screens/
├── splash_screen.dart             # App launch, token check & branding
├── login_screen.dart              # Secure JWT login for teachers
├── dashboard_screen.dart          # Class overview & verification statistics
├── student_list_screen.dart       # Assigned class roster with search & filters
├── student_detail_screen.dart     # Student identity dossier & verification actions
├── student_edit_screen.dart       # Edit student data (Roll, Class, Contact, etc.)
├── student_add_screen.dart        # Quick student enrollment form
├── photo_upload_screen.dart       # Live camera photo capture & crop
├── qr_scanner_screen.dart         # Camera QR barcode scanner
├── qr_result_screen.dart          # Instant QR verification result badge
├── profile_screen.dart            # Teacher account info & password change
└── about_screen.dart              # Institutional software info & guidelines
```

#### Screen 1: Splash Gateway
- **File**: `mobile/.../screens/splash_screen.dart`
- **Purpose**: Initializes app state, checks stored JWT credentials, and auto-routes to Dashboard or Login.

#### Screen 2: Teacher Login Screen
- **File**: `mobile/.../screens/login_screen.dart`
- **Purpose**: Clean, professional login screen for class teachers.
- **Features**: Username and password authentication against Django REST API (`/api/auth/login/`), storing encrypted JWT tokens in `SharedPreferences`.

#### Screen 3: Teacher Class Dashboard
- **File**: `mobile/.../screens/dashboard_screen.dart`
- **Purpose**: Main hub for the teacher showing their assigned Class & Section.
- **Features**:
  - Class Name Banner (e.g., "Grade 8 - Section A").
  - Statistics Grid: Total Enrolled, Verified Count, Pending Count, Photos Attached Count.
  - Quick Buttons: "Class Roster", "Enroll New Student", "Scan Student Card".

#### Screen 4: Class Student Roster
- **File**: `mobile/.../screens/student_list_screen.dart`
- **Purpose**: Fast, searchable student list strictly scoped to the teacher's assigned class.
- **Features**: Live search bar, pull-to-refresh, status filter pills (All, Verified, Pending, Missing Photo), and student card tiles with thumbnail and verification badges.

#### Screen 5: Student Profile & Verification Action
- **File**: `mobile/.../screens/student_detail_screen.dart`
- **Purpose**: Full student profile inspection screen.
- **Features**: High-resolution photo preview, complete demographic details, guardian phone call shortcut, and **"Submit for Admin Approval"** button.

#### Screen 6: Student Data Editor
- **File**: `mobile/.../screens/student_edit_screen.dart`
- **Purpose**: Allows teachers to update student details directly from mobile.
- **Features**: Unlocked editable fields: Student ID, Roll Number, Class Level, Section, Full Name, DOB, Blood Group, Guardian details, and Phone Number.

#### Screen 7: Student Quick Enrollment
- **File**: `mobile/.../screens/student_add_screen.dart`
- **Purpose**: Enroll a newly admitted student directly from the classroom.
- **Features**: Form validating roll number and student ID, saving directly to the server via `/api/teacher/students/create/`.

#### Screen 8: Camera Photo Capture & Crop
- **File**: `mobile/.../screens/photo_upload_screen.dart`
- **Purpose**: Take official student ID photos using the smartphone camera.
- **Features**: Native camera capture, gallery selection, portrait overlay guide, client-side compression, and upload to `/api/teacher/students/<id>/photo/`.

#### Screen 9: Live QR Barcode Camera Scanner
- **File**: `mobile/.../screens/qr_scanner_screen.dart`
- **Purpose**: Scans physical student ID cards using the mobile camera.
- **Features**: Live camera view with square target reticle, flashlight toggle, and instant QR code detection via `mobile_scanner`.

#### Screen 10: QR Verification Result Screen
- **File**: `mobile/.../screens/qr_result_screen.dart`
- **Purpose**: Displays instant validity badge after scanning a card.
- **Features**: Displays student photo, name, class, roll number, and green "ACTIVE CARD" or red "REVOKED / EXPIRED" alert.

#### Screen 11: Teacher Profile & Security
- **File**: `mobile/.../screens/profile_screen.dart`
- **Purpose**: Teacher account overview and security settings.
- **Features**: Assigned class & section details, username, email, and in-app password update dialog.

#### Screen 12: System About & Guidelines
- **File**: `mobile/.../screens/about_screen.dart`
- **Purpose**: Institution and version metadata.
- **Features**: App version, school contact, photo composition guidelines, and developer credits.

---

## 5. Core Operational Engines & Rules

### 1. Millimeter-Accurate Physical Print Engine
- **Files**: `apps/idcards/services/pdf_generator.py`
- **Capabilities**:
  - True physical millimeter layout ($54.0 \times 86.0\text{ mm}$ standard CR80 ID format).
  - Multi-card auto-grid calculation based on paper dimensions ($A4$, $A3$, Letter, Legal).
  - Capped rows and columns preventing portrait cards from overflowing below printable sheet bounds.
  - **Single-Sided vs. Double-Sided Printing Switch**:
    - `FRONT_ONLY`: Generates only the front side of ID cards. Back pages are completely suppressed.
    - `BOTH`: Generates both front cards and duplex-aligned mirrored back cards.
  - High-Resolution $300\text{ DPI}$ image rasterization via PyMuPDF into individual or combined PNG and JPEG files, or multi-student ZIP archives.

### 2. Rule 15: Verification & Printing Decoupling
- **Decoupled States**:
  - `verification_status`: `PENDING` $\rightarrow$ `SUBMITTED` $\rightarrow$ `VERIFIED` (or `REJECTED`).
  - `card_status`: `DRAFT` $\rightarrow$ `GENERATED` $\rightarrow$ `PRINTED`.
  - `validity_status`: `ACTIVE` vs. `REVOKED`.
- **Enforcement**:
  By default, students who are not `is_print_eligible` (must be `Active`, `Verified`, and have an attached photo) cannot be printed. Administrators have a clear, audited override option in the Print Center.

### 3. Bulk Data Processing
- **Excel Importer**: Uses `openpyxl` with dynamic column mapping and preview validation grid to import hundreds of students in seconds.
- **Bulk Photo ZIP**: Unpacks ZIP archives and uses regular expression matching to link photos to students by Student ID, Roll Number, or Name.

---

## 6. REST API Architecture (Backend to Mobile)

| Endpoint | Method | Role | Description |
| :--- | :---: | :---: | :--- |
| `/api/auth/login/` | `POST` | Public | Teacher JWT credential login |
| `/api/auth/refresh/` | `POST` | Public | JWT Token refresh |
| `/api/teacher/profile/` | `GET` | Teacher | Get logged-in teacher profile and assigned class |
| `/api/teacher/change-password/`| `POST` | Teacher | Change teacher account password |
| `/api/academic/classes-sections/`| `GET` | Teacher | List of all available classes and sections |
| `/api/teacher/dashboard/` | `GET` | Teacher | Live class statistics (enrolled, verified, pending) |
| `/api/teacher/students/` | `GET` | Teacher | Class-scoped student roster with search & filters |
| `/api/teacher/students/create/`| `POST` | Teacher | Enroll a new student into assigned class |
| `/api/teacher/students/<id>/` | `GET` | Teacher | Student detail profile |
| `/api/teacher/students/<id>/update/`| `PUT` | Teacher | Update student fields (ID, Roll, Class, Contacts) |
| `/api/teacher/students/<id>/photo/`| `POST` | Teacher | Upload student portrait photo from camera/gallery |
| `/api/teacher/students/<id>/submit-verification/`| `POST` | Teacher | Submit student to admin queue for verification |
| `/api/verify-qr/<token>/` | `GET` | Public | Validate scanned ID card token and return validity |
| `/api/app-config/` | `GET` | Public | Institutional metadata, app version, and guidelines |

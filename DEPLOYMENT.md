# Production Deployment & Operations Guide
## School ID Card Management System

This comprehensive guide details the step-by-step procedures to deploy, secure, and maintain the **Django Web Admin / REST API Backend** and the **Flutter Teacher Mobile Application** in a production environment.

---

## 1. System Architecture in Production

```
                                      [ Internet ]
                                           |
                                           | HTTPS (443)
                                           v
                              +------------------------+
                              |   Nginx Reverse Proxy  |
                              |   (SSL Termination)    |
                              +-----------+------------+
                                          |
                +-------------------------+-------------------------+
                |                                                   |
                v                                                   v
   +-------------------------+                         +-------------------------+
   |   Static Assets / CDN   |                         |     Gunicorn WSGI       |
   |   (/static/, /media/)   |                         |  (127.0.0.1:8000 socket)|
   +-------------------------+                         +------------+------------+
                                                                    |
                                                                    v
                                                       +-------------------------+
                                                       |     Django Application  |
                                                       | (Admin Panel, REST API) |
                                                       +------------+------------+
                                                                    |
                                                                    v
                                                       +-------------------------+
                                                       |    PostgreSQL 15+ DB    |
                                                       |   (ACID / Encrypted)    |
                                                       +-------------------------+

             +------------------------------------------------------+
             |                                                      |
             v                                                      v
+-------------------------+                            +-------------------------+
|   Flutter Mobile App    |                            |    Admin Desktop Web    |
| (Android .apk / .aab)   |                            |   (Chrome / Edge / Mac) |
+-------------------------+                            +-------------------------+
```

---

## 2. Server Requirements & Prerequisites

### 2.1 Recommended Server Specs (Virtual Private Server)
- **OS**: Ubuntu 22.04 LTS or 24.04 LTS
- **CPU**: 2+ vCPUs
- **RAM**: 4 GB minimum (8 GB recommended for concurrent PDF rendering)
- **Storage**: 40 GB+ NVMe SSD
- **Domain**: Registered domain with DNS records (`A` record pointing to server IP, e.g. `school.example.com` and `api.school.example.com`)

### 2.2 System Packages Installation
On your Ubuntu server, update repositories and install core dependencies:

```bash
sudo apt update && sudo apt upgrade -y
sudo apt install -y python3-pip python3-venv python3-dev \
    libpq-dev postgresql postgresql-contrib \
    nginx git curl certbot python3-certbot-nginx \
    libjpeg-dev zlib1g-dev libfreetype6-dev liblcms2-dev libopenjp2-7 libtiff5
```

---

## 3. PostgreSQL Database Setup

### 3.1 Create Database & Dedicated User
Log in to the PostgreSQL prompt:

```bash
sudo -u postgres psql
```

Execute the following SQL commands (replace `StrongPasswordHere123!` with a high-entropy password):

```sql
CREATE DATABASE school_id_db;
CREATE USER school_admin WITH PASSWORD 'StrongPasswordHere123!';

ALTER ROLE school_admin SET client_encoding TO 'utf8';
ALTER ROLE school_admin SET default_transaction_isolation TO 'read committed';
ALTER ROLE school_admin SET timezone TO 'UTC';

GRANT ALL PRIVILEGES ON DATABASE school_id_db TO school_admin;
\q
```

---

## 4. Backend Deployment (Django + Gunicorn)

### 4.1 Clone Repository & Set Up Virtual Environment

```bash
sudo mkdir -p /var/www/school_id_system
sudo chown -R $USER:$USER /var/www/school_id_system
cd /var/www/school_id_system

# Clone your project repository
git clone <YOUR_GIT_REPO_URL> .

# Create and activate Python virtualenv
python3 -m venv venv
source venv/bin/activate

# Upgrade pip and install production requirements
pip install --upgrade pip
pip install -r backend/requirements.txt
pip install gunicorn psycopg2-binary
```

---

### 4.2 Production Environment Configuration (`.env`)
Create `/var/www/school_id_system/.env` with strict permissions:

```bash
nano /var/www/school_id_system/.env
```

Paste and adjust the production settings:

```ini
# Security
SECRET_KEY=generate-a-secure-50-char-random-key-with-secrets-token_urlsafe
DEBUG=False
ALLOWED_HOSTS=school.yourdomain.com,api.yourdomain.com,127.0.0.1,localhost

# Database Configuration (PostgreSQL)
DB_ENGINE=django.db.backends.postgresql
DB_NAME=school_id_db
DB_USER=school_admin
DB_PASSWORD=StrongPasswordHere123!
DB_HOST=127.0.0.1
DB_PORT=5432

# CORS Configuration (for Flutter Web and Mobile)
CORS_ALLOWED_ORIGINS=https://school.yourdomain.com,https://api.yourdomain.com

# Paths & Storage
STATIC_URL=/static/
MEDIA_URL=/media/

# Application Branding & Placeholders
APP_NAME=School ID Card Management System
APP_VERSION=1.0.0
APP_DESIGNER_NAME=[YOUR FULL NAME]
APP_DESIGNER_ROLE=Designer & Developer
APP_CONTACT_PHONE=[YOUR PHONE]
APP_CONTACT_EMAIL=[YOUR EMAIL]
APP_WEBSITE=[YOUR WEBSITE]
APP_COPYRIGHT_YEAR=2026
```

Secure the environment file:
```bash
chmod 600 /var/www/school_id_system/.env
```

---

### 4.3 Django Static & Database Migration

```bash
cd /var/www/school_id_system/backend
source ../venv/bin/activate

# Apply migrations on PostgreSQL
python manage.py migrate

# Collect static assets into staticfiles directory
python manage.py collectstatic --noinput

# Run security check
python manage.py check --deploy
```

Create the initial Administrator account:
```bash
python manage.py createsuperuser
# Enter username, email, and strong password
```

---

### 4.4 Set Up Systemd Service for Gunicorn
Create a systemd service file:

```bash
sudo nano /etc/systemd/system/school_id.service
```

Add the following configuration:

```ini
[Unit]
Description=Gunicorn daemon for School ID Card Management System
After=network.target postgresql.service

[Service]
User=www-data
Group=www-data
WorkingDirectory=/var/www/school_id_system/backend
ExecStart=/var/www/school_id_system/venv/bin/gunicorn \
          --access-logfile /var/log/gunicorn/access.log \
          --error-logfile /var/log/gunicorn/error.log \
          --workers 4 \
          --bind unix:/run/school_id.sock \
          --timeout 120 \
          config.wsgi:application

Restart=always
RestartSec=5

[Install]
WantedBy=multi-user.target
```

Create logging and runtime socket directories:
```bash
sudo mkdir -p /var/log/gunicorn
sudo chown -R www-data:www-data /var/log/gunicorn
sudo chown -R www-data:www-data /var/www/school_id_system/backend/media
sudo chown -R www-data:www-data /var/www/school_id_system/backend/static
```

Enable and start the Gunicorn service:
```bash
sudo systemctl daemon-reload
sudo systemctl start school_id
sudo systemctl enable school_id
sudo systemctl status school_id
```

---

## 5. Nginx & SSL Configuration (HTTPS)

### 5.1 Create Nginx Site Configuration

```bash
sudo nano /etc/nginx/sites-available/school_id
```

Paste the following Nginx block:

```nginx
server {
    server_name school.yourdomain.com;

    client_max_body_size 50M;

    # Static Assets
    location /static/ {
        alias /var/www/school_id_system/backend/staticfiles/;
        expires 30d;
        add_header Cache-Control "public, no-transform";
    }

    # Media Uploads (Photos, Logos, Generated PDFs)
    location /media/ {
        alias /var/www/school_id_system/backend/media/;
        expires 7d;
        add_header Cache-Control "public, no-transform";
    }

    # Application Proxy
    location / {
        include proxy_params;
        proxy_pass http://unix:/run/school_id.sock;
        proxy_set_header X-Forwarded-Proto $scheme;
        proxy_read_timeout 180s;
        proxy_connect_timeout 180s;
    }
}
```

Enable the site and verify syntax:
```bash
sudo ln -s /etc/nginx/sites-available/school_id /etc/nginx/sites-enabled/
sudo nginx -t
sudo systemctl restart nginx
```

---

### 5.2 Obtain Free SSL Certificates (Certbot / Let's Encrypt)

```bash
sudo certbot --nginx -d school.yourdomain.com
```
Follow prompts to select automatic redirect from HTTP to HTTPS. Certbot automatically configures renew timers.

---

## 6. Flutter Mobile App Release Build (`school_id_teacher_app`)

### 6.1 Update Production API Base URL
Open `mobile/school_id_teacher_app/lib/constants/api_constants.dart`:

```dart
class ApiConstants {
  // Set to your production domain with HTTPS:
  static const String _productionBaseUrl = "https://school.yourdomain.com/api";

  static String get baseUrl => _productionBaseUrl;
}
```

---

### 6.2 Android Production Release (APK & App Bundle)

#### Step 1: Generate Release Keystore
In your terminal:
```bash
keytool -genkey -v -keystore school-id-release-key.jks -keyalg RSA -keysize 2048 -validity 10000 -alias school_id_key
```
Store `school-id-release-key.jks` in a secure location (never commit to git).

#### Step 2: Configure `android/key.properties`
Create `mobile/school_id_teacher_app/android/key.properties`:
```ini
storePassword=YourKeystorePassword
keyPassword=YourKeyPassword
keyAlias=school_id_key
storeFile=/path/to/school-id-release-key.jks
```

#### Step 3: Build the Android App Bundle (for Google Play Store):
```bash
cd mobile/school_id_teacher_app
flutter build appbundle --release
```
*Output artifact:* `build/app/outputs/bundle/release/app-release.aab`

#### Step 4: Build Standalone Signed APK (for direct school distribution):
```bash
flutter build apk --release --split-per-abi
```
*Output artifact:* `build/app/outputs/flutter-apk/app-arm64-v8a-release.apk`

---

### 6.3 Windows Desktop Production Release (for Teacher Laptops)
To build a standalone `.exe` installer for Windows laptops:

```bash
cd mobile/school_id_teacher_app
flutter build windows --release
```
*Output folder:* `build/windows/x64/runner/Release/`
Distribute this folder or package it into an installer with Inno Setup or NSIS.

---

## 7. Security Hardening Checklist

| Task | Configuration | Purpose |
| :--- | :--- | :--- |
| **HTTPS Only** | `SECURE_SSL_REDIRECT = True` | Forces all web traffic over TLS 1.3 |
| **HSTS Header** | `SECURE_HSTS_SECONDS = 31536000` | Prevents SSL-stripping attacks |
| **Secure Cookies** | `SESSION_COOKIE_SECURE = True`, `CSRF_COOKIE_SECURE = True` | Prohibits cookie transmission over cleartext |
| **Host Header Validation** | `ALLOWED_HOSTS = ['school.yourdomain.com']` | Defends against DNS rebinding & cache poisoning |
| **Upload File Limits** | `client_max_body_size 50M;` | Prevents memory exhaustion attacks |
| **MIME Validation** | Pillow image header inspection | Eliminates extension spoofing in bulk uploads |
| **JWT Access Limits** | 60-minute access token, 7-day refresh token | Mitigates token compromise risks |

---

## 8. Backup & Disaster Recovery Automation

### 8.1 Automated Database & Photos Backup Script
Create `/usr/local/bin/backup_school_id.sh`:

```bash
sudo nano /usr/local/bin/backup_school_id.sh
```

Paste:

```bash
#!/bin/bash
BACKUP_DIR="/var/backups/school_id"
DATE=$(date +"%Y%m%d_%H%M%S")

mkdir -p $BACKUP_DIR

# 1. PostgreSQL Database Dump (compressed)
pg_dump -U school_admin -h 127.0.0.1 school_id_db | gzip > $BACKUP_DIR/db_${DATE}.sql.gz

# 2. Student Photos & Logos Archive
tar -czf $BACKUP_DIR/media_${DATE}.tar.gz -C /var/www/school_id_system/backend media/

# 3. Retain only backups from last 30 days
find $BACKUP_DIR -type f -mtime +30 -exec rm {} +

echo "Backup completed successfully at $DATE"
```

Make executable:
```bash
sudo chmod +x /usr/local/bin/backup_school_id.sh
```

### 8.2 Schedule Daily Cron Job
Open crontab:
```bash
sudo crontab -e
```
Add entry to run every midnight at 02:00 AM:
```cron
0 2 * * * /usr/local/bin/backup_school_id.sh >> /var/log/school_id_backup.log 2>&1
```

---

## 9. Troubleshooting & Common Operational Commands

### View Live Gunicorn Logs
```bash
sudo journalctl -u school_id -f
```

### View Live Nginx Error Logs
```bash
sudo tail -f /var/log/nginx/error.log
```

### Restart Backend Service after Git Update
```bash
cd /var/www/school_id_system
git pull origin main
source venv/bin/activate
pip install -r backend/requirements.txt
python backend/manage.py migrate
python backend/manage.py collectstatic --noinput
sudo systemctl restart school_id
```

### Database Restoration Procedure
In case of disaster recovery:
```bash
gunzip < /var/backups/school_id/db_YYYYMMDD_HHMMSS.sql.gz | psql -U school_admin -h 127.0.0.1 school_id_db
```

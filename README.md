# ☁️ Cloud ERP System

A full-featured, cloud-native **Enterprise Resource Planning (ERP)** web application built with **Django** and deployed on **AWS**. Manage products, customers, and invoices — with automatic backups to S3, real-time monitoring via CloudWatch, and a PostgreSQL database on RDS.

---

## 🚀 Features

- **User Authentication** — Register, login, logout, and forgot-password with security questions
- **Product Management** — Add, update, delete, and list products with stock quantities
- **Customer Management** — Manage customer records including contact and address info
- **Invoice System** — Create invoices with multiple line items; view invoice history with date/customer filters
- **Billing Reports** — Summary of total revenue and invoice counts
- **CSV Export** — Export invoices, customers, products, or full backups as downloadable CSV files
- **CSV Import** — Bulk import products and customers via CSV upload
- **AWS S3 Backups** — All exports are automatically uploaded to an S3 bucket
- **AWS CloudWatch** — User actions and business metrics are logged directly to CloudWatch
- **AWS RDS** — PostgreSQL database hosted on Amazon RDS
- **AWS IAM** — Credential and permission validation via IAM utilities

---

## 🏗️ Tech Stack

| Layer | Technology |
|---|---|
| Backend | Django 3.2 (Python) |
| Database | PostgreSQL (AWS RDS) |
| File Storage | AWS S3 |
| Monitoring | AWS CloudWatch |
| Auth/Security | AWS IAM + Django Auth |
| Deployment | AWS EC2 (eu-north-1) |
| Linting/Security | flake8, pylint, bandit |

---

## 📁 Project Structure

```
erp_project/
├── core/                        # Main Django app
│   ├── models.py                # UserProfile, Product, Customer, Invoice, InvoiceItem
│   ├── views.py                 # All business logic views
│   ├── urls.py                  # URL routing
│   ├── templates/core/          # HTML templates
│   └── migrations/              # Database migrations
├── erp_project/                 # Django project config
│   ├── settings.py              # Settings (AWS, DB, logging)
│   ├── urls.py                  # Root URL config
│   ├── wsgi.py
│   └── asgi.py
├── utils/                       # Custom AWS utility libraries
│   ├── s3_utils.py              # S3Manager — upload/manage backups
│   ├── cloudwatch_utils.py      # CloudWatchLogger + CloudWatchMetrics
│   ├── rds_utils.py             # RDSStats + RDSHealthCheck
│   ├── iam_utils.py             # IAMCredentialCheck + SecureConfig
│   ├── auth_utils.py            # Auth helpers
│   ├── export_utils.py          # CSV export helpers
│   ├── import_utils.py          # CSV import helpers
│   ├── invoice_utils.py         # Invoice helpers
│   ├── report_utils.py          # Report helpers
│   └── validation_utils.py     # Input validation
├── cloud_erp_auth/              # Reusable PyPI auth package
│   └── cloud_erp_auth/
│       └── services.py
├── manage.py
└── db.sqlite3                   # Local dev DB (use RDS in production)
```

---

## ⚙️ Setup & Installation

### 1. Clone the Repository

```bash
git clone https://github.com/your-username/erp_project.git
cd erp_project
```

### 2. Create a Virtual Environment

```bash
python -m venv venv
source venv/bin/activate        # Windows: venv\Scripts\activate
pip install -r requirements.txt
```

### 3. Configure Environment Variables

Create a `.env` file in the project root (never commit this):

```env
SECRET_KEY=your-django-secret-key

# PostgreSQL / AWS RDS
DB_NAME=erp_db
DB_USER=erpuser
DB_PASSWORD=your-db-password
DB_HOST=your-rds-endpoint.rds.amazonaws.com

# AWS Credentials
AWS_ACCESS_KEY_ID=your-access-key
AWS_SECRET_ACCESS_KEY=your-secret-key

# Logging
LOG_FILE_PATH=/path/to/erp_logs.log
```

### 4. Run Migrations

```bash
python manage.py migrate
```

### 5. Create a Superuser (optional)

```bash
python manage.py createsuperuser
```

### 6. Start the Development Server

```bash
python manage.py runserver
```

Visit `http://127.0.0.1:8000` in your browser.

---

## 🌐 URL Reference

| URL | Description |
|---|---|
| `/` | Home page |
| `/register/` | User registration |
| `/login/` | Login |
| `/logout/` | Logout |
| `/forgot-password/` | Password reset via security question |
| `/dashboard/` | Main dashboard with summary stats |
| `/products/` | Product list |
| `/products/add/` | Add a product |
| `/customers/` | Customer list |
| `/customers/add/` | Add a customer |
| `/invoice/create/` | Create an invoice |
| `/invoice/list/` | Invoice list with filters |
| `/report/` | Billing report |
| `/invoice/export/` | Export invoices to CSV + S3 |
| `/backup/export/` | Export backup (customers/products/invoices/full) |
| `/backup/import/` | Import backup from CSV |

---

## ☁️ AWS Integration

### S3 — `utils/s3_utils.py`
The `S3Manager` class handles all S3 file operations. On every export, the CSV is uploaded to `s3://erp-exports-imran/` automatically.

### CloudWatch — `utils/cloudwatch_utils.py`
- `CloudWatchLogger` sends structured log events (login, logout, invoice creation, backup exports/imports) directly to CloudWatch Logs under the `/erp/django` log group.
- `CloudWatchMetrics` publishes custom business metrics (products added, invoices created, backups exported) as CloudWatch metric graphs.

### RDS — `utils/rds_utils.py`
- `RDSStats` fetches live dashboard counts (products, customers, invoices) from the PostgreSQL RDS instance.
- `RDSHealthCheck` verifies the database connection is alive.

### IAM — `utils/iam_utils.py`
- `IAMCredentialCheck` validates AWS credentials via STS on startup.
- `IAMPermissionAudit` checks active S3/CloudWatch permissions.
- `SecureConfig` safely loads secrets from environment variables.

---

## 📦 Reusable Auth Package

The `cloud_erp_auth` directory is a standalone, installable PyPI package for reusable Django registration logic.

```bash
pip install imran-cloud-erp-auth
```

**Author:** Imran Murshad | **Version:** 0.1.2

---

## 🔒 Security

- `DEBUG = False` in production
- All secrets loaded from environment variables (never hardcoded)
- Django password validators enforced
- CSRF middleware enabled
- Security scanning with **bandit** and dependency auditing with **pip-audit**
- Code quality enforced with **flake8** and **pylint**

---

## 📄 License

This project is for educational and portfolio purposes.

---

## 👤 Author

**Imran Murshad**  
Cloud ERP Project — Built with Django + AWS

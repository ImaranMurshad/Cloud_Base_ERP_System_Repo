"""
views.py — ERP Project (AWS Cloud Version)
==========================================
All 4 custom AWS libraries are imported and used here:

  utils/s3_utils.py          → S3Manager          (upload CSV exports)
  utils/cloudwatch_utils.py  → CloudWatchLogger    (log user actions)
                             → CloudWatchMetrics   (record business metrics)
  utils/rds_utils.py         → RDSStats            (live DB counts for dashboard)
  utils/iam_utils.py         → IAMCredentialCheck  (verify AWS is connected)
"""

import csv
import logging
from io import TextIOWrapper

from django.shortcuts import render, redirect
from django.contrib.auth.models import User
from django.contrib.auth import authenticate, login, logout
from django.contrib.auth.decorators import login_required
from django.db.models import Sum
from django.http import HttpResponse
from django.utils.dateparse import parse_date

from utils.invoice_utils import calculate_total
from utils.report_utils import get_total_revenue

# ================================================================
# Custom AWS Libraries
# ================================================================
from utils.s3_utils import S3Manager
from utils.cloudwatch_utils import CloudWatchLogger, CloudWatchMetrics
from utils.rds_utils import RDSStats
from utils.iam_utils import IAMCredentialCheck
# ================================================================

from .models import UserProfile, Product, Customer, Invoice, InvoiceItem

logger = logging.getLogger('core')


# ================= HOME =================

def index(request):
    return render(request, 'core/index.html')

def about(request):
    return render(request, 'core/about.html')

def contact(request):
    return render(request, 'core/contact.html')


# ================= REGISTER =================

def register(request):
    if request.method == "POST":
        full_name        = request.POST.get('full_name')
        email            = request.POST.get('email')
        username         = request.POST.get('username')
        password         = request.POST.get('password')
        confirm_password = request.POST.get('confirm_password')
        question         = request.POST.get('question')
        answer           = request.POST.get('answer')

        if not all([full_name, email, username, password, confirm_password, question, answer]):
            return render(request, 'core/register.html', {'error': 'All fields are required'})
        if password != confirm_password:
            return render(request, 'core/register.html', {'error': 'Passwords do not match'})
        if User.objects.filter(username=username).exists():
            return render(request, 'core/register.html', {'error': 'Username already exists'})
        if User.objects.filter(email=email).exists():
            return render(request, 'core/register.html', {'error': 'Email already registered'})

        user = User.objects.create_user(username=username, password=password, email=email)
        UserProfile.objects.create(
            user=user, full_name=full_name, email=email,
            security_question=question, security_answer=answer
        )
        return redirect('/login/')

    return render(request, 'core/register.html')


# ================= LOGIN =================

def login_view(request):
    if request.method == "POST":
        username = request.POST.get('username')
        password = request.POST.get('password')

        if not username or not password:
            return render(request, 'core/login.html', {'error': 'Please enter all fields'})

        user = authenticate(request, username=username, password=password)

        if user:
            login(request, user)

            # ---- CloudWatchLogger: log successful login ----
            try:
                CloudWatchLogger().log_login(username=username)
            except Exception as e:
                logger.warning(f"CloudWatch log_login failed: {e}")

            return redirect('/dashboard/')
        else:
            return render(request, 'core/login.html', {'error': 'Invalid credentials'})

    return render(request, 'core/login.html')


# ================= LOGOUT =================

def logout_view(request):
    # ---- CloudWatchLogger: log logout ----
    try:
        if request.user.is_authenticated:
            CloudWatchLogger().log_logout(username=request.user.username)
    except Exception as e:
        logger.warning(f"CloudWatch log_logout failed: {e}")

    logout(request)
    return redirect('/')


# ================= FORGOT PASSWORD =================

def forgot_password(request):
    if request.method == "POST":
        username     = request.POST.get('username')
        email        = request.POST.get('email')
        question     = request.POST.get('question')
        answer       = request.POST.get('answer')
        new_password = request.POST.get('new_password')

        try:
            user    = User.objects.get(username=username)
            profile = UserProfile.objects.get(user=user)

            if not new_password:
                if (
                    profile.email == email and
                    profile.security_question == question and
                    profile.security_answer.lower() == answer.lower()
                ):
                    return render(request, 'core/forgot_password.html', {
                        'show_password': True, 'success': 'Verified! Enter new password.'
                    })
                else:
                    return render(request, 'core/forgot_password.html', {'error': 'Invalid details'})
            else:
                user.set_password(new_password)
                user.save()
                return render(request, 'core/forgot_password.html', {'success': 'Password reset successful!'})

        except User.DoesNotExist:
            return render(request, 'core/forgot_password.html', {'error': 'User not found'})

    return render(request, 'core/forgot_password.html')


# ================= DASHBOARD =================

@login_required
def dashboard(request):
    # ---- RDSStats: single call replaces 3 separate .count() queries ----
    try:
        stats           = RDSStats().get_summary(user=request.user)
        total_products  = stats['total_products']
        total_customers = stats['total_customers']
        total_invoices  = stats['total_invoices']
    except Exception as e:
        logger.error(f"RDSStats failed: {e}")
        total_products  = Product.objects.filter(user=request.user).count()
        total_customers = Customer.objects.filter(user=request.user).count()
        total_invoices  = Invoice.objects.filter(user=request.user).count()

    return render(request, 'core/dashboard.html', {
        'total_products':  total_products,
        'total_customers': total_customers,
        'total_invoices':  total_invoices,
    })


# ================= PRODUCTS =================

@login_required
def product_list(request):
    products = Product.objects.filter(user=request.user)
    return render(request, 'core/product_list.html', {'products': products})


@login_required
def add_product(request):
    if request.method == "POST":
        name     = request.POST.get('name')
        price    = request.POST.get('price')
        quantity = request.POST.get('quantity')

        if not all([name, price, quantity]):
            return render(request, 'core/add_product.html', {'error': 'All fields required'})

        Product.objects.create(user=request.user, name=name, price=price, quantity=quantity)

        # ---- CloudWatchMetrics: count new products ----
        try:
            CloudWatchMetrics().record_product_added()
        except Exception as e:
            logger.warning(f"CloudWatch metric failed (add_product): {e}")

        return redirect('/products/')

    return render(request, 'core/add_product.html')


@login_required
def update_product(request, id):
    product = Product.objects.get(id=id, user=request.user)
    if request.method == "POST":
        product.name     = request.POST.get('name')
        product.price    = request.POST.get('price')
        product.quantity = request.POST.get('quantity')
        product.save()
        return redirect('/products/')
    return render(request, 'core/update_product.html', {'product': product})


@login_required
def delete_product(request, id):
    Product.objects.get(id=id, user=request.user).delete()
    return redirect('/products/')


# ================= CUSTOMERS =================

@login_required
def customer_list(request):
    customers = Customer.objects.filter(user=request.user)
    return render(request, 'core/customer_list.html', {'customers': customers})


@login_required
def add_customer(request):
    if request.method == "POST":
        name    = request.POST.get('name')
        email   = request.POST.get('email')
        phone   = request.POST.get('phone')
        address = request.POST.get('address')

        if not all([name, email, phone]):
            return render(request, 'core/add_customer.html', {'error': 'All fields required'})

        Customer.objects.create(user=request.user, name=name, email=email, phone=phone, address=address)

        # ---- CloudWatchMetrics: count new customers ----
        try:
            CloudWatchMetrics().record_customer_added()
        except Exception as e:
            logger.warning(f"CloudWatch metric failed (add_customer): {e}")

        return redirect('/customers/')

    return render(request, 'core/add_customer.html')


@login_required
def update_customer(request, id):
    customer = Customer.objects.get(id=id, user=request.user)
    if request.method == "POST":
        customer.name    = request.POST.get('name')
        customer.email   = request.POST.get('email')
        customer.phone   = request.POST.get('phone')
        customer.address = request.POST.get('address')
        customer.save()
        return redirect('/customers/')
    return render(request, 'core/update_customer.html', {'customer': customer})


@login_required
def delete_customer(request, id):
    Customer.objects.get(id=id, user=request.user).delete()
    return redirect('/customers/')


# ================= INVOICES =================

@login_required
def create_invoice(request):
    products  = Product.objects.filter(user=request.user)
    customers = Customer.objects.filter(user=request.user)

    if request.method == "POST":
        customer_id = request.POST.get('customer')

        if customer_id == "new":
            customer = Customer.objects.create(
                user=request.user,
                name=request.POST.get('cust_name'),
                email=request.POST.get('cust_email'),
                phone=request.POST.get('cust_phone'),
                address=request.POST.get('cust_address'),
            )
        else:
            customer = Customer.objects.get(id=customer_id, user=request.user)

        invoice     = Invoice.objects.create(user=request.user, customer=customer, total_amount=0)
        total       = 0
        product_ids = request.POST.getlist('product')
        quantities  = request.POST.getlist('quantity')

        for i in range(len(product_ids)):
            product  = Product.objects.get(id=product_ids[i])
            qty      = int(quantities[i])
            total   += product.price * qty
            InvoiceItem.objects.create(invoice=invoice, product=product, quantity=qty, price=product.price)

        invoice.total_amount = total
        invoice.save()

        # ---- CloudWatchLogger + Metrics: invoice created ----
        try:
            CloudWatchLogger().log_invoice_created(
                username=request.user.username,
                invoice_id=invoice.id,
                total_amount=total,
            )
            CloudWatchMetrics().record_invoice_created(total_amount=total)
        except Exception as e:
            logger.warning(f"CloudWatch invoice logging failed: {e}")

        return redirect(f'/invoice/view/{invoice.id}/')

    return render(request, 'core/create_invoice.html', {'products': products, 'customers': customers})


def invoice_view(request, id):
    invoice = Invoice.objects.get(id=id, user=request.user)
    items   = InvoiceItem.objects.filter(invoice=invoice)
    for item in items:
        item.subtotal = item.price * item.quantity
    return render(request, 'core/invoice_view.html', {'invoice': invoice, 'items': items})


@login_required
def invoice_list(request):
    invoices   = Invoice.objects.filter(user=request.user)
    start_date = request.GET.get('start_date')
    end_date   = request.GET.get('end_date')
    customer   = request.GET.get('customer')

    if start_date:
        invoices = invoices.filter(created_at__date__gte=parse_date(start_date))
    if end_date:
        invoices = invoices.filter(created_at__date__lte=parse_date(end_date))
    if customer:
        invoices = invoices.filter(customer__name__icontains=customer)

    invoices = invoices.order_by('-id')

    return render(request, 'core/invoice_list.html', {
        'invoices':       invoices,
        'total_revenue':  invoices.aggregate(Sum('total_amount'))['total_amount__sum'] or 0,
        'total_invoices': invoices.count(),
    })


# ================= REPORT =================

@login_required
def billing_report(request):
    invoices      = Invoice.objects.filter(user=request.user)
    total_revenue = invoices.aggregate(Sum('total_amount'))['total_amount__sum'] or 0
    return render(request, 'core/billing_report.html', {
        'total_revenue':  total_revenue,
        'total_invoices': invoices.count(),
        'invoices':       invoices,
    })


# ================= EXPORT INVOICES =================

@login_required
def export_invoices(request):
    invoices = Invoice.objects.filter(user=request.user)

    response = HttpResponse(content_type='text/csv')
    response['Content-Disposition'] = 'attachment; filename="invoices.csv"'
    writer = csv.writer(response)
    writer.writerow(['ID', 'Customer', 'Total', 'Date'])

    for inv in invoices:
        writer.writerow([inv.id, inv.customer.name, inv.total_amount, inv.created_at])

    # ---- S3Manager: upload invoice CSV to S3 ----
    try:
        s3_key = S3Manager().upload_invoice_export(
            username=request.user.username,
            csv_bytes=response.content,
        )
        CloudWatchLogger().log_backup_exported(
            username=request.user.username,
            backup_type='invoices',
            s3_key=s3_key,
        )
    except Exception as e:
        logger.error(f"S3/CloudWatch export_invoices failed: {e}")

    return response


# ================= EXPORT BACKUP =================

@login_required
def export_backup(request):
    if request.method == "POST":
        backup_type = request.POST.get('backup_type')

        if not backup_type:
            return render(request, 'core/export_backup.html', {'error': 'Please select backup type'})

        response = HttpResponse(content_type='text/csv')
        writer   = csv.writer(response)

        if backup_type == "customer":
            response['Content-Disposition'] = 'attachment; filename="customers.csv"'
            writer.writerow(['CUSTOMERS'])
            writer.writerow(['Name', 'Email', 'Phone', 'Address'])
            for c in Customer.objects.filter(user=request.user):
                writer.writerow([c.name, c.email, c.phone, c.address])

        elif backup_type == "product":
            response['Content-Disposition'] = 'attachment; filename="products.csv"'
            writer.writerow(['PRODUCTS'])
            writer.writerow(['Name', 'Price', 'Quantity'])
            for p in Product.objects.filter(user=request.user):
                writer.writerow([p.name, p.price, p.quantity])

        elif backup_type == "invoice":
            response['Content-Disposition'] = 'attachment; filename="invoices.csv"'
            writer.writerow(['INVOICES'])
            writer.writerow(['InvoiceID', 'Customer', 'Total', 'Date'])
            for i in Invoice.objects.filter(user=request.user):
                writer.writerow([i.id, i.customer.name, i.total_amount, i.created_at])

        elif backup_type == "full":
            response['Content-Disposition'] = 'attachment; filename="full_backup.csv"'
            writer.writerow(['CUSTOMERS'])
            writer.writerow(['Name', 'Email', 'Phone', 'Address'])
            for c in Customer.objects.filter(user=request.user):
                writer.writerow([c.name, c.email, c.phone, c.address])
            writer.writerow([])
            writer.writerow(['PRODUCTS'])
            writer.writerow(['Name', 'Price', 'Quantity'])
            for p in Product.objects.filter(user=request.user):
                writer.writerow([p.name, p.price, p.quantity])
            writer.writerow([])
            writer.writerow(['INVOICES'])
            writer.writerow(['InvoiceID', 'Customer', 'Total', 'Date'])
            for i in Invoice.objects.filter(user=request.user):
                writer.writerow([i.id, i.customer.name, i.total_amount, i.created_at])

        # ---- S3Manager: upload backup CSV to S3 ----
        # (replaces the raw boto3.client() block that was in the original views.py)
        s3_key = None
        try:
            s3_key = S3Manager().upload_backup(
                username=request.user.username,
                backup_type=backup_type,
                csv_bytes=response.content,
            )
        except Exception as e:
            logger.error(f"S3Manager upload_backup failed: {e}")

        # ---- CloudWatchLogger + Metrics: log the export ----
        try:
            CloudWatchLogger().log_backup_exported(
                username=request.user.username,
                backup_type=backup_type,
                s3_key=s3_key,
            )
            CloudWatchMetrics().record_backup_exported()
        except Exception as e:
            logger.warning(f"CloudWatch backup log failed: {e}")

        return response

    return render(request, 'core/export_backup.html')


# ================= IMPORT BACKUP =================

@login_required
def import_backup(request):
    if request.method == "POST":
        file = request.FILES.get('file')

        if not file:
            return render(request, 'core/import_backup.html', {'error': 'Please upload a file'})

        decoded_file = TextIOWrapper(file.file, encoding='utf-8')
        reader       = csv.reader(decoded_file)
        mode         = None

        for row in reader:
            if not row:
                continue

            header = row[0].strip().upper()
            if "CUSTOMERS" in header:
                mode = "customer"
                continue
            elif "PRODUCTS" in header:
                mode = "product"
                continue

            if row[0].lower() in ["name", "invoice id"]:
                continue

            try:
                if mode == "product":
                    Product.objects.create(
                        user=request.user, name=row[0],
                        price=float(row[1]), quantity=int(row[2])
                    )
                elif mode == "customer":
                    Customer.objects.create(
                        user=request.user, name=row[0],
                        email=row[1], phone=row[2], address=row[3]
                    )
            except Exception as e:
                logger.error(f"import_backup row error: {e}")

        # ---- CloudWatchLogger + Metrics: log the import ----
        try:
            CloudWatchLogger().log_backup_imported(
                username=request.user.username,
                filename=file.name,
            )
            CloudWatchMetrics().record_backup_imported()
        except Exception as e:
            logger.warning(f"CloudWatch import log failed: {e}")

        return redirect('/dashboard/')

    return render(request, 'core/import_backup.html')

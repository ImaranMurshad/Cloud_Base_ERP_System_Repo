from django.shortcuts import render, redirect
from django.contrib.auth.models import User
from django.contrib.auth import authenticate, login, logout
from django.contrib.auth.decorators import login_required
from django.db.models import Sum

from utils.invoice_utils import calculate_total
from utils.report_utils import get_total_revenue

from .models import (
    UserProfile,
    Product,
    Customer,
    Invoice,
    InvoiceItem
)

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
        full_name = request.POST.get('full_name')
        email = request.POST.get('email')
        username = request.POST.get('username')
        password = request.POST.get('password')
        confirm_password = request.POST.get('confirm_password')
        question = request.POST.get('question')
        answer = request.POST.get('answer')

        if not all([full_name, email, username, password, confirm_password, question, answer]):
            return render(request, 'core/register.html', {'error': 'All fields are required'})

        if password != confirm_password:
            return render(request, 'core/register.html', {'error': 'Passwords do not match'})

        if User.objects.filter(username=username).exists():
            return render(request, 'core/register.html', {'error': 'Username already exists'})

        if User.objects.filter(email=email).exists():
            return render(request, 'core/register.html', {'error': 'Email already registered'})

        user = User.objects.create_user(
            username=username,
            password=password,
            email=email
        )

        UserProfile.objects.create(
            user=user,
            full_name=full_name,
            email=email,
            security_question=question,
            security_answer=answer
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
            return redirect('/dashboard/')
        else:
            return render(request, 'core/login.html', {'error': 'Invalid credentials'})

    return render(request, 'core/login.html')


# ================= LOGOUT =================
from django.contrib.auth import logout

def logout_view(request):
    logout(request)
    return redirect('/')

# ================= FORGOT PASSWORD =================

def forgot_password(request):
    if request.method == "POST":
        username = request.POST.get('username')
        email = request.POST.get('email')
        question = request.POST.get('question')
        answer = request.POST.get('answer')
        new_password = request.POST.get('new_password')

        try:
            user = User.objects.get(username=username)
            profile = UserProfile.objects.get(user=user)

            if not new_password:
                if (
                    profile.email == email and
                    profile.security_question == question and
                    profile.security_answer.lower() == answer.lower()
                ):
                    return render(request, 'core/forgot_password.html', {
                        'show_password': True,
                        'success': 'Verified! Enter new password.'
                    })
                else:
                    return render(request, 'core/forgot_password.html', {
                        'error': 'Invalid details'
                    })
            else:
                user.set_password(new_password)
                user.save()
                return render(request, 'core/forgot_password.html', {
                    'success': 'Password reset successful!'
                })

        except User.DoesNotExist:
            return render(request, 'core/forgot_password.html', {'error': 'User not found'})

    return render(request, 'core/forgot_password.html')


# ================= DASHBOARD =================

from .models import Product, Customer, Invoice
from django.contrib.auth.decorators import login_required

@login_required
def dashboard(request):
    total_products = Product.objects.filter(user=request.user).count()
    total_customers = Customer.objects.filter(user=request.user).count()
    total_invoices = Invoice.objects.filter(user=request.user).count()

    return render(request, 'core/dashboard.html', {
        'total_products': total_products,
        'total_customers': total_customers,
        'total_invoices': total_invoices
    })


# ================= PRODUCT =================

@login_required
def product_list(request):
    products = Product.objects.filter(user=request.user)
    return render(request, 'core/product_list.html', {'products': products})


@login_required
def add_product(request):
    if request.method == "POST":
        name = request.POST.get('name')
        price = request.POST.get('price')
        quantity = request.POST.get('quantity')

        if not all([name, price, quantity]):
            return render(request, 'core/add_product.html', {'error': 'All fields required'})

        Product.objects.create(
            user=request.user,
            name=name,
            price=price,
            quantity=quantity
        )

        return redirect('/products/')

    return render(request, 'core/add_product.html')


@login_required
def update_product(request, id):
    product = Product.objects.get(id=id, user=request.user)

    if request.method == "POST":
        product.name = request.POST.get('name')
        product.price = request.POST.get('price')
        product.quantity = request.POST.get('quantity')
        product.save()
        return redirect('/products/')

    return render(request, 'core/update_product.html', {'product': product})


@login_required
def delete_product(request, id):
    Product.objects.get(id=id, user=request.user).delete()
    return redirect('/products/')


# ================= CUSTOMER =================

@login_required
def customer_list(request):
    customers = Customer.objects.filter(user=request.user)
    return render(request, 'core/customer_list.html', {'customers': customers})


@login_required
def add_customer(request):
    if request.method == "POST":
        name = request.POST.get('name')
        email = request.POST.get('email')
        phone = request.POST.get('phone')
        address = request.POST.get('address')

        if not all([name, email, phone]):
            return render(request, 'core/add_customer.html', {'error': 'All fields required'})

        Customer.objects.create(
            user=request.user,
            name=name,
            email=email,
            phone=phone,
            address=address
        )

        return redirect('/customers/')

    return render(request, 'core/add_customer.html')


@login_required
def update_customer(request, id):
    customer = Customer.objects.get(id=id, user=request.user)

    if request.method == "POST":
        customer.name = request.POST.get('name')
        customer.email = request.POST.get('email')
        customer.phone = request.POST.get('phone')
        customer.address = request.POST.get('address')
        customer.save()
        return redirect('/customers/')

    return render(request, 'core/update_customer.html', {'customer': customer})


@login_required
def delete_customer(request, id):
    Customer.objects.get(id=id, user=request.user).delete()
    return redirect('/customers/')


# ================= INVOICE =================

@login_required
def create_invoice(request):
    products = Product.objects.filter(user=request.user)
    customers = Customer.objects.filter(user=request.user)

    if request.method == "POST":

        customer_id = request.POST.get('customer')

        if customer_id == "new":
            customer = Customer.objects.create(
                user=request.user,
                name=request.POST.get('cust_name'),
                email=request.POST.get('cust_email'),
                phone=request.POST.get('cust_phone'),
                address=request.POST.get('cust_address')
            )
        else:
            customer = Customer.objects.get(id=customer_id, user=request.user)

        invoice = Invoice.objects.create(
            user=request.user,
            customer=customer,
            total_amount=0
        )

        total = 0
        product_ids = request.POST.getlist('product')
        quantities = request.POST.getlist('quantity')

        for i in range(len(product_ids)):
            product = Product.objects.get(id=product_ids[i])
            qty = int(quantities[i])
            subtotal = product.price * qty
            total += subtotal

            InvoiceItem.objects.create(
                invoice=invoice,
                product=product,
                quantity=qty,
                price=product.price
            )

        invoice.total_amount = total
        invoice.save()

        # ✅ FIXED REDIRECT
        return redirect(f'/invoice/view/{invoice.id}/')

    return render(request, 'core/create_invoice.html', {
        'products': products,
        'customers': customers
    })


def invoice_view(request, id):
    invoice = Invoice.objects.get(id=id, user=request.user)
    items = InvoiceItem.objects.filter(invoice=invoice)

    # ✅ ADD THIS
    for item in items:
        item.subtotal = item.price * item.quantity

    return render(request, 'core/invoice_view.html', {
        'invoice': invoice,
        'items': items
    })


from django.db.models import Sum
from django.utils.dateparse import parse_date

@login_required
def invoice_list(request):
    invoices = Invoice.objects.filter(user=request.user)

    # 🔍 FILTERS
    start_date = request.GET.get('start_date')
    end_date = request.GET.get('end_date')
    customer = request.GET.get('customer')

    if start_date:
        invoices = invoices.filter(created_at__date__gte=parse_date(start_date))

    if end_date:
        invoices = invoices.filter(created_at__date__lte=parse_date(end_date))

    if customer:
        invoices = invoices.filter(customer__name__icontains=customer)

    invoices = invoices.order_by('-id')

    # 📊 REPORT DATA
    total_revenue = invoices.aggregate(Sum('total_amount'))['total_amount__sum'] or 0
    total_invoices = invoices.count()

    return render(request, 'core/invoice_list.html', {
        'invoices': invoices,
        'total_revenue': total_revenue,
        'total_invoices': total_invoices
    })


# ================= REPORT =================

@login_required
def billing_report(request):
    invoices = Invoice.objects.filter(user=request.user)

    total_revenue = invoices.aggregate(Sum('total_amount'))['total_amount__sum'] or 0

    return render(request, 'core/billing_report.html', {
        'total_revenue': total_revenue,
        'total_invoices': invoices.count(),
        'invoices': invoices
    })
    
import csv
from django.http import HttpResponse

@login_required
def export_invoices(request):
    invoices = Invoice.objects.filter(user=request.user)

    response = HttpResponse(content_type='text/csv')
    response['Content-Disposition'] = 'attachment; filename="invoices.csv"'

    writer = csv.writer(response)
    writer.writerow(['ID', 'Customer', 'Total', 'Date'])

    for inv in invoices:
        writer.writerow([inv.id, inv.customer.name, inv.total_amount, inv.created_at])

    return response


import csv
from django.http import HttpResponse

@login_required
def export_backup(request):
    response = HttpResponse(content_type='text/csv')
    response['Content-Disposition'] = 'attachment; filename="erp_backup.csv"'

    writer = csv.writer(response)

    # ===== PRODUCTS =====
    writer.writerow(['PRODUCTS'])
    writer.writerow(['Name', 'Price', 'Quantity'])

    products = Product.objects.filter(user=request.user)
    for p in products:
        writer.writerow([p.name, p.price, p.quantity])

    # ===== CUSTOMERS =====
    writer.writerow([])
    writer.writerow(['CUSTOMERS'])
    writer.writerow(['Name', 'Email', 'Phone', 'Address'])

    customers = Customer.objects.filter(user=request.user)
    for c in customers:
        writer.writerow([c.name, c.email, c.phone, c.address])

    return response


import csv
from io import TextIOWrapper
from django.contrib.auth.decorators import login_required
from django.shortcuts import render, redirect
from .models import Product, Customer

@login_required
def import_backup(request):
    if request.method == "POST":
        file = request.FILES.get('file')

        if not file:
            return render(request, 'core/import_backup.html', {
                'error': 'Please upload a file'
            })

        decoded_file = TextIOWrapper(file.file, encoding='utf-8')
        reader = csv.reader(decoded_file)

        mode = None

        for row in reader:

            if not row:
                continue

            # ✅ FIX HEADER MATCH
            header = row[0].strip().upper()

            if "CUSTOMERS" in header:
                mode = "customer"
                continue

            elif "PRODUCTS" in header:
                mode = "product"
                continue

            # ✅ SKIP COLUMN HEADERS
            if row[0].lower() in ["name", "invoice id"]:
                continue

            try:
                # ✅ INSERT PRODUCT
                if mode == "product":
                    Product.objects.create(
                        user=request.user,
                        name=row[0],
                        price=float(row[1]),
                        quantity=int(row[2])
                    )

                # ✅ INSERT CUSTOMER
                elif mode == "customer":
                    Customer.objects.create(
                        user=request.user,
                        name=row[0],
                        email=row[1],
                        phone=row[2],
                        address=row[3]
                    )

            except Exception as e:
                print("Error:", e)  # Debug

        return redirect('/dashboard/')

    return render(request, 'core/import_backup.html')




import csv
import boto3
from datetime import date
from django.conf import settings
from django.http import HttpResponse
from django.contrib.auth.decorators import login_required
from django.shortcuts import render
from .models import Customer, Product, Invoice


@login_required
def export_backup(request):

    if request.method == "POST":
        backup_type = request.POST.get('backup_type')

        if not backup_type:
            return render(request, 'core/export_backup.html', {
                'error': 'Please select backup type'
            })

        response = HttpResponse(content_type='text/csv')
        writer = csv.writer(response)

        # 🔹 CUSTOMER BACKUP
        if backup_type == "customer":
            response['Content-Disposition'] = 'attachment; filename="customers.csv"'

            writer.writerow(['CUSTOMERS'])
            writer.writerow(['Name', 'Email', 'Phone', 'Address'])

            for c in Customer.objects.filter(user=request.user):
                writer.writerow([c.name, c.email, c.phone, c.address])

        # 🔹 PRODUCT BACKUP
        elif backup_type == "product":
            response['Content-Disposition'] = 'attachment; filename="products.csv"'

            writer.writerow(['PRODUCTS'])
            writer.writerow(['Name', 'Price', 'Quantity'])

            for p in Product.objects.filter(user=request.user):
                writer.writerow([p.name, p.price, p.quantity])

        # 🔹 INVOICE BACKUP
        elif backup_type == "invoice":
            response['Content-Disposition'] = 'attachment; filename="invoices.csv"'

            writer.writerow(['INVOICES'])
            writer.writerow(['InvoiceID', 'Customer', 'Total', 'Date'])

            for i in Invoice.objects.filter(user=request.user):
                writer.writerow([i.id, i.customer.name, i.total_amount, i.created_at])

        # 🔹 FULL BACKUP
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

        # ✅ 🔥 UPLOAD TO S3 (AFTER CSV IS READY)
        try:
            s3 = boto3.client(
                's3',
                aws_access_key_id=settings.AWS_ACCESS_KEY_ID,
                aws_secret_access_key=settings.AWS_SECRET_ACCESS_KEY,
                region_name=settings.AWS_S3_REGION_NAME
            )

            filename = f"backup_{request.user.username}_{date.today()}.csv"

            s3.put_object(
                Bucket=settings.AWS_STORAGE_BUCKET_NAME,
                Key=f"backups/{filename}",
                Body=response.content,
                ContentType='text/csv'
            )

        except Exception as e:
            print("S3 Upload Error:", e)  # debug only

        return response

    return render(request, 'core/export_backup.html')
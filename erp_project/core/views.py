# ================= IMPORTS =================

# Django core utilities for rendering pages and redirects
from django.shortcuts import render, redirect

# Django authentication system
from django.contrib.auth.models import User
from django.contrib.auth import authenticate, login, logout

# Restrict access to logged-in users only
from django.contrib.auth.decorators import login_required

# HTTP response (used for file downloads like CSV)
from django.http import HttpResponse

# Database aggregation functions (SUM)
from django.db.models import Sum

# Used for parsing date filters from UI
from django.utils.dateparse import parse_date

# Python libraries for CSV handling
import csv
from io import TextIOWrapper


# ================= CUSTOM LIBRARIES =================
# These are user-defined reusable modules (VERY IMPORTANT FOR LO3)

# 👉 Handles invoice calculation logic (separation of business logic)
from utils.invoice_utils import calculate_total

# 👉 Handles report calculations like total revenue
from utils.report_utils import get_total_revenue

# 👉 Handles form validation (checks empty fields etc.)
from utils.validation_utils import required_fields


# ================= MODELS =================
# Importing database tables
from .models import UserProfile, Product, Customer, Invoice, InvoiceItem


# ================= HOME =================

# Landing page
def index(request):
    return render(request, 'core/index.html')

# About page
def about(request):
    return render(request, 'core/about.html')

# Contact page
def contact(request):
    return render(request, 'core/contact.html')


# ================= REGISTER =================

def register(request):
    if request.method == "POST":

        # Collect all input data
        data = [
            request.POST.get('full_name'),
            request.POST.get('email'),
            request.POST.get('username'),
            request.POST.get('password'),
            request.POST.get('confirm_password'),
            request.POST.get('question'),
            request.POST.get('answer')
        ]

        # ✅ Validate using custom library
        if not required_fields(data):
            return render(request, 'core/register.html', {'error': 'All fields required'})

        # Password match check
        if data[3] != data[4]:
            return render(request, 'core/register.html', {'error': 'Passwords do not match'})

        # Check username exists
        if User.objects.filter(username=data[2]).exists():
            return render(request, 'core/register.html', {'error': 'Username exists'})

        # Create user
        user = User.objects.create_user(username=data[2], password=data[3], email=data[1])

        # Create profile
        UserProfile.objects.create(
            user=user,
            full_name=data[0],
            email=data[1],
            security_question=data[5],
            security_answer=data[6]
        )

        return redirect('/login/')

    return render(request, 'core/register.html')


# ================= LOGIN =================

def login_view(request):
    if request.method == "POST":

        # Authenticate user credentials
        user = authenticate(
            request,
            username=request.POST.get('username'),
            password=request.POST.get('password')
        )

        if user:
            login(request, user)
            return redirect('/dashboard/')
        else:
            return render(request, 'core/login.html', {'error': 'Invalid credentials'})

    return render(request, 'core/login.html')


# ================= LOGOUT =================

def logout_view(request):
    logout(request)  # Destroy session
    return redirect('/')  # Redirect to homepage


# ================= FORGOT PASSWORD =================

def forgot_password(request):
    if request.method == "POST":

        # Get user inputs
        username = request.POST.get('username')
        email = request.POST.get('email')
        question = request.POST.get('question')
        answer = request.POST.get('answer')
        new_password = request.POST.get('new_password')

        try:
            user = User.objects.get(username=username)
            profile = UserProfile.objects.get(user=user)

            # Step 1: Verify user identity
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
                    return render(request, 'core/forgot_password.html', {'error': 'Invalid details'})

            # Step 2: Reset password
            else:
                user.set_password(new_password)
                user.save()
                return render(request, 'core/forgot_password.html', {
                    'success': 'Password reset successful!'
                })

        except:
            return render(request, 'core/forgot_password.html', {'error': 'User not found'})

    return render(request, 'core/forgot_password.html')


# ================= DASHBOARD =================

@login_required
def dashboard(request):

    # Fetch user-specific data
    products = Product.objects.filter(user=request.user)
    customers = Customer.objects.filter(user=request.user)
    invoices = Invoice.objects.filter(user=request.user)

    return render(request, 'core/dashboard.html', {
        'total_products': products.count(),
        'total_customers': customers.count(),
        'total_invoices': invoices.count(),

        # ✅ Revenue calculated using custom library
        'total_revenue': get_total_revenue(invoices)
    })


# ================= PRODUCT =================

@login_required
def product_list(request):
    return render(request, 'core/product_list.html', {
        'products': Product.objects.filter(user=request.user)
    })


@login_required
def add_product(request):
    if request.method == "POST":

        # Collect form data
        data = [
            request.POST.get('name'),
            request.POST.get('price'),
            request.POST.get('quantity')
        ]

        # ✅ Validate using custom library
        if not required_fields(data):
            return render(request, 'core/add_product.html', {'error': 'All fields required'})

        # Save product
        Product.objects.create(user=request.user, name=data[0], price=data[1], quantity=data[2])
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
    return render(request, 'core/customer_list.html', {
        'customers': Customer.objects.filter(user=request.user)
    })


@login_required
def add_customer(request):
    if request.method == "POST":

        data = [
            request.POST.get('name'),
            request.POST.get('email'),
            request.POST.get('phone')
        ]

        # ✅ Validation via custom library
        if not required_fields(data):
            return render(request, 'core/add_customer.html', {'error': 'All fields required'})

        Customer.objects.create(
            user=request.user,
            name=data[0],
            email=data[1],
            phone=data[2],
            address=request.POST.get('address')
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

        # Handle new or existing customer
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

        # Create invoice
        invoice = Invoice.objects.create(user=request.user, customer=customer, total_amount=0)

        items = []
        product_ids = request.POST.getlist('product')
        quantities = request.POST.getlist('quantity')

        # Loop through products
        for i in range(len(product_ids)):
            product = Product.objects.get(id=product_ids[i])
            qty = int(quantities[i])

            # Prepare for calculation
            items.append({'price': product.price, 'quantity': qty})

            InvoiceItem.objects.create(
                invoice=invoice,
                product=product,
                quantity=qty,
                price=product.price
            )

        # ✅ Calculate total using custom library
        invoice.total_amount = calculate_total(items)
        invoice.save()

        return redirect(f'/invoice/view/{invoice.id}/')

    return render(request, 'core/create_invoice.html', {
        'products': products,
        'customers': customers
    })


@login_required
def invoice_view(request, id):
    invoice = Invoice.objects.get(id=id, user=request.user)
    items = InvoiceItem.objects.filter(invoice=invoice)

    # Calculate subtotal per item
    for item in items:
        item.subtotal = item.price * item.quantity

    return render(request, 'core/invoice_view.html', {
        'invoice': invoice,
        'items': items
    })


@login_required
def invoice_list(request):
    invoices = Invoice.objects.filter(user=request.user)

    # Apply filters
    if request.GET.get('start_date'):
        invoices = invoices.filter(created_at__date__gte=parse_date(request.GET.get('start_date')))

    if request.GET.get('end_date'):
        invoices = invoices.filter(created_at__date__lte=parse_date(request.GET.get('end_date')))

    if request.GET.get('customer'):
        invoices = invoices.filter(customer__name__icontains=request.GET.get('customer'))

    invoices = invoices.order_by('-id')

    return render(request, 'core/invoice_list.html', {
        'invoices': invoices,
        'total_revenue': get_total_revenue(invoices),  # custom lib
        'total_invoices': invoices.count()
    })


# ================= EXPORT =================

@login_required
def export_invoices(request):

    # Create CSV response
    response = HttpResponse(content_type='text/csv')
    response['Content-Disposition'] = 'attachment; filename="invoices.csv"'

    writer = csv.writer(response)
    writer.writerow(['ID', 'Customer', 'Total (€)', 'Date'])

    for i in Invoice.objects.filter(user=request.user):
        writer.writerow([i.id, i.customer.name, i.total_amount, i.created_at])

    return response


@login_required
def export_backup(request):

    response = HttpResponse(content_type='text/csv')
    response['Content-Disposition'] = 'attachment; filename="backup.csv"'

    writer = csv.writer(response)

    # Export products
    writer.writerow(['PRODUCTS'])
    for p in Product.objects.filter(user=request.user):
        writer.writerow([p.name, p.price, p.quantity])

    # Export customers
    writer.writerow([])
    writer.writerow(['CUSTOMERS'])
    for c in Customer.objects.filter(user=request.user):
        writer.writerow([c.name, c.email, c.phone, c.address])

    return response


# ================= IMPORT =================

@login_required
def import_backup(request):
    if request.method == "POST":

        file = request.FILES.get('file')

        decoded = TextIOWrapper(file.file, encoding='utf-8')
        reader = csv.reader(decoded)

        mode = None

        for row in reader:
            if not row:
                continue

            # Detect section
            if "PRODUCTS" in row[0].upper():
                mode = "product"
                continue

            if "CUSTOMERS" in row[0].upper():
                mode = "customer"
                continue

            try:
                if mode == "product":
                    Product.objects.create(
                        user=request.user,
                        name=row[0],
                        price=float(row[1]),
                        quantity=int(row[2])
                    )

                elif mode == "customer":
                    Customer.objects.create(
                        user=request.user,
                        name=row[0],
                        email=row[1],
                        phone=row[2],
                        address=row[3]
                    )
            except:
                pass  # Skip invalid rows

        return redirect('/dashboard/')

    return render(request, 'core/import_backup.html')


# ================= BILLING REPORT =================

@login_required
def billing_report(request):

    invoices = Invoice.objects.filter(user=request.user)

    # Calculate total revenue using aggregation
    total_revenue = invoices.aggregate(
        Sum('total_amount')
    )['total_amount__sum'] or 0

    return render(request, 'core/billing_report.html', {
        'total_revenue': total_revenue,
        'total_invoices': invoices.count(),
        'invoices': invoices
    })
from django.urls import path
from . import views

urlpatterns = [
    path("", views.index),
    path("about/", views.about),
    path("contact/", views.contact),
    path("login/", views.login_view),
    path("register/", views.register),
    path("forgot-password/", views.forgot_password),
    path("dashboard/", views.dashboard),  # next step
    path("products/", views.product_list),
    path("products/add/", views.add_product),
    path("products/update/<int:id>/", views.update_product),
    path("products/delete/<int:id>/", views.delete_product),
    path("customers/", views.customer_list),
    path("customers/add/", views.add_customer),
    path("customers/update/<int:id>/", views.update_customer),
    path("customers/delete/<int:id>/", views.delete_customer),
    path("invoice/create/", views.create_invoice),
    path("invoice/view/<int:id>/", views.invoice_view),
    path("invoice/list/", views.invoice_list),
    path("report/", views.billing_report),
    path("invoice/export/", views.export_invoices),
    path("backup/export/", views.export_backup),
    path("backup/import/", views.import_backup),
    path("backup/export/", views.export_backup),
    path("logout/", views.logout_view),
]

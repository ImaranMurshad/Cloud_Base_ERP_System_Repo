from django.db.models import Sum

def get_total_revenue(invoices):
    return invoices.aggregate(
        Sum('total_amount')
    )['total_amount__sum'] or 0


def get_total_count(queryset):
    return queryset.count()
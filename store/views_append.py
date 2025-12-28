
@login_required
def sales_list(request):
    """
    عرض قائمة الفواتير مع الفلترة.
    """
    sales = Sale.objects.all().order_by("-created_at")
    
    # Filters
    start_date = request.GET.get("start")
    end_date = request.GET.get("end")
    payment_method = request.GET.get("payment_method")
    invoice_id = request.GET.get("invoice_id")

    if start_date:
        sales = sales.filter(created_at__date__gte=start_date)
    if end_date:
        sales = sales.filter(created_at__date__lte=end_date)
    if payment_method:
        sales = sales.filter(payment_method=payment_method)
    if invoice_id:
        sales = sales.filter(id=invoice_id)

    # Pagination could be added here if needed

    context = {
        "sales": sales,
        "start_date": start_date,
        "end_date": end_date,
        "payment_method": payment_method,
        "invoice_id": invoice_id,
        "payment_methods": Sale.PAYMENT_METHOD_CHOICES,
    }
    return render(request, "store/sales_list.html", context)

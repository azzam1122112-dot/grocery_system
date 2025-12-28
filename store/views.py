from decimal import Decimal
from django.db.models.functions import Coalesce
from django.db.models import Sum, Q, F, Max, OuterRef, Subquery, DecimalField
from django.shortcuts import get_object_or_404
from django.db import transaction
from django.db.models import Sum, Count
from django.utils.dateparse import parse_date

from django.contrib import messages
from django.contrib.auth import login, logout
from django.contrib.auth.decorators import login_required, user_passes_test
from django.shortcuts import redirect, render
from django.contrib.auth.models import User

from .forms import AddItemForm, CheckoutForm, DebtPaymentForm, ProductForm, EmployeeForm
from .models import Debtor, Product, Sale, SaleItem, DebtPayment

def is_manager(user):
    return user.is_superuser

def _get_cart(request):
    """
    جلب السلة الحالية من الـ session.
    """
    return request.session.get("pos_cart", [])


def _save_cart(request, cart):
    """
    حفظ السلة في الـ session.
    """
    request.session["pos_cart"] = cart
    request.session.modified = True


def _cart_total(cart):
    """
    حساب إجمالي السلة الحالية.
    """
    total = Decimal("0.00")
    for item in cart:
        total = total + Decimal(str(item.get("line_total", "0")))
    return total


@login_required
def pos_view(request):
    """
    شاشة المبيعات:
    - سلة تحتوي عدّة منتجات.
    - نموذج لإضافة صنف، ونموذج لإنهاء الفاتورة.
    """
    cart = _get_cart(request)
    last_sale = None

    if request.method == "POST":
        action = request.POST.get("action")

        # إضافة منتج إلى السلة
        if action == "add_item":
            add_item_form = AddItemForm(request.POST, cart_items=cart)
            checkout_form = CheckoutForm()
            if add_item_form.is_valid():
                product = add_item_form.cleaned_data["product"]
                quantity = add_item_form.cleaned_data["quantity"]
                line_total = add_item_form.cleaned_data["line_total"]

                # إن كان المنتج موجودًا بالسلة نحدّث الكمية
                updated = False
                new_cart = []
                for item in cart:
                    if item.get("product_id") == product.id:
                        new_qty = int(item["quantity"]) + quantity
                        new_line_total = Decimal(str(item["unit_price"])) * Decimal(
                            new_qty
                        )
                        new_cart.append(
                            {
                                "product_id": product.id,
                                "code": product.code,
                                "name": product.name,
                                "quantity": new_qty,
                                "unit_price": str(product.sale_price),
                                "line_total": str(new_line_total),
                            }
                        )
                        updated = True
                    else:
                        new_cart.append(item)

                if not updated:
                    new_cart.append(
                        {
                            "product_id": product.id,
                            "code": product.code,
                            "name": product.name,
                            "quantity": quantity,
                            "unit_price": str(product.sale_price),
                            "line_total": str(line_total),
                        }
                    )

                cart = new_cart
                _save_cart(request, cart)
                messages.success(request, "تم إضافة المنتج إلى السلة.")
                # Clear the add item form fields after successful addition
                add_item_form = AddItemForm(cart_items=cart) # Re-initialize the form
            else:
                messages.error(request, "يرجى تصحيح الأخطاء في نموذج إضافة المنتج.")

        # حذف منتج من السلة
        elif action == "remove_item":
            index_str = request.POST.get("index")
            if index_str is not None:
                try:
                    index = int(index_str)
                    if 0 <= index < len(cart):
                        cart.pop(index)
                        _save_cart(request, cart)
                        messages.success(request, "تم حذف المنتج من السلة.")
                except ValueError:
                    messages.error(request, "تعذر حذف المنتج من السلة.")
            add_item_form = AddItemForm(cart_items=cart)
            checkout_form = CheckoutForm()

        # إنهاء الفاتورة (تسجيل عملية البيع)
        elif action == "checkout":
            checkout_form = CheckoutForm(request.POST)
            add_item_form = AddItemForm(cart_items=cart)

            if not cart:
                messages.error(request, "السلة فارغة، لا يمكن تسجيل عملية البيع.")
            elif checkout_form.is_valid():
                payment_method = checkout_form.cleaned_data["payment_method"]
                debtor_name = checkout_form.cleaned_data["debtor_name"]
                debtor = None
                if payment_method == Sale.PAYMENT_DEBT:
                    debtor, _ = Debtor.objects.get_or_create(name=debtor_name)

                try:
                    with transaction.atomic():
                        total_amount = _cart_total(cart)

                        sale = Sale.objects.create(
                            payment_method=payment_method,
                            debtor=debtor,
                            total_amount=total_amount,
                            created_by=request.user,
                        )

                        # التحقق من المخزون من جديد وإنشاء الأصناف
                        for item in cart:
                            product = Product.objects.select_for_update().get(
                                id=item["product_id"]
                            )
                            quantity = int(item["quantity"])
                            if quantity > product.current_stock:
                                raise ValueError(
                                    f"الكمية المطلوبة من {product.name} أكبر من المتوفر."
                                )

                            unit_price = Decimal(str(item["unit_price"]))
                            line_total = Decimal(str(item["line_total"]))

                            SaleItem.objects.create(
                                sale=sale,
                                product=product,
                                quantity=quantity,
                                unit_price=unit_price,
                                line_total=line_total,
                            )

                            product.current_stock = product.current_stock - quantity
                            product.save(update_fields=["current_stock"])

                    last_sale = sale
                    cart = []
                    _save_cart(request, cart)
                    messages.success(request, "تم تسجيل عملية البيع بنجاح.")

                    # إعادة توجيه لتفادي إعادة الإرسال عند التحديث
                    return redirect("store:pos")

                except Exception:
                    messages.error(
                        request,
                        "حدث خطأ غير متوقع أثناء حفظ عملية البيع. يرجى المحاولة مرة أخرى.",
                    )
            else:
                messages.error(request, "يرجى تصحيح الأخطاء في نموذج الدفع.")

        # أي action غير معروف
        else:
            add_item_form = AddItemForm(cart_items=cart)
            checkout_form = CheckoutForm()

    else:
        add_item_form = AddItemForm(cart_items=cart)
        checkout_form = CheckoutForm()

    context = {
        "add_item_form": add_item_form,
        "checkout_form": checkout_form,
        "cart": cart,
        "cart_total": _cart_total(cart),
        "last_sale": last_sale,
    }
    return render(request, "store/pos.html", context)


@login_required
@user_passes_test(is_manager)
def dashboard_view(request):
    """
    لوحة تحكم لصاحب البقالة:
    - إجمالي المبيعات + تقسيم حسب طريقة الدفع.
    - أفضل وأسوأ المنتجات مبيعاً.
    - حالة المخزون (قريب من النفاد / منتهي).
    """

    # قراءة فلاتر التاريخ من GET
    start_date_str = request.GET.get("start")
    end_date_str = request.GET.get("end")

    sales_qs = Sale.objects.all()

    if start_date_str:
        start_date = parse_date(start_date_str)
        if start_date:
            sales_qs = sales_qs.filter(created_at__date__gte=start_date)

    if end_date_str:
        end_date = parse_date(end_date_str)
        if end_date:
            sales_qs = sales_qs.filter(created_at__date__lte=end_date)

    # إجمالي المبيعات وتقسيمها حسب طريقة الدفع (استعلامات منفصلة لتفادي FieldError)
    totals = {}

    agg_all = sales_qs.aggregate(total=Sum("total_amount"))
    totals["total_amount"] = agg_all["total"] or 0

    agg_cash = sales_qs.filter(payment_method=Sale.PAYMENT_CASH).aggregate(
        total=Sum("total_amount")
    )
    totals["total_cash"] = agg_cash["total"] or 0

    agg_transfer = sales_qs.filter(payment_method=Sale.PAYMENT_TRANSFER).aggregate(
        total=Sum("total_amount")
    )
    totals["total_transfer"] = agg_transfer["total"] or 0

    agg_debt = sales_qs.filter(payment_method=Sale.PAYMENT_DEBT).aggregate(
        total=Sum("total_amount")
    )
    totals["total_debt"] = agg_debt["total"] or 0

    # حساب المبالغ التي لم تحصل (الديون المتبقية الكلية)
    # نحسبها بشكل كلي (Global) لأنها تعبر عن رصيد حالي وليس فترة محددة
    _global_debt = Sale.objects.filter(payment_method=Sale.PAYMENT_DEBT).aggregate(t=Sum("total_amount"))["t"] or 0
    _global_paid = DebtPayment.objects.aggregate(t=Sum("amount"))["t"] or 0
    totals["total_outstanding"] = _global_debt - _global_paid

    # حساب الأرباح (إجمالي المبيعات - إجمالي التكلفة)
    # التكلفة = سعر التكلفة للمنتج * الكمية المباعة
    profit_agg = SaleItem.objects.filter(sale__in=sales_qs).aggregate(
        total_cost=Sum(F("product__cost_price") * F("quantity"), output_field=DecimalField())
    )
    total_cost = profit_agg["total_cost"] or 0
    totals["total_profit"] = totals["total_amount"] - total_cost

    # المنتجات الأعلى مبيعاً (حسب الكمية)
    top_products = (
        SaleItem.objects.filter(sale__in=sales_qs)
        .values("product__id", "product__name", "product__code")
        .annotate(
            total_qty=Sum("quantity"),
            total_amount=Sum("line_total"),
        )
        .order_by("-total_qty")[:10]
    )

    # المنتجات الأقل مبيعاً: نعتمد على نفس الفترة، لكن ترتيب تصاعدي
    low_products = (
        SaleItem.objects.filter(sale__in=sales_qs)
        .values("product__id", "product__name", "product__code")
        .annotate(
            total_qty=Sum("quantity"),
            total_amount=Sum("line_total"),
        )
        .order_by("total_qty")[:10]
    )

    # حالة المخزون
    low_stock_products = Product.objects.filter(
        is_active=True, current_stock__gt=0, current_stock__lt=5
    ).order_by("current_stock", "name")

    out_of_stock_products = Product.objects.filter(
        is_active=True, current_stock=0
    ).order_by("name")

    context = {
        "totals": totals,
        "top_products": top_products,
        "low_products": low_products,
        "low_stock_products": low_stock_products,
        "out_of_stock_products": out_of_stock_products,
        "start_date": start_date_str or "",
        "end_date": end_date_str or "",
    }
    return render(request, "store/dashboard.html", context)





@login_required
@user_passes_test(is_manager)
def debtor_detail(request, debtor_id):
    """
    تفاصيل ديون مديون معيّن (قائمة الفواتير التي بالدين).
    """
    # نتأكد أن المديون موجود وله فواتير دين
    debt_sales = Sale.objects.filter(
        payment_method=Sale.PAYMENT_DEBT,
        debtor_id=debtor_id,
    ).select_related("debtor", "created_by").order_by("-created_at")

    debtor = None
    total_debt = 0
    invoices_count = 0

    if debt_sales:
        debtor = debt_sales[0].debtor
        agg = debt_sales.aggregate(total=Sum("total_amount"), count=Count("id"))
        total_debt = agg["total"] or 0
        invoices_count = agg["count"] or 0

    context = {
        "debtor": debtor,
        "debt_sales": debt_sales,
        "total_debt": total_debt,
        "invoices_count": invoices_count,
    }
    return render(request, "store/debtor_detail.html", context)


@login_required
@user_passes_test(is_manager)
def debt_pay_view(request, debtor_id):
    """
    شاشة سداد دين لمَدين معيّن، مع اختيار طريقة السداد.
    """

    debtor = get_object_or_404(Debtor, id=debtor_id)

    # حساب إجمالي الدين والمدفوع والمتبقي (استعلامات منفصلة لتجنب التكرار في الـ Join)
    total_debt = Sale.objects.filter(debtor=debtor, payment_method=Sale.PAYMENT_DEBT).aggregate(t=Sum("total_amount"))["t"] or Decimal("0.00")
    total_paid = DebtPayment.objects.filter(debtor=debtor).aggregate(t=Sum("amount"))["t"] or Decimal("0.00")
    remaining = total_debt - total_paid

    totals = {
        "total_debt": total_debt,
        "total_paid": total_paid,
        "remaining": remaining
    }

    if request.method == "POST":
        form = DebtPaymentForm(request.POST, debtor=debtor, max_amount=remaining)
        if form.is_valid():
            payment = form.save(commit=False)
            payment.debtor = debtor
            payment.created_by = request.user
            payment.save()
            messages.success(request, "تم تسجيل سداد الدين بنجاح.")
            return redirect("store:debts_list")
        else:
            messages.error(request, "يرجى تصحيح الأخطاء في نموذج السداد.")
    else:
        form = DebtPaymentForm(debtor=debtor, max_amount=remaining)

    payments = debtor.payments.all().order_by("-paid_at")[:20]

    context = {
        "debtor": debtor,
        "totals": totals,
        "remaining": remaining,
        "form": form,
        "payments": payments,
    }
    return render(request, "store/debt_pay.html", context)


@login_required
@user_passes_test(is_manager)
def debts_list(request):
    """
    قائمة المدينين مع إجمالي الديون والمبالغ المسددة والمتبقي.
    """
    # 1. حساب الإجماليات العامة (للكروت العلوية)
    # إجمالي الديون (مبيعات آجلة)
    total_debt_all = Sale.objects.filter(payment_method=Sale.PAYMENT_DEBT).aggregate(t=Sum("total_amount"))["t"] or 0
    # إجمالي المسدد
    total_paid_all = DebtPayment.objects.aggregate(t=Sum("amount"))["t"] or 0
    # المتبقي الكلي
    total_outstanding = total_debt_all - total_paid_all

    # 2. قائمة المديونين
    # استخدام Subquery لتجنب مشكلة التكرار عند عمل Join مع جدولين (Sales, Payments)
    sales_subquery = Sale.objects.filter(
        debtor=OuterRef("pk"),
        payment_method=Sale.PAYMENT_DEBT
    ).values("debtor").annotate(
        total=Sum("total_amount")
    ).values("total")

    payments_subquery = DebtPayment.objects.filter(
        debtor=OuterRef("pk")
    ).values("debtor").annotate(
        total=Sum("amount")
    ).values("total")

    debtors = (
        Debtor.objects
        .annotate(
            total_debt=Coalesce(Subquery(sales_subquery), Decimal("0.00")),
            total_paid=Coalesce(Subquery(payments_subquery), Decimal("0.00")),
            last_invoice_id=Max("sales__id", filter=Q(sales__payment_method=Sale.PAYMENT_DEBT)),
        )
        .annotate(remaining=F("total_debt") - F("total_paid"))
        .filter(total_debt__gt=0)
        .order_by("-remaining", "name")
    )

    context = {
        "debtors": debtors,
        "total_outstanding": total_outstanding,
        "total_paid": total_paid_all,
    }
    return render(request, "store/debts_list.html", context)


@login_required
@user_passes_test(is_manager)
def inventory_list(request):
    """
    عرض قائمة المنتجات وإدارة المخزون (تعديل الكميات).
    """
    query = request.GET.get("q", "")
    products = Product.objects.filter(is_active=True)

    if query:
        products = products.filter(
            Q(name__icontains=query) | Q(code__icontains=query)
        )
    
    products = products.order_by("name")

    context = {
        "products": products,
        "query": query
    }
    return render(request, "store/inventory_list.html", context)


@login_required
@user_passes_test(is_manager)
def inventory_update(request, product_id):
    """
    تحديث مخزون منتج معين (إضافة أو إنقاص).
    """
    product = get_object_or_404(Product, id=product_id)
    
    if request.method == "POST":
        action = request.POST.get("action") # 'add' or 'subtract'
        try:
            quantity = int(request.POST.get("quantity", 0))
        except ValueError:
            quantity = 0
            
        if quantity > 0:
            if action == "add":
                product.current_stock += quantity
                messages.success(request, f"تم إضافة {quantity} إلى مخزون {product.name}")
            elif action == "subtract":
                if product.current_stock >= quantity:
                    product.current_stock -= quantity
                    messages.success(request, f"تم خصم {quantity} من مخزون {product.name}")
                else:
                    messages.error(request, f"الكمية المراد خصمها أكبر من المتوفر ({product.current_stock})")
            
            product.save()
        else:
             messages.warning(request, "الكمية يجب أن تكون أكبر من صفر")

    return redirect("store:inventory_list")


@login_required
@user_passes_test(is_manager)
def product_create(request):
    if request.method == 'POST':
        form = ProductForm(request.POST)
        if form.is_valid():
            form.save()
            messages.success(request, "تم إضافة المنتج بنجاح")
            return redirect('store:inventory_list')
    else:
        form = ProductForm()
    return render(request, 'store/product_form.html', {'form': form, 'title': 'إضافة منتج جديد'})


@login_required
@user_passes_test(is_manager)
def product_update(request, pk):
    product = get_object_or_404(Product, pk=pk)
    if request.method == 'POST':
        form = ProductForm(request.POST, instance=product)
        if form.is_valid():
            form.save()
            messages.success(request, "تم تحديث المنتج بنجاح")
            return redirect('store:inventory_list')
    else:
        form = ProductForm(instance=product)
    return render(request, 'store/product_form.html', {'form': form, 'title': 'تعديل منتج', 'product': product})


@login_required
@user_passes_test(is_manager)
def product_delete(request, pk):
    product = get_object_or_404(Product, pk=pk)
    if request.method == 'POST':
        product.delete()
        messages.success(request, "تم حذف المنتج بنجاح")
        return redirect('store:inventory_list')
    return render(request, 'store/product_confirm_delete.html', {'product': product})


@login_required
@user_passes_test(is_manager)
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

    context = {
        "sales": sales,
        "start_date": start_date,
        "end_date": end_date,
        "payment_method": payment_method,
        "invoice_id": invoice_id,
        "payment_methods": Sale.PAYMENT_METHOD_CHOICES,
    }
    return render(request, "store/sales_list.html", context)


@login_required
@user_passes_test(is_manager)
def sale_detail(request, sale_id):
    """
    عرض تفاصيل فاتورة معينة.
    """
    sale = get_object_or_404(Sale, id=sale_id)
    return render(request, "store/sale_detail.html", {"sale": sale})


@login_required
@user_passes_test(is_manager)
def employee_list(request):
    employees = User.objects.all().order_by('username')
    return render(request, 'store/employee_list.html', {'employees': employees})


@login_required
@user_passes_test(is_manager)
def employee_create(request):
    if request.method == 'POST':
        form = EmployeeForm(request.POST)
        if form.is_valid():
            form.save()
            messages.success(request, "تم إضافة الموظف بنجاح.")
            return redirect('store:employee_list')
    else:
        form = EmployeeForm()
    return render(request, 'store/employee_form.html', {'form': form, 'title': 'إضافة موظف جديد'})


@login_required
@user_passes_test(is_manager)
def employee_update(request, pk):
    employee = get_object_or_404(User, pk=pk)
    if request.method == 'POST':
        form = EmployeeForm(request.POST, instance=employee)
        if form.is_valid():
            form.save()
            messages.success(request, "تم تحديث بيانات الموظف بنجاح.")
            return redirect('store:employee_list')
    else:
        form = EmployeeForm(instance=employee)
    return render(request, 'store/employee_form.html', {'form': form, 'title': 'تعديل بيانات الموظف'})


@login_required
@user_passes_test(is_manager)
def employee_delete(request, pk):
    employee = get_object_or_404(User, pk=pk)
    if request.method == 'POST':
        if employee == request.user:
            messages.error(request, "لا يمكنك حذف حسابك الحالي.")
        else:
            employee.delete()
            messages.success(request, "تم حذف الموظف بنجاح.")
        return redirect('store:employee_list')
    return render(request, 'store/employee_confirm_delete.html', {'employee': employee})


def login_view(request):
    if request.user.is_authenticated:
        return redirect('store:pos')
        
    if request.method == 'POST':
        username = request.POST.get('username')
        if username:
            try:
                user = User.objects.get(username=username, is_active=True)
                # Log in without password check
                login(request, user, backend='django.contrib.auth.backends.ModelBackend')
                messages.success(request, f"مرحباً {user.first_name or user.username}")
                return redirect('store:pos')
            except User.DoesNotExist:
                messages.error(request, "اسم المستخدم غير صحيح")
        else:
            messages.error(request, "الرجاء إدخال اسم المستخدم")
            
    return render(request, 'store/login.html')


def logout_view(request):
    logout(request)
    return redirect('store:login')



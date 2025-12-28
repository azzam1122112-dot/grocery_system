from decimal import Decimal

from django.db import models
from django.contrib.auth import get_user_model

User = get_user_model()


class Product(models.Model):
    code = models.CharField(
        max_length=50,
        unique=True,
        verbose_name="كود المنتج",
        help_text="يمكن أن يكون باركود أو كود يدوي",
    )
    name = models.CharField(
        max_length=200,
        verbose_name="اسم المنتج",
    )
    cost_price = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        verbose_name="سعر التكلفة",
    )
    sale_price = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        verbose_name="سعر البيع",
    )
    current_stock = models.IntegerField(
        default=0,
        verbose_name="الكمية في المخزون",
    )
    is_active = models.BooleanField(
        default=True,
        verbose_name="منتج نشط",
    )
    created_at = models.DateTimeField(
        auto_now_add=True,
        verbose_name="تاريخ الإضافة",
    )
    updated_at = models.DateTimeField(
        auto_now=True,
        verbose_name="آخر تحديث",
    )

    class Meta:
        verbose_name = "منتج"
        verbose_name_plural = "المنتجات"
        ordering = ["name"]

    def __str__(self) -> str:
        return f"{self.name} ({self.code})"


class Debtor(models.Model):
    name = models.CharField(
        max_length=200,
        verbose_name="اسم المديون",
    )
    phone = models.CharField(
        max_length=20,
        blank=True,
        null=True,
        verbose_name="رقم الجوال",
    )
    notes = models.TextField(
        blank=True,
        null=True,
        verbose_name="ملاحظات",
    )

    class Meta:
        verbose_name = "مديون"
        verbose_name_plural = "المديونون"

    def __str__(self) -> str:
        return self.name


class Sale(models.Model):
    PAYMENT_CASH = "cash"
    PAYMENT_TRANSFER = "transfer"
    PAYMENT_DEBT = "debt"

    PAYMENT_METHOD_CHOICES = [
        (PAYMENT_CASH, "كاش"),
        (PAYMENT_TRANSFER, "حوالة"),
        (PAYMENT_DEBT, "دين"),
    ]

    created_at = models.DateTimeField(
        auto_now_add=True,
        verbose_name="تاريخ ووقت البيع",
    )
    payment_method = models.CharField(
        max_length=20,
        choices=PAYMENT_METHOD_CHOICES,
        verbose_name="طريقة الدفع",
    )
    debtor = models.ForeignKey(
        Debtor,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="sales",
        verbose_name="المديون",
        help_text="مطلوب فقط في حالة الدفع بالدين",
    )
    total_amount = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        verbose_name="إجمالي الفاتورة",
    )
    created_by = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        verbose_name="المستخدم الذي سجّل العملية",
    )

    class Meta:
        verbose_name = "فاتورة بيع"
        verbose_name_plural = "فواتير المبيعات"
        ordering = ["-created_at"]

    def __str__(self) -> str:
        return f"فاتورة #{self.id} - {self.created_at.strftime('%Y-%m-%d %H:%M')}"

    @property
    def is_debt(self) -> bool:
        return self.payment_method == self.PAYMENT_DEBT


class SaleItem(models.Model):
    sale = models.ForeignKey(
        Sale,
        on_delete=models.CASCADE,
        related_name="items",
        verbose_name="الفاتورة",
    )
    product = models.ForeignKey(
        Product,
        on_delete=models.PROTECT,
        verbose_name="المنتج",
    )
    quantity = models.PositiveIntegerField(
        verbose_name="الكمية",
    )
    unit_price = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        verbose_name="سعر الوحدة وقت البيع",
    )
    line_total = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        verbose_name="إجمالي السطر",
    )

    class Meta:
        verbose_name = "صنف في الفاتورة"
        verbose_name_plural = "أصناف الفواتير"

    def __str__(self) -> str:
        return f"{self.product.name} × {self.quantity}"


class DebtPayment(models.Model):
    """تسجيل دفعات سداد الديون لكل مديون."""

    PAYMENT_CASH = "cash"
    PAYMENT_TRANSFER = "transfer"

    PAYMENT_METHOD_CHOICES = [
        (PAYMENT_CASH, "كاش"),
        (PAYMENT_TRANSFER, "حوالة"),
    ]

    debtor = models.ForeignKey(
        Debtor,
        on_delete=models.CASCADE,
        related_name="payments",
        verbose_name="المديون",
    )
    amount = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        verbose_name="المبلغ المسدّد",
    )
    payment_method = models.CharField(
        max_length=20,
        choices=PAYMENT_METHOD_CHOICES,
        verbose_name="طريقة السداد",
    )
    note = models.CharField(
        max_length=255,
        blank=True,
        verbose_name="ملاحظة",
    )
    paid_at = models.DateTimeField(
        auto_now_add=True,
        verbose_name="تاريخ ووقت السداد",
    )
    created_by = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        verbose_name="المستخدم الذي سجّل السداد",
    )

    class Meta:
        verbose_name = "سداد دين"
        verbose_name_plural = "سدادات الديون"
        ordering = ["-paid_at"]

    def __str__(self) -> str:
        return f"{self.debtor} - {self.amount} ({self.get_payment_method_display()})"

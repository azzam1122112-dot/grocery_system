from decimal import Decimal

from django import forms
from django.core.exceptions import ValidationError
from django.contrib.auth.models import User

from .models import Product, Sale, Debtor, DebtPayment


class EmployeeForm(forms.ModelForm):
    password = forms.CharField(
        label="كلمة المرور",
        required=False,
        widget=forms.PasswordInput(attrs={"class": "form-control"}),
        help_text="اتركها فارغة إذا كنت لا تريد تغييرها (مطلوبة عند الإضافة)"
    )
    role = forms.ChoiceField(
        label="الصلاحية",
        choices=[('cashier', 'كاشير'), ('manager', 'مدير')],
        widget=forms.Select(attrs={"class": "form-control"})
    )

    class Meta:
        model = User
        fields = ['username', 'first_name', 'last_name', 'email', 'is_active']
        widgets = {
            'username': forms.TextInput(attrs={'class': 'form-control'}),
            'first_name': forms.TextInput(attrs={'class': 'form-control'}),
            'last_name': forms.TextInput(attrs={'class': 'form-control'}),
            'email': forms.EmailInput(attrs={'class': 'form-control'}),
            'is_active': forms.CheckboxInput(attrs={'class': 'form-check-input'}),
        }
        labels = {
            'username': 'اسم المستخدم',
            'first_name': 'الاسم الأول',
            'last_name': 'الاسم الأخير',
            'email': 'البريد الإلكتروني',
            'is_active': 'حساب نشط',
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        if self.instance.pk:
            self.fields['role'].initial = 'manager' if self.instance.is_superuser else 'cashier'
        else:
            self.fields['password'].required = True

    def save(self, commit=True):
        user = super().save(commit=False)
        password = self.cleaned_data.get('password')
        if password:
            user.set_password(password)
        
        role = self.cleaned_data.get('role')
        if role == 'manager':
            user.is_superuser = True
            user.is_staff = True
        else:
            user.is_superuser = False
            user.is_staff = False
            
        if commit:
            user.save()
        return user


class AddItemForm(forms.Form):
    code = forms.CharField(
        label="كود المنتج",
        max_length=50,
        widget=forms.TextInput(
            attrs={
                "class": "input",
                "placeholder": "أدخل كود المنتج",
                "autofocus": "autofocus",
            }
        ),
    )
    quantity = forms.IntegerField(
        label="الكمية",
        min_value=1,
        initial=1,
        widget=forms.NumberInput(
            attrs={
                "class": "input",
            }
        ),
    )

    def __init__(self, *args, **kwargs):
        # نستقبل السلة الحالية لحساب المتوفر
        self.cart_items = kwargs.pop("cart_items", [])
        super().__init__(*args, **kwargs)
        self.fields["code"].widget.attrs["dir"] = "ltr"
        self.fields["quantity"].widget.attrs["dir"] = "ltr"
        self.order_fields(["code", "quantity"])

    def clean_code(self):
        code = self.cleaned_data.get("code", "").strip()
        if not code:
            raise ValidationError("يرجى إدخال كود المنتج.")
        try:
            product = Product.objects.get(code=code, is_active=True)
        except Product.DoesNotExist:
            raise ValidationError("المنتج غير موجود أو غير نشط.")
        self._product = product
        return code

    def clean(self):
        cleaned_data = super().clean()
        code = cleaned_data.get("code")
        quantity = cleaned_data.get("quantity")

        if not code or not quantity:
            return cleaned_data

        product = getattr(self, "_product", None)
        if product is None:
            raise ValidationError("تعذر جلب بيانات المنتج، يرجى المحاولة مرة أخرى.")

        # الكمية الموجودة مسبقاً لنفس المنتج في السلة
        already_in_cart = 0
        for item in self.cart_items:
            if item.get("product_id") == product.id:
                already_in_cart = already_in_cart + int(item.get("quantity", 0))

        available = product.current_stock - already_in_cart
        if quantity > available:
            raise ValidationError(
                f"الكمية المطلوبة ({quantity}) أكبر من المتوفر في المخزون ({available})."
            )

        total = Decimal(quantity) * product.sale_price
        cleaned_data["product"] = product
        cleaned_data["line_total"] = total
        return cleaned_data


class CheckoutForm(forms.Form):
    payment_method = forms.ChoiceField(
        label="طريقة الدفع",
        choices=Sale.PAYMENT_METHOD_CHOICES,
        widget=forms.RadioSelect,
    )
    debtor_name = forms.CharField(
        label="اسم المديون",
        required=False,
        widget=forms.TextInput(
            attrs={
                "class": "input",
                "placeholder": "أدخل اسم المديون عند اختيار (دين)",
            }
        ),
    )

    def clean(self):
        cleaned_data = super().clean()
        payment_method = cleaned_data.get("payment_method")
        debtor_name = cleaned_data.get("debtor_name", "").strip()

        if payment_method == Sale.PAYMENT_DEBT and not debtor_name:
            raise ValidationError("عند اختيار طريقة الدفع (دين) يجب إدخال اسم المديون.")

        cleaned_data["debtor_name"] = debtor_name
        return cleaned_data



from decimal import Decimal
from django import forms

from .models import DebtPayment, Debtor


class DebtPaymentForm(forms.ModelForm):
    class Meta:
        model = DebtPayment
        fields = ["amount", "payment_method", "note"]
        labels = {
            "amount": "مبلغ السداد",
            "payment_method": "طريقة السداد",
            "note": "ملاحظة (اختياري)",
        }
        widgets = {
            "amount": forms.NumberInput(attrs={"class": "input", "step": "0.01", "min": "0"}),
            "payment_method": forms.RadioSelect(),
            "note": forms.TextInput(attrs={"class": "input"}),
        }

    def __init__(self, *args, **kwargs):
        self.debtor = kwargs.pop("debtor", None)
        self.max_amount = kwargs.pop("max_amount", None)
        super().__init__(*args, **kwargs)

    def clean_amount(self):
        amount = self.cleaned_data.get("amount") or Decimal("0")
        if amount <= 0:
            raise forms.ValidationError("مبلغ السداد يجب أن يكون أكبر من صفر.")
        if self.max_amount is not None and amount > self.max_amount:
            raise forms.ValidationError("مبلغ السداد أكبر من المبلغ المتبقي على المديون.")
        return amount


class ProductForm(forms.ModelForm):
    class Meta:
        model = Product
        fields = ['code', 'name', 'cost_price', 'sale_price', 'current_stock']
        labels = {
            'code': 'كود المنتج',
            'name': 'اسم المنتج',
            'cost_price': 'سعر التكلفة',
            'sale_price': 'سعر البيع',
            'current_stock': 'الكمية الحالية',
        }
        widgets = {
            'code': forms.TextInput(attrs={'class': 'form-control'}),
            'name': forms.TextInput(attrs={'class': 'form-control'}),
            'cost_price': forms.NumberInput(attrs={'class': 'form-control', 'step': '0.01'}),
            'sale_price': forms.NumberInput(attrs={'class': 'form-control', 'step': '0.01'}),
            'current_stock': forms.NumberInput(attrs={'class': 'form-control'}),
        }

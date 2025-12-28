
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

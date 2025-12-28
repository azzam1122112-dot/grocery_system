from django.contrib import admin
from .models import Product, Debtor, Sale, SaleItem


@admin.register(Product)
class ProductAdmin(admin.ModelAdmin):
    list_display = ("name", "code", "sale_price", "current_stock", "is_active")
    list_filter = ("is_active",)
    search_fields = ("name", "code")
    ordering = ("name",)


@admin.register(Debtor)
class DebtorAdmin(admin.ModelAdmin):
    list_display = ("name", "phone")
    search_fields = ("name", "phone")


class SaleItemInline(admin.TabularInline):
    model = SaleItem
    extra = 0
    readonly_fields = ("line_total",)


@admin.register(Sale)
class SaleAdmin(admin.ModelAdmin):
    list_display = ("id", "created_at", "payment_method", "total_amount", "debtor", "created_by")
    list_filter = ("payment_method", "created_at")
    date_hierarchy = "created_at"
    inlines = [SaleItemInline]
    search_fields = ("id", "debtor__name", "created_by__username")

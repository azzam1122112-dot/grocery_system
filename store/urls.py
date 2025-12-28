from django.urls import path

from . import views

app_name = "store"

urlpatterns = [
    path("", views.pos_view, name="home"),
    path("pos/", views.pos_view, name="pos"),
    path("dashboard/", views.dashboard_view, name="dashboard"),
    path("sales/", views.sales_list, name="sales_list"),
    path("sales/<int:sale_id>/", views.sale_detail, name="sale_detail"),
    path("debts/", views.debts_list, name="debts_list"),
    path("debts/<int:debtor_id>/", views.debtor_detail, name="debtor_detail"),
    path("debts/<int:debtor_id>/pay/", views.debt_pay_view, name="debt_pay"),
    path("inventory/", views.inventory_list, name="inventory_list"),
    path("inventory/add/", views.product_create, name="product_create"),
    path("inventory/<int:pk>/edit/", views.product_update, name="product_update"),
    path("inventory/<int:pk>/delete/", views.product_delete, name="product_delete"),
    path("inventory/<int:product_id>/update/", views.inventory_update, name="inventory_update"),
    
    # Employee Management
    path("employees/", views.employee_list, name="employee_list"),
    path("employees/add/", views.employee_create, name="employee_create"),
    path("employees/<int:pk>/edit/", views.employee_update, name="employee_update"),
    path("employees/<int:pk>/delete/", views.employee_delete, name="employee_delete"),
    
    # Authentication
    path("login/", views.login_view, name="login"),
    path("logout/", views.logout_view, name="logout"),
]

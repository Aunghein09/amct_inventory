from django.urls import path

from . import views

app_name = "inventory"

urlpatterns = [
    path("", views.dashboard, name="dashboard"),

    path("moves/", views.stock_move_list, name="stock_move_list"),
    path("moves/receive/", views.stock_receive_create, name="stock_receive_create"),
    path("moves/sale/", views.stock_sale_create, name="stock_sale_create"),
    path("moves/adjust/", views.stock_adjust_create, name="stock_adjust_create"),
]

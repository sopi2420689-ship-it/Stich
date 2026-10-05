from django.urls import path
from . import views


app_name = "tailors"


urlpatterns = [

    # ========================================================
    # DASHBOARD
    # ========================================================

    path(
        "dashboard/",
        views.dashboard,
        name="dashboard"
    ),


    # ========================================================
    # ORDERS
    # ========================================================

    path(
        "orders/",
        views.orders,
        name="orders"
    ),

    path(
        "orders/<int:pk>/",
        views.order_detail,
        name="order_detail"
    ),


    # ========================================================
    # PRODUCTION
    # ========================================================

    path(
        "production/",
        views.production,
        name="production"
    ),


    # ========================================================
    # DESIGNS
    # ========================================================

    path(
        "designs/",
        views.designs,
        name="designs"
    ),

    path(
        "designs/add/",
        views.add_design,
        name="add_design"
    ),

    path(
        "designs/<int:pk>/update/",
        views.update_design,
        name="update_design"
    ),

    path(
        "designs/<int:pk>/delete/",
        views.delete_design,
        name="delete_design"
    ),


    # ========================================================
    # PROFILE
    # ========================================================

    path(
        "profile/",
        views.profile,
        name="profile"
    ),


    # ========================================================
    # CHAT
    # ========================================================

    path(
        "chat/",
        views.chat,
        name="chat"
    ),
]

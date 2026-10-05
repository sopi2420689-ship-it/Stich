# from django.urls import path
# from django.http import HttpResponse

# app_name = "riders"


# from django.shortcuts import render
# from django.contrib.auth.decorators import login_required


# @login_required(login_url="/login/")
# def dashboard(request):
#     return render(request, "riders/dashboard.html")


# urlpatterns = [
#     path("dashboard/", dashboard, name="dashboard"),
# ]


from django.urls import path
from . import views

app_name = "riders"


urlpatterns = [
    # Dashboard
    path(
        "",
        views.dashboard,
        name="dashboard",
    ),
    # Jobs
    path(
        "jobs/",
        views.jobs,
        name="jobs",
    ),
    path(
        "jobs/<int:job_id>/",
        views.job_detail,
        name="job_detail",
    ),
    # Pickup
    path(
        "jobs/<int:job_id>/pickup/",
        views.pickup_action,
        name="pickup_action",
    ),
    # Delivery
    path(
        "jobs/<int:job_id>/delivery/start/",
        views.start_delivery,
        name="start_delivery",
    ),
    path(
        "jobs/<int:job_id>/delivery/verify/",
        views.verify_delivery,
        name="verify_delivery",
    ),
    # History
    path(
        "history/",
        views.history,
        name="history",
    ),
    # Rider Profile
    path(
        "profile/",
        views.profile,
        name="profile",
    ),
    path(
        "messages/",
        views.messages_view,
        name="messages",
    ),
]

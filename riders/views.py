# from django.shortcuts import render
# from django.contrib.auth.decorators import login_required


# @login_required(login_url="/login/")
# def dashboard(request):
#     return render(request, "riders/dashboard.html")


from functools import wraps
from .models import RiderJob, RiderProfile, Message
from django.contrib import messages
from django.contrib.auth import update_session_auth_hash
from django.contrib.auth.decorators import login_required
from django.db.models import Q
from django.shortcuts import (
    get_object_or_404,
    redirect,
    render,
)
from django.utils import timezone

from core.models import UserProfile
from .models import RiderJob, RiderProfile

# =========================================================
# RIDER ACCESS CHECK
# =========================================================


def rider_required(view_func):

    @wraps(view_func)
    @login_required(login_url="/login/")
    def wrapper(request, *args, **kwargs):

        try:
            profile = request.user.profile
        except UserProfile.DoesNotExist:
            messages.error(
                request,
                "Your account profile could not be found.",
            )
            return redirect("core:home")

        if profile.role != "Rider":
            messages.error(
                request,
                "You do not have permission to access the Rider portal.",
            )
            return redirect("core:home")

        if profile.approval_status != "Approved":
            messages.warning(
                request,
                "Your Rider account is awaiting administrator approval.",
            )
            return redirect("core:home")

        return view_func(request, *args, **kwargs)

    return wrapper


# =========================================================
# HELPER
# =========================================================


def get_rider_profile(user):

    rider_profile, created = RiderProfile.objects.get_or_create(user=user)

    return rider_profile


# =========================================================
# DASHBOARD
# =========================================================


@rider_required
def dashboard(request):

    rider_profile = get_rider_profile(request.user)

    jobs = (
        RiderJob.objects.filter(rider=request.user)
        .select_related(
            "order",
            "order__user",
        )
        .order_by("-created_at")
    )

    active_jobs = jobs.filter(completed_at__isnull=True)

    pending_pickups = active_jobs.filter(pickup_required=True).exclude(
        pickup_status="fabric_delivered"
    )

    pending_deliveries = active_jobs.filter(delivery_required=True).exclude(
        delivery_status="delivered"
    )

    completed_deliveries = jobs.filter(delivery_status="delivered")

    context = {
        "rider_profile": rider_profile,
        "jobs": active_jobs[:6],
        "assigned_count": active_jobs.count(),
        "pending_pickups_count": pending_pickups.count(),
        "pending_deliveries_count": pending_deliveries.count(),
        "completed_count": completed_deliveries.count(),
    }

    return render(
        request,
        "riders/dashboard.html",
        context,
    )


# =========================================================
# JOBS
# =========================================================


@rider_required
def jobs(request):

    query = request.GET.get(
        "q",
        "",
    ).strip()

    job_type = request.GET.get(
        "type",
        "all",
    )

    jobs_list = (
        RiderJob.objects.filter(
            rider=request.user,
            completed_at__isnull=True,
        )
        .select_related(
            "order",
            "order__user",
        )
        .order_by("-created_at")
    )

    # -----------------------------------------
    # Search
    # -----------------------------------------

    if query:

        jobs_list = jobs_list.filter(
            Q(order__order_id__icontains=query)
            | Q(order__customer_name__icontains=query)
            | Q(order__product_name__icontains=query)
            | Q(order__shop_name__icontains=query)
        )

    # -----------------------------------------
    # Type filter
    # -----------------------------------------

    if job_type == "pickup":

        jobs_list = jobs_list.filter(pickup_required=True).exclude(
            pickup_status="fabric_delivered"
        )

    elif job_type == "delivery":

        jobs_list = jobs_list.filter(delivery_required=True).exclude(
            delivery_status="delivered"
        )

    context = {
        "jobs": jobs_list,
        "query": query,
        "selected_type": job_type,
    }

    return render(
        request,
        "riders/jobs.html",
        context,
    )


# =========================================================
# JOB DETAIL
# =========================================================


@rider_required
def job_detail(request, job_id):

    job = get_object_or_404(
        RiderJob.objects.select_related(
            "order",
            "order__user",
        ),
        id=job_id,
        rider=request.user,
    )

    return render(
        request,
        "riders/job_detail.html",
        {
            "job": job,
        },
    )


# =========================================================
# PICKUP ACTION
# =========================================================


@rider_required
def pickup_action(request, job_id):

    if request.method != "POST":

        return redirect(
            "riders:job_detail",
            job_id=job_id,
        )

    job = get_object_or_404(
        RiderJob,
        id=job_id,
        rider=request.user,
    )

    if not job.pickup_required:

        messages.error(
            request,
            "This order does not require a fabric pickup.",
        )

        return redirect(
            "riders:job_detail",
            job_id=job.id,
        )

    # -----------------------------------------
    # Pickup Requested -> Rider Assigned
    # -----------------------------------------

    if job.pickup_status == "pickup_requested":

        job.pickup_status = "rider_assigned"

        messages.success(
            request,
            "Pickup accepted.",
        )

    # -----------------------------------------
    # Rider Assigned -> Fabric Collected
    # -----------------------------------------

    elif job.pickup_status == "rider_assigned":

        job.pickup_status = "fabric_collected"

        messages.success(
            request,
            "Fabric marked as collected.",
        )

    # -----------------------------------------
    # Fabric Collected -> Delivered to Tailor
    # -----------------------------------------

    elif job.pickup_status == "fabric_collected":

        job.pickup_status = "fabric_delivered"

        # Update the existing customer Order field too
        if hasattr(job.order, "pickup_status"):

            job.order.pickup_status = "Fabric Delivered to Tailor Shop"

            job.order.save(
                update_fields=[
                    "pickup_status",
                ]
            )

        messages.success(
            request,
            "Fabric delivered to the tailor shop.",
        )

    else:

        messages.info(
            request,
            "Pickup has already been completed.",
        )

    job.save()

    return redirect(
        "riders:job_detail",
        job_id=job.id,
    )


# =========================================================
# START DELIVERY
# =========================================================


@rider_required
def start_delivery(request, job_id):

    if request.method != "POST":

        return redirect(
            "riders:job_detail",
            job_id=job_id,
        )

    job = get_object_or_404(
        RiderJob,
        id=job_id,
        rider=request.user,
    )

    if not job.delivery_required:

        messages.error(
            request,
            "This job does not require delivery.",
        )

        return redirect(
            "riders:job_detail",
            job_id=job.id,
        )

    if job.pickup_required:

        if job.pickup_status != "fabric_delivered":

            messages.error(
                request,
                "Complete the fabric pickup before starting delivery.",
            )

            return redirect(
                "riders:job_detail",
                job_id=job.id,
            )

    if job.delivery_status == "waiting":

        messages.warning(
            request,
            "The tailor has not marked this order ready yet.",
        )

    elif job.delivery_status == "ready":

        job.delivery_status = "out_for_delivery"

        job.save(
            update_fields=[
                "delivery_status",
            ]
        )

        messages.success(
            request,
            "Delivery started.",
        )

    return redirect(
        "riders:job_detail",
        job_id=job.id,
    )


# =========================================================
# VERIFY DELIVERY OTP
# =========================================================


@rider_required
def verify_delivery(request, job_id):

    if request.method != "POST":

        return redirect(
            "riders:job_detail",
            job_id=job_id,
        )

    job = get_object_or_404(
        RiderJob.objects.select_related("order"),
        id=job_id,
        rider=request.user,
    )

    otp = request.POST.get(
        "otp",
        "",
    ).strip()

    if job.delivery_status != "out_for_delivery":

        messages.error(
            request,
            "Start the delivery before verifying the OTP.",
        )

        return redirect(
            "riders:job_detail",
            job_id=job.id,
        )

    # -----------------------------------------
    # Use the REAL Order delivery PIN
    # -----------------------------------------

    expected_otp = str(job.order.delivery_pin or "").strip()

    if not expected_otp:

        messages.error(
            request,
            "This order does not have a delivery OTP.",
        )

        return redirect(
            "riders:job_detail",
            job_id=job.id,
        )

    if otp != expected_otp:

        messages.error(
            request,
            "Incorrect delivery OTP.",
        )

        return redirect(
            "riders:job_detail",
            job_id=job.id,
        )

    # -----------------------------------------
    # Complete delivery
    # -----------------------------------------

    job.delivery_status = "delivered"

    job.completed_at = timezone.now()

    job.save(
        update_fields=[
            "delivery_status",
            "completed_at",
        ]
    )

    # Update Customer Order
    job.order.status = "Delivered"

    job.order.save(
        update_fields=[
            "status",
        ]
    )

    messages.success(
        request,
        "OTP verified. Delivery completed successfully.",
    )

    return redirect(
        "riders:job_detail",
        job_id=job.id,
    )


# =========================================================
# HISTORY
# =========================================================


@rider_required
def history(request):

    jobs_list = (
        RiderJob.objects.filter(
            rider=request.user,
        )
        .filter(
            Q(completed_at__isnull=False)
            | Q(delivery_status="delivered")
            | Q(pickup_status="fabric_delivered")
        )
        .select_related(
            "order",
            "order__user",
        )
        .order_by("-completed_at", "-created_at")
    )

    return render(
        request,
        "riders/history.html",
        {
            "jobs": jobs_list,
        },
    )


# =========================================================
# PROFILE
# =========================================================


@rider_required
def profile(request):

    user = request.user

    user_profile = user.profile

    rider_profile = get_rider_profile(user)

    if request.method == "POST":

        action = request.POST.get("action")

        # =====================================
        # VEHICLE / RIDER PROFILE
        # =====================================

        if action == "profile":

            user_profile.phone = request.POST.get(
                "phone",
                user_profile.phone or "",
            ).strip()

            user_profile.vehicle_type = request.POST.get(
                "vehicle_type",
                user_profile.vehicle_type or "",
            ).strip()

            rider_profile.license_plate = request.POST.get(
                "license_plate",
                "",
            ).strip()

            rider_profile.vehicle_model = request.POST.get(
                "vehicle_model",
                "",
            ).strip()

            rider_profile.service_area = request.POST.get(
                "service_area",
                "",
            ).strip()

            user_profile.save()

            rider_profile.save()

            messages.success(
                request,
                "Rider profile updated successfully.",
            )

            return redirect("riders:profile")

        # =====================================
        # ONLINE STATUS
        # =====================================

        elif action == "availability":

            rider_profile.is_online = not rider_profile.is_online

            rider_profile.save(
                update_fields=[
                    "is_online",
                ]
            )

            return redirect("riders:profile")

        # =====================================
        # PASSWORD
        # =====================================

        elif action == "password":

            current_password = request.POST.get(
                "current_password",
                "",
            )

            new_password = request.POST.get(
                "new_password",
                "",
            )

            confirm_password = request.POST.get(
                "confirm_password",
                "",
            )

            if not user.check_password(current_password):

                messages.error(
                    request,
                    "Current password is incorrect.",
                )

                return redirect("riders:profile")

            if not new_password:

                messages.error(
                    request,
                    "Enter a new password.",
                )

                return redirect("riders:profile")

            if new_password != confirm_password:

                messages.error(
                    request,
                    "New passwords do not match.",
                )

                return redirect("riders:profile")

            user.set_password(new_password)

            user.save()

            update_session_auth_hash(
                request,
                user,
            )

            messages.success(
                request,
                "Password updated successfully.",
            )

            return redirect("riders:profile")

    context = {
        "user_profile": user_profile,
        "rider_profile": rider_profile,
    }

    return render(
        request,
        "riders/profile.html",
        context,
    )


from .models import Message


@rider_required
def messages_view(request):

    conversation = request.GET.get(
        "conversation",
        "Rahim Ahmed",
    )

    messages_list = Message.objects.filter(conversation=conversation).order_by(
        "created_at"
    )

    if request.method == "POST":

        text = request.POST.get(
            "message",
            "",
        ).strip()

        if text:

            Message.objects.create(
                conversation=conversation,
                sender="rider",
                text=text,
            )

            return redirect(f"/rider/messages/?conversation={conversation}")

    return render(
        request,
        "riders/messages.html",
        {
            "conversation": conversation,
            "messages_list": messages_list,
        },
    )

from datetime import datetime, time
from decimal import Decimal, InvalidOperation
from functools import wraps

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.contrib.auth.models import User
from django.db.models import Q
from django.http import JsonResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone

from core.models import Design, UserProfile
from customers.models import Order
from riders.models import RiderJob
from .models import TailorShop, ChatMessage

# ============================================================
# TAILOR ACCESS
# ============================================================


def tailor_required(view_func):

    @wraps(view_func)
    @login_required(login_url="/login/")
    def wrapper(request, *args, **kwargs):

        try:
            profile = request.user.profile

        except UserProfile.DoesNotExist:

            messages.error(request, "Your account profile could not be found.")

            return redirect("core:home")

        if profile.role != "Tailor":

            messages.error(
                request, "You do not have permission to access the Tailor portal."
            )

            return redirect("core:home")

        if profile.approval_status != "Approved":

            messages.warning(
                request, "Your Tailor account is awaiting administrator approval."
            )

            return redirect("core:home")

        return view_func(request, *args, **kwargs)

    return wrapper


# ============================================================
# TAILOR SHOP
# ============================================================


def get_tailor_shop(user):

    shop, created = TailorShop.objects.get_or_create(
        owner=user,
        defaults={"name": f"{user.get_full_name() or user.username}'s Tailor Shop"},
    )

    return shop


# ============================================================
# APPROVED RIDERS
# ============================================================


def get_approved_riders():

    return User.objects.filter(
        is_active=True,
        profile__role="Rider",
        profile__approval_status="Approved",
    ).order_by("first_name", "last_name", "username")


# ============================================================
# DASHBOARD
# ============================================================


@tailor_required
def dashboard(request):

    shop = get_tailor_shop(request.user)

    orders = Order.objects.filter(shop_name=shop.name).order_by("-date", "-id")

    pending_orders = orders.filter(status="Pending")

    production_orders = orders.filter(
        status__in=[
            "Accepted",
            "In Production",
        ]
    )

    ready_orders = orders.filter(status="Ready")

    delivered_orders = orders.filter(status="Delivered")

    cancelled_orders = orders.filter(status="Cancelled")

    revenue = sum((order.total_price or Decimal("0")) for order in delivered_orders)

    unread_messages = ChatMessage.objects.filter(
        receiver=request.user,
        is_read=False,
    ).count()

    context = {
        "orders": orders,
        # Your dashboard template expects new_orders
        "new_orders": pending_orders[:5],
        "pending_orders": pending_orders,
        "production_orders": production_orders,
        "ready_orders": ready_orders,
        "delivered_orders": delivered_orders,
        "cancelled_orders": cancelled_orders,
        "pending_count": pending_orders.count(),
        "production_count": production_orders.count(),
        "ready_count": ready_orders.count(),
        "delivered_count": delivered_orders.count(),
        "cancelled_count": cancelled_orders.count(),
        "revenue": revenue,
        "unread_messages": unread_messages,
        "approval_status": request.user.profile.approval_status,
        "shop": shop,
        "shop_name": shop.name,
        "profile": shop,
    }

    return render(
        request,
        "tailors/dashboard.html",
        context,
    )


# ============================================================
# ORDERS
# ============================================================


@tailor_required
def orders(request):

    shop = get_tailor_shop(request.user)

    # --------------------------------------------------------
    # ACCEPT / REJECT
    # --------------------------------------------------------

    if request.method == "POST":

        order_pk = request.POST.get("order_id")
        action = request.POST.get("action")

        order = get_object_or_404(
            Order,
            pk=order_pk,
            shop_name=shop.name,
        )

        if order.status != "Pending":

            messages.warning(request, "This order has already been processed.")

            return redirect("tailors:orders")

        if action == "accept":

            order.status = "Accepted"
            order.save(update_fields=["status"])

            messages.success(request, f"Order {order.order_id} accepted.")

        elif action == "reject":

            order.status = "Cancelled"
            order.save(update_fields=["status"])

            messages.success(request, f"Order {order.order_id} rejected.")

        return redirect("tailors:orders")

    # --------------------------------------------------------
    # LIST
    # --------------------------------------------------------

    orders_queryset = Order.objects.filter(shop_name=shop.name).order_by("-date", "-id")

    search = request.GET.get(
        "search",
        "",
    ).strip()

    if search:

        orders_queryset = orders_queryset.filter(
            Q(order_id__icontains=search)
            | Q(customer_name__icontains=search)
            | Q(product_name__icontains=search)
        )

    selected_status = request.GET.get(
        "status",
        "All",
    )

    valid_statuses = dict(Order.STATUS_CHOICES)

    if selected_status != "All" and selected_status in valid_statuses:

        orders_queryset = orders_queryset.filter(status=selected_status)

    else:
        selected_status = "All"

    context = {
        "orders": orders_queryset,
        "search": search,
        "selected_status": selected_status,
        "status_choices": Order.STATUS_CHOICES,
        "shop": shop,
        "shop_name": shop.name,
        "profile": shop,
    }

    return render(
        request,
        "tailors/orders.html",
        context,
    )


# ============================================================
# ORDER DETAIL
# ============================================================


@tailor_required
def order_detail(request, pk):

    shop = get_tailor_shop(request.user)

    order = get_object_or_404(
        Order,
        pk=pk,
        shop_name=shop.name,
    )

    rider_job = RiderJob.objects.filter(order=order).select_related("rider").first()

    approved_riders = get_approved_riders()

    # --------------------------------------------------------
    # POST ACTIONS
    # --------------------------------------------------------

    if request.method == "POST":

        action = request.POST.get("action")

        # ====================================================
        # ACCEPT ORDER
        # ====================================================

        if action == "accept":

            if order.status == "Pending":

                order.status = "Accepted"

                order.save(update_fields=["status"])

                messages.success(request, "Order accepted successfully.")

        # ====================================================
        # REJECT ORDER
        # ====================================================

        elif action == "reject":

            if order.status == "Pending":

                order.status = "Cancelled"

                order.save(update_fields=["status"])

                messages.success(request, "Order rejected.")

        # ====================================================
        # ASSIGN RIDER
        # ====================================================

        elif action == "assign_rider":

            rider_id = request.POST.get("rider_id")

            rider = get_object_or_404(
                User,
                id=rider_id,
                is_active=True,
                profile__role="Rider",
                profile__approval_status="Approved",
            )

            pickup_required = order.fabric_source == "own"

            delivery_status = "ready" if order.status == "Ready" else "waiting"

            rider_job, created = RiderJob.objects.update_or_create(
                order=order,
                defaults={
                    "rider": rider,
                    "pickup_required": pickup_required,
                    "delivery_required": True,
                    "pickup_status": (
                        "rider_assigned" if pickup_required else "pickup_requested"
                    ),
                    "delivery_status": delivery_status,
                },
            )

            order.rider_name = rider.get_full_name() or rider.email or rider.username

            update_fields = ["rider_name"]

            if pickup_required:

                order.pickup_status = "Rider Assigned"

                update_fields.append("pickup_status")

            order.save(update_fields=update_fields)

            messages.success(
                request, f"Rider {order.rider_name} assigned successfully."
            )

        # ====================================================
        # START PRODUCTION
        # ====================================================

        elif action == "start_production":

            if order.status != "Accepted":

                messages.error(request, "Only accepted orders can enter production.")

            elif (
                order.fabric_source == "own"
                and order.pickup_status != "Fabric Delivered to Tailor Shop"
            ):

                messages.error(
                    request,
                    "The customer's fabric must be delivered "
                    "to the tailor shop before production can start.",
                )

            else:

                order.status = "In Production"

                order.save(update_fields=["status"])

                messages.success(request, "Production started.")

        # ====================================================
        # MARK READY
        # ====================================================

        elif action == "ready":

            if order.status != "In Production":

                messages.error(
                    request, "Only an order in production can be marked ready."
                )

            else:

                order.status = "Ready"

                order.save(update_fields=["status"])

                # If a rider has already been assigned,
                # tell the Rider portal the order is ready.
                rider_job = RiderJob.objects.filter(order=order).first()

                if rider_job:

                    rider_job.delivery_status = "ready"

                    rider_job.save(update_fields=["delivery_status"])

                messages.success(request, "Order is ready for delivery.")

        else:

            messages.error(request, "Invalid order action.")

        return redirect(
            "tailors:order_detail",
            pk=order.pk,
        )

    context = {
        "order": order,
        "rider_job": rider_job,
        "approved_riders": approved_riders,
        "shop": shop,
        "shop_name": shop.name,
        "profile": shop,
        "status_choices": Order.STATUS_CHOICES,
    }

    return render(
        request,
        "tailors/order_detail.html",
        context,
    )


# ============================================================
# PRODUCTION
# ============================================================


@tailor_required
def production(request):

    shop = get_tailor_shop(request.user)

    # --------------------------------------------------------
    # HANDLE PRODUCTION ACTIONS
    # --------------------------------------------------------

    if request.method == "POST":

        order_pk = request.POST.get("order_id")
        action = request.POST.get("action")

        order = get_object_or_404(
            Order,
            pk=order_pk,
            shop_name=shop.name,
        )

        # ----------------------------------------------------
        # ACCEPT
        # ----------------------------------------------------

        if action == "accept":

            if order.status == "Pending":

                order.status = "Accepted"

                order.save(update_fields=["status"])

        # ----------------------------------------------------
        # REJECT
        # ----------------------------------------------------

        elif action == "reject":

            if order.status == "Pending":

                order.status = "Cancelled"

                order.save(update_fields=["status"])

        # ----------------------------------------------------
        # START PRODUCTION
        # ----------------------------------------------------

        elif action == "start_production":

            if order.status != "Accepted":

                messages.error(request, "This order cannot start production.")

            elif (
                order.fabric_source == "own"
                and order.pickup_status != "Fabric Delivered to Tailor Shop"
            ):

                messages.error(request, "Fabric pickup must be completed first.")

            else:

                order.status = "In Production"

                order.save(update_fields=["status"])

        # ----------------------------------------------------
        # READY
        # ----------------------------------------------------

        elif action == "ready":

            if order.status == "In Production":

                order.status = "Ready"

                order.save(update_fields=["status"])

                rider_job = RiderJob.objects.filter(order=order).first()

                if rider_job:

                    rider_job.delivery_status = "ready"

                    rider_job.save(update_fields=["delivery_status"])

        return redirect("tailors:production")

    # --------------------------------------------------------
    # PRODUCTION DATA
    # --------------------------------------------------------

    shop_orders = Order.objects.filter(shop_name=shop.name).order_by("-date", "-id")

    pending_orders = shop_orders.filter(status="Pending")

    accepted_orders = shop_orders.filter(status="Accepted")

    production_orders = shop_orders.filter(status="In Production")

    ready_orders = shop_orders.filter(status="Ready")

    context = {
        "pending_orders": pending_orders,
        "accepted_orders": accepted_orders,
        "production_orders": production_orders,
        "ready_orders": ready_orders,
        "shop": shop,
        "shop_name": shop.name,
        "profile": shop,
    }

    return render(
        request,
        "tailors/production.html",
        context,
    )


# ============================================================
# DESIGNS
# ============================================================


@tailor_required
def designs(request):

    shop = get_tailor_shop(request.user)

    designs_queryset = Design.objects.filter(shop=shop).order_by("-created_at")

    search = request.GET.get(
        "search",
        "",
    ).strip()

    if search:

        designs_queryset = designs_queryset.filter(
            Q(title__icontains=search) | Q(description__icontains=search)
        )

    context = {
        "designs": designs_queryset,
        "search": search,
        "shop": shop,
        "shop_name": shop.name,
        "profile": shop,
    }

    return render(
        request,
        "tailors/designs.html",
        context,
    )


# ============================================================
# ADD DESIGN
# ============================================================


@tailor_required
def add_design(request):

    shop = get_tailor_shop(request.user)

    if request.method == "POST":

        title = request.POST.get(
            "title",
            "",
        ).strip()

        description = request.POST.get(
            "description",
            "",
        ).strip()

        price_value = request.POST.get(
            "price",
            "",
        ).strip()

        image = request.FILES.get("image")

        if not title:

            return render(
                request,
                "tailors/add_design.html",
                {
                    "shop": shop,
                    "shop_name": shop.name,
                    "profile": shop,
                    "error": "Design title is required.",
                },
            )

        try:

            price = Decimal(price_value)

            if price < 0:
                raise InvalidOperation

        except (
            InvalidOperation,
            ValueError,
            TypeError,
        ):

            return render(
                request,
                "tailors/add_design.html",
                {
                    "shop": shop,
                    "shop_name": shop.name,
                    "profile": shop,
                    "error": "Please enter a valid price.",
                },
            )

        Design.objects.create(
            shop=shop,
            title=title,
            description=description,
            price=price,
            image=image,
        )

        messages.success(request, "Design created successfully.")

        return redirect("tailors:designs")

    return render(
        request,
        "tailors/add_design.html",
        {
            "shop": shop,
            "shop_name": shop.name,
            "profile": shop,
        },
    )


# ============================================================
# UPDATE DESIGN
# ============================================================


@tailor_required
def update_design(request, pk):

    if request.method != "POST":

        return JsonResponse(
            {
                "success": False,
                "error": "Invalid request method.",
            },
            status=405,
        )

    shop = get_tailor_shop(request.user)

    # IMPORTANT:
    # Tailor can only edit THEIR OWN design.
    design = get_object_or_404(
        Design,
        pk=pk,
        shop=shop,
    )

    title = request.POST.get(
        "title",
        "",
    ).strip()

    description = request.POST.get(
        "description",
        "",
    ).strip()

    price_value = request.POST.get(
        "price",
        "",
    ).strip()

    image = request.FILES.get("image")

    if not title:

        return JsonResponse(
            {
                "success": False,
                "error": "Design name is required.",
            },
            status=400,
        )

    try:

        price = Decimal(price_value)

        if price < 0:
            raise InvalidOperation

    except (
        InvalidOperation,
        ValueError,
        TypeError,
    ):

        return JsonResponse(
            {
                "success": False,
                "error": "Please enter a valid price.",
            },
            status=400,
        )

    old_image = design.image if image else None

    design.title = title
    design.description = description
    design.price = price

    if image:
        design.image = image

    design.save()

    if image and old_image:

        try:
            old_image.delete(save=False)

        except Exception:
            pass

    return JsonResponse(
        {
            "success": True,
            "design": {
                "id": design.id,
                "title": design.title,
                "description": design.description,
                "price": str(design.price),
                "image": (design.image.url if design.image else ""),
            },
        }
    )


# ============================================================
# DELETE DESIGN
# ============================================================


@tailor_required
def delete_design(request, pk):

    if request.method != "POST":

        return JsonResponse(
            {
                "success": False,
                "error": "Invalid request method.",
            },
            status=405,
        )

    shop = get_tailor_shop(request.user)

    # Tailor can only delete THEIR OWN design.
    design = get_object_or_404(
        Design,
        pk=pk,
        shop=shop,
    )

    if design.image:

        try:
            design.image.delete(save=False)

        except Exception:
            pass

    design.delete()

    return JsonResponse(
        {
            "success": True,
            "id": pk,
        }
    )


# ============================================================
# PROFILE
# ============================================================


@tailor_required
def profile(request):

    shop = get_tailor_shop(request.user)

    user_profile = request.user.profile

    if request.method == "POST":

        first_name = request.POST.get(
            "first_name",
            "",
        ).strip()

        email = request.POST.get(
            "email",
            "",
        ).strip()

        phone = request.POST.get(
            "phone",
            "",
        ).strip()

        shop_name = request.POST.get(
            "shop_name",
            "",
        ).strip()

        bio = request.POST.get(
            "bio",
            "",
        ).strip()

        location = request.POST.get(
            "location",
            "",
        ).strip()

        specialties = request.POST.get(
            "specialties",
            "",
        ).strip()

        if shop_name:
            shop.name = shop_name

        shop.bio = bio
        shop.location = location

        if specialties:

            shop.specialties = [
                item.strip() for item in specialties.split(",") if item.strip()
            ]

        else:
            shop.specialties = []

        image = request.FILES.get("image")

        if image:
            shop.image = image

        trade_license = request.FILES.get("trade_license")

        if trade_license:
            shop.trade_license = trade_license

        request.user.first_name = first_name
        request.user.email = email

        request.user.save(
            update_fields=[
                "first_name",
                "email",
            ]
        )

        user_profile.phone = phone

        user_profile.save(
            update_fields=[
                "phone",
            ]
        )

        shop.save()

        messages.success(request, "Shop profile updated successfully.")

        return redirect("tailors:profile")

    specialties_text = ", ".join(
        shop.specialties
        if isinstance(
            shop.specialties,
            list,
        )
        else []
    )

    context = {
        "shop": shop,
        "profile": shop,
        "user_profile": user_profile,
        "shop_name": shop.name,
        "specialties_text": specialties_text,
        "approval_status": (user_profile.approval_status),
    }

    return render(
        request,
        "tailors/profile.html",
        context,
    )


# ============================================================
# CHAT
# ============================================================


@tailor_required
def chat(request):

    shop = get_tailor_shop(request.user)

    current_user = request.user

    # ========================================================
    # CUSTOMERS WHO HAVE ORDERS WITH THIS SHOP
    # ========================================================

    order_customer_ids = set(
        Order.objects.filter(shop_name=shop.name)
        .exclude(user__isnull=True)
        .values_list(
            "user_id",
            flat=True,
        )
    )

    # ========================================================
    # SEND MESSAGE
    # ========================================================

    if request.method == "POST":

        receiver_id = request.POST.get("receiver_id")

        message_text = request.POST.get(
            "message",
            "",
        ).strip()

        try:
            receiver_id = int(receiver_id)

        except (
            TypeError,
            ValueError,
        ):

            receiver_id = None

        if receiver_id and message_text and receiver_id in order_customer_ids:

            receiver = get_object_or_404(
                User,
                id=receiver_id,
            )

            if receiver != current_user:

                ChatMessage.objects.create(
                    sender=current_user,
                    receiver=receiver,
                    message=message_text,
                )

        if receiver_id:

            return redirect(f"/tailor/chat/?user={receiver_id}")

        return redirect("tailors:chat")

    # ========================================================
    # USERS FROM EXISTING MESSAGES
    # ========================================================

    sent_user_ids = set(
        ChatMessage.objects.filter(sender=current_user).values_list(
            "receiver_id",
            flat=True,
        )
    )

    received_user_ids = set(
        ChatMessage.objects.filter(receiver=current_user).values_list(
            "sender_id",
            flat=True,
        )
    )

    conversation_user_ids = sent_user_ids | received_user_ids | order_customer_ids

    conversation_user_ids.discard(current_user.id)

    # ========================================================
    # ACTIVE CUSTOMER
    # ========================================================

    selected_user_id = request.GET.get("user")

    active_customer = None

    if selected_user_id:

        try:

            selected_user_id = int(selected_user_id)

            if selected_user_id in conversation_user_ids:

                active_customer = User.objects.get(id=selected_user_id)

        except (
            ValueError,
            TypeError,
            User.DoesNotExist,
        ):

            active_customer = None

    # ========================================================
    # CONVERSATIONS
    # ========================================================

    conversations = []

    for user_id in conversation_user_ids:

        try:

            customer = User.objects.get(id=user_id)

        except User.DoesNotExist:
            continue

        last_message = (
            ChatMessage.objects.filter(
                Q(
                    sender=current_user,
                    receiver=customer,
                )
                | Q(
                    sender=customer,
                    receiver=current_user,
                )
            )
            .order_by("-created_at")
            .first()
        )

        latest_order = (
            Order.objects.filter(
                user=customer,
                shop_name=shop.name,
            )
            .order_by(
                "-date",
                "-id",
            )
            .first()
        )

        conversations.append(
            {
                "user": customer,
                "last_message": last_message,
                "order": latest_order,
            }
        )

    # ========================================================
    # SORT
    # ========================================================

    def conversation_sort_key(item):

        if item["last_message"]:

            return item["last_message"].created_at

        if item["order"]:

            order_datetime = datetime.combine(
                item["order"].date,
                time.min,
            )

            if timezone.is_naive(order_datetime):

                order_datetime = timezone.make_aware(order_datetime)

            return order_datetime

        return timezone.make_aware(datetime.min)

    conversations.sort(
        key=conversation_sort_key,
        reverse=True,
    )

    # ========================================================
    # ACTIVE CHAT
    # ========================================================

    chat_messages = []

    active_order = None

    if active_customer:

        chat_messages = ChatMessage.objects.filter(
            Q(
                sender=current_user,
                receiver=active_customer,
            )
            | Q(
                sender=active_customer,
                receiver=current_user,
            )
        ).order_by("created_at")

        ChatMessage.objects.filter(
            sender=active_customer,
            receiver=current_user,
            is_read=False,
        ).update(is_read=True)

        active_order = (
            Order.objects.filter(
                user=active_customer,
                shop_name=shop.name,
            )
            .order_by(
                "-date",
                "-id",
            )
            .first()
        )

    context = {
        "shop": shop,
        "profile": shop,
        "shop_name": shop.name,
        "conversations": conversations,
        "active_customer": active_customer,
        # Keep this name because your existing
        # chat.html expects "messages".
        "messages": chat_messages,
        "active_order": active_order,
    }

    return render(
        request,
        "tailors/chat.html",
        context,
    )

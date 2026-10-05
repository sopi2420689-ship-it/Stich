from django.db import models
from django.contrib.auth.models import User
from customers.models import Order

# =========================================================
# RIDER PROFILE
# Extra Rider-only information.
# Login/name/email/phone still come from User + UserProfile.
# =========================================================


class RiderProfile(models.Model):
    user = models.OneToOneField(
        User,
        on_delete=models.CASCADE,
        related_name="rider_profile",
    )

    license_plate = models.CharField(
        max_length=50,
        blank=True,
    )

    vehicle_model = models.CharField(
        max_length=100,
        blank=True,
    )

    service_area = models.CharField(
        max_length=255,
        blank=True,
    )

    is_online = models.BooleanField(
        default=True,
    )

    def __str__(self):
        return f"Rider: {self.user.get_full_name() or self.user.email}"


# =========================================================
# RIDER JOB
# One Rider job belongs to one StitchSync Order.
# =========================================================


class RiderJob(models.Model):

    PICKUP_STATUSES = [
        ("pickup_requested", "Pickup Requested"),
        ("rider_assigned", "Rider Assigned"),
        ("fabric_collected", "Fabric Collected"),
        ("fabric_delivered", "Delivered to Tailor Shop"),
    ]

    DELIVERY_STATUSES = [
        ("waiting", "Waiting for Tailor"),
        ("ready", "Ready"),
        ("out_for_delivery", "Out for Delivery"),
        ("delivered", "Delivered"),
    ]

    order = models.OneToOneField(
        Order,
        on_delete=models.CASCADE,
        related_name="rider_job",
    )

    rider = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="rider_jobs",
    )

    pickup_required = models.BooleanField(
        default=False,
    )

    delivery_required = models.BooleanField(
        default=True,
    )

    pickup_status = models.CharField(
        max_length=30,
        choices=PICKUP_STATUSES,
        default="pickup_requested",
    )

    delivery_status = models.CharField(
        max_length=30,
        choices=DELIVERY_STATUSES,
        default="waiting",
    )

    scheduled_time = models.DateTimeField(
        null=True,
        blank=True,
    )

    notes = models.TextField(
        blank=True,
    )

    created_at = models.DateTimeField(
        auto_now_add=True,
    )

    completed_at = models.DateTimeField(
        null=True,
        blank=True,
    )

    def __str__(self):
        return f"{self.order.order_id} - {self.rider or 'Unassigned'}"


class Message(models.Model):

    SENDER_CHOICES = [
        ("rider", "Rider"),
        ("other", "Customer/Tailor"),
    ]

    conversation = models.CharField(max_length=120)

    sender = models.CharField(max_length=20, choices=SENDER_CHOICES)

    text = models.TextField()

    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["created_at"]

    def __str__(self):
        return f"{self.conversation}: {self.text[:30]}"

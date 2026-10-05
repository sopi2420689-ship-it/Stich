from django.db import models
from django.contrib.auth.models import User


class TailorShop(models.Model):
    owner = models.OneToOneField(User, on_delete=models.CASCADE, related_name="shop")
    name = models.CharField(max_length=255)
    bio = models.TextField(blank=True, null=True)
    location = models.CharField(max_length=255, blank=True, null=True)
    rating = models.DecimalField(max_digits=3, decimal_places=1, default=5.0)

    # Store specialties natively using MySQL JSON (e.g. ["Suits", "Panjabis"])
    specialties = models.JSONField(default=list, blank=True)
    image = models.ImageField(upload_to="shops/", blank=True, null=True)
    created_at = models.DateTimeField(auto_now_add=True)
    trade_license = models.FileField(
        upload_to="private/tailor_licenses/", blank=True, null=True
    )

    def __str__(self):
        return self.name



class ChatMessage(models.Model):

    sender = models.ForeignKey(
        User,
        on_delete=models.CASCADE,
        related_name="sent_chat_messages"
    )

    receiver = models.ForeignKey(
        User,
        on_delete=models.CASCADE,
        related_name="received_chat_messages"
    )

    message = models.TextField()

    created_at = models.DateTimeField(
        auto_now_add=True
    )

    is_read = models.BooleanField(
        default=False
    )

    class Meta:
        ordering = ["created_at"]

    def __str__(self):

        return (
            f"{self.sender.username} → "
            f"{self.receiver.username}: "
            f"{self.message[:30]}"
        )
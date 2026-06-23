"""Optional reference-photo content moderation hook (stub — no paid API)."""
from dataclasses import dataclass

from django.conf import settings
from django.utils.translation import gettext_lazy as _


@dataclass
class ModerationResult:
    allowed: bool = True
    message: str = ""


def moderate_reference_photo(uploaded_file) -> ModerationResult:
    """
    Optional hook for external moderation services.
    When IMAGE_MODERATION_ENABLED is False (default), all validated uploads pass.
    """
    if not getattr(settings, "IMAGE_MODERATION_ENABLED", False):
        return ModerationResult()

    provider = getattr(settings, "IMAGE_MODERATION_PROVIDER", "").strip()
    if not provider:
        return ModerationResult(
            allowed=False,
            message=str(_("Image moderation is enabled but no provider is configured.")),
        )

    # Placeholder for future provider integration (e.g. AWS Rekognition, Sightengine).
    return ModerationResult()

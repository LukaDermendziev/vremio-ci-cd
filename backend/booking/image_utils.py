import io
import uuid

from django.core.files.base import ContentFile
from django.core.exceptions import ValidationError
from django.utils.translation import gettext_lazy as _

try:
    from PIL import Image, UnidentifiedImageError
except ImportError:  # pragma: no cover - Pillow is expected with Django ImageField
    Image = None
    UnidentifiedImageError = Exception

ALLOWED_IMAGE_FORMATS = {"JPEG", "PNG", "WEBP"}
FORMAT_TO_EXT = {"JPEG": "jpg", "PNG": "png", "WEBP": "webp"}


def booking_photo_upload_to(instance, filename):
    ext = getattr(instance, "_reference_photo_ext", None) or "jpg"
    return f"booking_photos/{uuid.uuid4().hex}.{ext}"


def validate_reference_photo(uploaded_file, max_size_mb=5):
    """
    Validate uploaded reference photo content and size.
    Returns detected PIL format string (JPEG/PNG/WEBP).
    Raises ValidationError with Macedonian user messages.
    """
    if not uploaded_file:
        return None

    max_bytes = max_size_mb * 1024 * 1024
    size = getattr(uploaded_file, "size", 0) or 0
    if size <= 0:
        raise ValidationError(
            _("Invalid image format. Allowed formats are JPG, PNG, and WEBP."),
            code="invalid_image",
        )
    if size > max_bytes:
        raise ValidationError(
            _("The image is too large. Please upload an image up to %(size)s MB.")
            % {"size": max_size_mb},
            code="image_too_large",
        )

    if Image is None:
        return "JPEG"

    try:
        uploaded_file.seek(0)
        with Image.open(uploaded_file) as img:
            img.verify()
        uploaded_file.seek(0)
        with Image.open(uploaded_file) as img:
            img.load()
            image_format = (img.format or "").upper()
    except (UnidentifiedImageError, OSError, ValueError):
        raise ValidationError(
            _("Invalid image format. Allowed formats are JPG, PNG, and WEBP."),
            code="invalid_image",
        ) from None
    finally:
        uploaded_file.seek(0)

    if image_format not in ALLOWED_IMAGE_FORMATS:
        raise ValidationError(
            _("Invalid image format. Allowed formats are JPG, PNG, and WEBP."),
            code="invalid_image",
        )

    return image_format


def prepare_reference_photo(uploaded_file, image_format):
    """
    Re-encode image without EXIF and return ContentFile with safe storage name.
    """
    if Image is None:
        uploaded_file.seek(0)
        ext = FORMAT_TO_EXT.get(image_format, "jpg")
        content = uploaded_file.read()
        return ContentFile(content, name=f"{uuid.uuid4().hex}.{ext}")

    uploaded_file.seek(0)
    with Image.open(uploaded_file) as img:
        if img.mode not in ("RGB", "RGBA"):
            img = img.convert("RGBA" if image_format == "PNG" else "RGB")

        buffer = io.BytesIO()
        save_format = image_format
        save_kwargs = {}
        if save_format == "JPEG":
            if img.mode == "RGBA":
                img = img.convert("RGB")
            save_kwargs["quality"] = 90
        elif save_format == "WEBP":
            save_kwargs["quality"] = 90

        img.save(buffer, format=save_format, **save_kwargs)
        ext = FORMAT_TO_EXT[save_format]
        return ContentFile(buffer.getvalue(), name=f"{uuid.uuid4().hex}.{ext}")

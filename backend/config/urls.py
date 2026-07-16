from django.conf import settings
from django.conf.urls.static import static
from django.contrib import admin
from django.urls import include, path
from django.views.i18n import set_language

from booking.views import favicon


urlpatterns = [
    path("favicon.ico", favicon, name="favicon"),
    path("i18n/setlang/", set_language, name="set_language"),
    path("admin/", admin.site.urls),
    path("", include("booking.urls")),
]

if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)

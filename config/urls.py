from django.conf import settings
from django.conf.urls.static import static
from django.contrib import admin
from django.urls import include, path
from drf_spectacular.views import SpectacularAPIView, SpectacularSwaggerView

urlpatterns = [
    path("admin/", admin.site.urls),
    path("api/v1/auth/", include("apps.users.auth_urls")),
    path("api/v1/", include("apps.users.urls")),
    path("api/v1/", include("apps.social.urls")),
    path("api/v1/", include("apps.rooms.urls")),
    path("api/v1/", include("apps.economy.urls")),
    path("api/v1/", include("apps.moderation.urls")),
    path("api/v1/schema/", SpectacularAPIView.as_view(), name="schema"),
    path(
        "api/v1/docs/",
        SpectacularSwaggerView.as_view(url_name="schema"),
        name="swagger-ui",
    ),
]

# Recordings are user uploads; in production a real web server or object
# store fronts these.
urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)

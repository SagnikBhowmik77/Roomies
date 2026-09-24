from django.conf import settings
from django.conf.urls.static import static
from django.http import FileResponse, Http404
from django.urls import re_path
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


def spa(request):
    """Serve the built React app for client-side routes like /rooms/3."""
    index = settings.STATIC_ROOT / "index.html"
    if not index.is_file():
        raise Http404("Frontend build not found; run collectstatic.")
    return FileResponse(index.open("rb"), content_type="text/html")


# Last resort, and never shadows the API, admin, websockets or files.
urlpatterns += [
    re_path(r"^(?!api/|admin/|ws/|static/|media/).*$", spa, name="spa"),
]

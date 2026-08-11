"""Root URL configuration.

    /                     -> redirect to the Django login page
    /accounts/...         -> server-rendered auth pages (hand-drawn theme)
    /admin/               -> Django admin
    /api/                 -> REST API consumed by the React SPA
    /api/docs/            -> Swagger UI  (schema at /api/schema/)
    /api/redoc/           -> ReDoc
"""

from django.conf import settings
from django.conf.urls.static import static
from django.contrib import admin
from django.urls import include, path
from django.views.generic import RedirectView
from drf_spectacular.views import (
    SpectacularAPIView,
    SpectacularRedocView,
    SpectacularSwaggerView,
)
from rest_framework.routers import DefaultRouter

from accounts.api_views import UserViewSet
from core.dashboard import DashboardAPIView
from core.views import health_check
from crm.views import CustomerViewSet, FollowUpViewSet
from inventory.views import ProductViewSet, StockMovementViewSet
from sales.views import SalesChallanViewSet

router = DefaultRouter()
router.register("customers", CustomerViewSet, basename="customer")
router.register("follow-ups", FollowUpViewSet, basename="followup")
router.register("products", ProductViewSet, basename="product")
router.register("stock-movements", StockMovementViewSet, basename="stockmovement")
router.register("challans", SalesChallanViewSet, basename="challan")
router.register("users", UserViewSet, basename="user")

api_patterns = [
    path("auth/", include("accounts.api_urls")),
    path("dashboard/", DashboardAPIView.as_view(), name="api-dashboard"),
    path("health/", health_check, name="api-health"),
    path("", include(router.urls)),
]

urlpatterns = [
    path("", RedirectView.as_view(pattern_name="accounts:login", permanent=False), name="home"),
    path("admin/", admin.site.urls),
    path("accounts/", include("accounts.urls")),
    path("api/", include(api_patterns)),
    # -- OpenAPI ----------------------------------------------------------
    path("api/schema/", SpectacularAPIView.as_view(), name="schema"),
    path(
        "api/docs/",
        SpectacularSwaggerView.as_view(url_name="schema"),
        name="swagger-ui",
    ),
    path("api/redoc/", SpectacularRedocView.as_view(url_name="schema"), name="redoc"),
]

if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
    urlpatterns += static(settings.STATIC_URL, document_root=settings.STATIC_ROOT)

admin.site.site_header = f"{settings.SITE_NAME} administration"
admin.site.site_title = settings.SITE_NAME
admin.site.index_title = settings.SITE_TAGLINE

from django.conf import settings


def site_context(request):
    """Expose branding / feature flags to the server-rendered auth pages."""
    return {
        "SITE_NAME": settings.SITE_NAME,
        "SITE_TAGLINE": settings.SITE_TAGLINE,
        "SIGNUP_OPEN": settings.SIGNUP_OPEN,
        "REQUIRE_EMAIL_VERIFICATION": settings.REQUIRE_EMAIL_VERIFICATION,
        "FRONTEND_URL": settings.FRONTEND_URL,
        "COMPANY_NAME": settings.COMPANY_NAME,
    }

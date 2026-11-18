from django.contrib import admin
from django.urls import include, path

from core import views as core_views
from core.ratelimit import limit_failed_logins

# The admin login shares the failed-login limiter (plan 5.2, AUTH-05).
admin.site.login = limit_failed_logins(admin.site.login)

urlpatterns = [
    path("", core_views.home, name="home"),
    path("how-it-works", core_views.how_it_works, name="how_it_works"),
    path("safety", core_views.safety, name="safety"),
    path("privacy", core_views.privacy, name="privacy"),
    path("search/stub", core_views.search_stub, name="search_stub"),
    path("safety", core_views.safety, name="safety"),
    path("healthz", core_views.healthz, name="healthz"),
    path("robots.txt", core_views.robots, name="robots"),
    path("", include("accounts.urls")),
    path("admin/", admin.site.urls),
]

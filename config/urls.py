from django.contrib import admin
from django.urls import path

from core import views as core_views

urlpatterns = [
    path("", core_views.home, name="home"),
    path("search/stub", core_views.search_stub, name="search_stub"),
    path("healthz", core_views.healthz, name="healthz"),
    path("robots.txt", core_views.robots, name="robots"),
    path("admin/", admin.site.urls),
]

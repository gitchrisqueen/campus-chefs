from django.urls import path

from . import views

urlpatterns = [
    path("kitchen/import", views.import_menu, name="menu_import"),
    path("kitchen/import/confirm", views.import_confirm, name="menu_import_confirm"),
]

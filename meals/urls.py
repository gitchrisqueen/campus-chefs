from django.urls import path

from . import views

urlpatterns = [
    path("kitchen", views.kitchen, name="kitchen"),
    path("kitchen/setup", views.kitchen_setup, name="kitchen_setup"),
    path("kitchen/bio", views.kitchen_bio, name="kitchen_bio"),
    path("kitchen/items/new", views.item_create, name="item_create"),
    path("kitchen/items/<int:pk>/edit", views.item_edit, name="item_edit"),
    path("kitchen/items/<int:pk>/archive", views.item_archive, name="item_archive"),
    path("kitchen/offerings/new", views.offering_create, name="offering_create"),
    path("kitchen/offerings/<int:pk>/edit", views.offering_edit, name="offering_edit"),
    path("kitchen/offerings/<int:pk>/delete", views.offering_delete, name="offering_delete"),
    path("cooks/<int:pk>", views.cook_page, name="cook_page"),
    path("offerings/<int:pk>", views.offering_detail, name="offering_detail"),
]

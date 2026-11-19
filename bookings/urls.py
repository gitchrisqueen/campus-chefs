from django.urls import path

from . import views

urlpatterns = [
    path("offerings/<int:pk>/book", views.book, name="book"),
    path("bookings/<int:pk>", views.booking_detail, name="booking_detail"),
    path("bookings/<int:pk>/transition", views.booking_transition, name="booking_transition"),
    path("bookings/<int:pk>/review", views.booking_review, name="booking_review"),
    path("bookings/<int:pk>/received", views.booking_received, name="booking_received"),
]

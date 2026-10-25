from django.urls import path

from . import views

urlpatterns = [
    path("stops/", views.stop_list),
    path("routes/", views.route_list),
    path("routes/<int:pk>/", views.route_detail),
    path("plan/", views.plan),
    path("safety/", views.safety),
]
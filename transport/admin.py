from django.contrib import admin
from django.contrib import admin
from .models import Stop, Route, RouteStop, SafetyAdvisory


class RouteStopInline(admin.TabularInline):
    model = RouteStop
    extra = 1


@admin.register(Route)
class RouteAdmin(admin.ModelAdmin):
    list_display = ("number", "name", "fare")
    inlines = [RouteStopInline]


admin.site.register(Stop)
admin.site.register(SafetyAdvisory)

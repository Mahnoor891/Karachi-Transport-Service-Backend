from rest_framework import serializers

from .models import Stop, Route, RouteStop, SafetyAdvisory


class StopSerializer(serializers.ModelSerializer):
    class Meta:
        model = Stop
        fields = ["id", "name", "area", "latitude", "longitude"]


class SafetyAdvisorySerializer(serializers.ModelSerializer):
    class Meta:
        model = SafetyAdvisory
        fields = ["id", "route", "stop", "level", "message"]


class RouteSerializer(serializers.ModelSerializer):
    class Meta:
        model = Route
        fields = ["id", "number", "name", "fare",
                  "first_bus_time", "last_bus_time", "frequency_minutes"]


class RouteStopSerializer(serializers.ModelSerializer):
    stop = StopSerializer()

    class Meta:
        model = RouteStop
        fields = ["sequence", "minutes_from_previous", "stop"]


class RouteDetailSerializer(RouteSerializer):
    stops = RouteStopSerializer(source="route_stops", many=True)
    advisories = SafetyAdvisorySerializer(many=True)

    class Meta(RouteSerializer.Meta):
        fields = RouteSerializer.Meta.fields + ["stops", "advisories"]
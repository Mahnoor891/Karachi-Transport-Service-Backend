from django.db import models

from django.db import models


class Stop(models.Model):
    name = models.CharField(max_length=100, unique=True)
    area = models.CharField(max_length=100, blank=True)
    latitude = models.FloatField(null=True, blank=True)
    longitude = models.FloatField(null=True, blank=True)

    def __str__(self):
        return self.name


class Route(models.Model):
    number = models.CharField(max_length=10, unique=True)
    name = models.CharField(max_length=100)
    fare = models.PositiveIntegerField(help_text="Flat fare in PKR for whole route")
    min_fare = models.PositiveIntegerField(default=30, help_text="Fare in PKR for a very short ride")
    first_bus_time = models.TimeField(null=True, blank=True)
    last_bus_time = models.TimeField(null=True, blank=True)
    frequency_minutes = models.PositiveIntegerField(default=15)

    def __str__(self):
        return f"{self.number} - {self.name}"


class RouteStop(models.Model):
    route = models.ForeignKey(Route, on_delete=models.CASCADE,
                              related_name="route_stops")
    stop = models.ForeignKey(Stop, on_delete=models.CASCADE,
                             related_name="route_stops")
    sequence = models.PositiveIntegerField()
    minutes_from_previous = models.PositiveIntegerField(default=0)

    class Meta:
        ordering = ["route", "sequence"]
        unique_together = [("route", "sequence"), ("route", "stop")]

    def __str__(self):
        return f"{self.route.number} #{self.sequence}: {self.stop.name}"


class SafetyAdvisory(models.Model):
    LEVELS = [("info", "Info"), ("caution", "Caution"), ("warning", "Warning")]

    route = models.ForeignKey(Route, null=True, blank=True,
                              on_delete=models.CASCADE,
                              related_name="advisories")
    stop = models.ForeignKey(Stop, null=True, blank=True,
                             on_delete=models.CASCADE,
                             related_name="advisories")
    level = models.CharField(max_length=10, choices=LEVELS, default="info")
    message = models.TextField()

    def __str__(self):
        return f"[{self.level}] {self.message[:40]}"

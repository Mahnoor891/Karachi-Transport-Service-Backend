from django.shortcuts import render
from django.shortcuts import get_object_or_404
from rest_framework.decorators import api_view
from rest_framework.response import Response

from transport.models import Stop, Route, SafetyAdvisory
from transport.serializers import (
    StopSerializer, RouteSerializer, RouteDetailSerializer,
    SafetyAdvisorySerializer,
)
from .services import MODES, plan_route, compare_routes


def error(message, status):
    return Response({"error": message}, status=status)


@api_view(["GET"])
def stop_list(request):
    """GET /api/stops/?q=text  - search stops by name."""
    query = request.query_params.get("q", "")
    stops = Stop.objects.filter(name__icontains=query).order_by("name")
    return Response(StopSerializer(stops, many=True).data)


@api_view(["GET"])
def route_list(request):
    """GET /api/routes/  - all routes."""
    routes = Route.objects.order_by("number")
    return Response(RouteSerializer(routes, many=True).data)


@api_view(["GET"])
def route_detail(request, pk):
    """GET /api/routes/<id>/  - one route with its ordered stops and advisories."""
    route = get_object_or_404(Route, pk=pk)
    return Response(RouteDetailSerializer(route).data)


@api_view(["GET"])
def plan(request):
    """GET /api/plan/?from=<stop id>&to=<stop id>&mode=<mode>

    mode is optional: fastest, cheapest, fewest_transfers, or all (default).
    """
    origin_id = request.query_params.get("from", "")
    destination_id = request.query_params.get("to", "")
    mode = request.query_params.get("mode", "all")

    if not origin_id.isdigit() or not destination_id.isdigit():
        return error("'from' and 'to' must be stop ids.", 400)
    if mode != "all" and mode not in MODES:
        return error("mode must be one of: all, " + ", ".join(MODES), 400)
    if origin_id == destination_id:
        return error("Origin and destination must be different.", 400)

    origin = Stop.objects.filter(pk=origin_id).first()
    destination = Stop.objects.filter(pk=destination_id).first()
    if origin is None or destination is None:
        return error("Unknown stop id.", 404)

    if mode == "all":
        options = compare_routes(origin.id, destination.id)
    else:
        option = plan_route(origin.id, destination.id, mode)
        options = [option] if option else []

    if not options:
        return error("No route found between these stops.", 404)

    return Response({
        "from": origin.name,
        "to": destination.name,
        "options": options,
    })


@api_view(["GET"])
def safety(request):
    """GET /api/safety/?route=<route number>  - advisories (all if no route given)."""
    advisories = SafetyAdvisory.objects.all()
    route_number = request.query_params.get("route")
    if route_number:
        advisories = advisories.filter(route__number=route_number)
    return Response(SafetyAdvisorySerializer(advisories, many=True).data)

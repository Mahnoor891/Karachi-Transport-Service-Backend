from django.shortcuts import get_object_or_404, render

from planner.services import compare_routes
from transport.models import Route, Stop

MODE_LABELS = {
    "fastest": "Fastest",
    "cheapest": "Cheapest",
    "fewest_transfers": "Fewest transfers",
}


def all_stops():
    return Stop.objects.order_by("name")


def find_stop(name):
    """Find a stop by its name, ignoring capital letters."""
    return Stop.objects.filter(name__iexact=name).first()


def home(request):
    return render(request, "web/home.html", {
        "routes": Route.objects.order_by("number"),
        "stops": all_stops(),
    })


def plan(request):
    from_name = request.GET.get("from", "").strip()
    to_name = request.GET.get("to", "").strip()
    searched = bool(request.GET)      # False when the page is opened without a search
    options = []
    error = ""

    if searched:
        if not from_name or not to_name:
            error = "Please choose both stops."
        elif from_name.lower() == to_name.lower():
            error = "Start and destination must be different."
        else:
            origin = find_stop(from_name)
            destination = find_stop(to_name)
            if origin is None or destination is None:
                error = "We could not find that stop. Please pick one from the list."
            else:
                options = compare_routes(origin.id, destination.id)
                if not options:
                    error = "No route found between these stops."

    for option in options:
        option["label"] = MODE_LABELS[option["mode"]]

    return render(request, "web/results.html", {
        "from_name": from_name,
        "to_name": to_name,
        "searched": searched,
        "options": options,
        "error": error,
        "stops": all_stops(),
    })


def route_list(request):
    return render(request, "web/route_list.html", {
        "routes": Route.objects.order_by("number"),
    })


def route_detail(request, pk):
    route = get_object_or_404(Route, pk=pk)
    return render(request, "web/route_detail.html", {
        "route": route,
        "route_stops": route.route_stops.select_related("stop").order_by("sequence"),
        "advisories": route.advisories.all(),
    })

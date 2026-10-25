from django.test import TestCase
from django.test import TestCase
from django.core.management import call_command

from transport.models import Stop, Route, RouteStop, SafetyAdvisory
from .services import plan_route, compare_routes


# ---------- Test data ----------

def make_route(number, fare, frequency, stops):
    route = Route.objects.create(
        number=number, name=f"Route {number}",
        fare=fare, min_fare=fare, frequency_minutes=frequency,
    )
    for position, (stop, minutes) in enumerate(stops, start=1):
        RouteStop.objects.create(
            route=route, stop=stop,
            sequence=position, minutes_from_previous=minutes,
        )
    return route


def make_test_data():
    """
    Route 1: A -5- B -5- C        fare 30, bus every 10 min
    Route 2: C -6- D              fare 40, bus every 20 min
    Route 3: A -20- E -20- D      fare 50, bus every 10 min
    Stop F is not on any route.

    A to D:  Route 1 + 2 = 31 min, fare 70, 1 transfer
             Route 3     = 45 min, fare 50, 0 transfers
    """
    stops = {name: Stop.objects.create(name=f"Stop {name}") for name in "ABCDEF"}
    make_route("1", 30, 10, [(stops["A"], 0), (stops["B"], 5), (stops["C"], 5)])
    make_route("2", 40, 20, [(stops["C"], 0), (stops["D"], 6)])
    make_route("3", 50, 10, [(stops["A"], 0), (stops["E"], 20), (stops["D"], 20)])
    return stops


def route_numbers(result):
    return [leg["route_number"] for leg in result["legs"]]


# ---------- Route-search logic ----------

class PlannerServiceTests(TestCase):
    def setUp(self):
        self.stops = make_test_data()
        self.a = self.stops["A"].id
        self.d = self.stops["D"].id

    def test_fastest_uses_transfer(self):
        result = plan_route(self.a, self.d, "fastest")
        self.assertEqual(route_numbers(result), ["1", "2"])
        self.assertEqual(result["total_minutes"], 31)
        self.assertEqual(result["total_fare"], 70)
        self.assertEqual(result["transfers"], 1)

    def test_cheapest_uses_single_route(self):
        result = plan_route(self.a, self.d, "cheapest")
        self.assertEqual(route_numbers(result), ["3"])
        self.assertEqual(result["total_minutes"], 45)
        self.assertEqual(result["total_fare"], 50)

    def test_fewest_transfers_avoids_changing_bus(self):
        result = plan_route(self.a, self.d, "fewest_transfers")
        self.assertEqual(route_numbers(result), ["3"])
        self.assertEqual(result["transfers"], 0)

    def test_reverse_direction_works(self):
        result = plan_route(self.d, self.a, "fastest")
        self.assertEqual(route_numbers(result), ["2", "1"])
        self.assertEqual(result["total_minutes"], 31)

    def test_same_origin_and_destination_returns_none(self):
        self.assertIsNone(plan_route(self.a, self.a, "fastest"))

    def test_unconnected_stop_returns_none(self):
        self.assertIsNone(plan_route(self.a, self.stops["F"].id, "fastest"))

    def test_compare_returns_three_options(self):
        options = compare_routes(self.a, self.d)
        modes = [o["mode"] for o in options]
        self.assertEqual(modes, ["fastest", "cheapest", "fewest_transfers"])

    def test_safety_advisory_is_attached(self):
        SafetyAdvisory.objects.create(
            route=Route.objects.get(number="3"),
            level="caution", message="Test advisory",
        )
        result = plan_route(self.a, self.d, "cheapest")
        messages = [a["message"] for a in result["advisories"]]
        self.assertIn("Test advisory", messages)

    def test_fare_grows_with_distance(self):
        names = ["P", "Q", "R", "S", "T"]
        stops = {n: Stop.objects.create(name=f"Stop {n}") for n in names}
        route = Route.objects.create(number="9", name="Route 9", fare=190,
                                     min_fare=30, frequency_minutes=10)
        for i, n in enumerate(names, start=1):
            RouteStop.objects.create(route=route, stop=stops[n], sequence=i,
                                     minutes_from_previous=0 if i == 1 else 5)
        fares = {
            end: plan_route(stops["P"].id, stops[end].id, "fastest")["total_fare"]
            for end in "QRST"
        }
        self.assertEqual(fares, {"Q": 70, "R": 110, "S": 150, "T": 190})


# ---------- API endpoints ----------

class ApiTests(TestCase):
    def setUp(self):
        self.stops = make_test_data()
        self.a = self.stops["A"].id
        self.d = self.stops["D"].id

    def plan(self, **params):
        return self.client.get("/api/plan/", params)

    def test_plan_returns_all_options(self):
        response = self.plan(**{"from": self.a, "to": self.d})
        self.assertEqual(response.status_code, 200)
        self.assertEqual(len(response.json()["options"]), 3)

    def test_plan_single_mode(self):
        response = self.plan(**{"from": self.a, "to": self.d, "mode": "cheapest"})
        self.assertEqual(response.status_code, 200)
        self.assertEqual(len(response.json()["options"]), 1)

    def test_plan_same_stop_is_rejected(self):
        response = self.plan(**{"from": self.a, "to": self.a})
        self.assertEqual(response.status_code, 400)

    def test_plan_non_numeric_id_is_rejected(self):
        response = self.plan(**{"from": "abc", "to": self.d})
        self.assertEqual(response.status_code, 400)

    def test_plan_invalid_mode_is_rejected(self):
        response = self.plan(**{"from": self.a, "to": self.d, "mode": "teleport"})
        self.assertEqual(response.status_code, 400)

    def test_plan_unknown_stop_returns_404(self):
        response = self.plan(**{"from": 999999, "to": self.d})
        self.assertEqual(response.status_code, 404)

    def test_plan_no_route_returns_404(self):
        response = self.plan(**{"from": self.a, "to": self.stops["F"].id})
        self.assertEqual(response.status_code, 404)

    def test_stop_search(self):
        response = self.client.get("/api/stops/", {"q": "stop a"})
        names = [s["name"] for s in response.json()]
        self.assertEqual(names, ["Stop A"])

    def test_route_detail_lists_ordered_stops(self):
        route = Route.objects.get(number="1")
        response = self.client.get(f"/api/routes/{route.id}/")
        self.assertEqual(response.status_code, 200)
        stop_names = [s["stop"]["name"] for s in response.json()["stops"]]
        self.assertEqual(stop_names, ["Stop A", "Stop B", "Stop C"])

class RealDataTests(TestCase):
    def setUp(self):
        call_command("seed_data")

    def test_five_routes_loaded(self):
        self.assertEqual(Route.objects.count(), 5)

    def test_end_to_end_fare_never_exceeds_route_fare(self):
        for route in Route.objects.all():
            route_stops = list(route.route_stops.order_by("sequence"))
            result = plan_route(route_stops[0].stop_id,
                                route_stops[-1].stop_id, "cheapest")
            self.assertIsNotNone(result)
            self.assertLessEqual(result["total_fare"], route.fare)
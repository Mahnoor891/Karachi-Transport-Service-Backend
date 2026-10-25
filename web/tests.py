from django.test import TestCase

from planner.tests import make_test_data
from transport.models import Route


class WebPageTests(TestCase):
    def setUp(self):
        self.stops = make_test_data()

    def test_home_page_loads(self):
        response = self.client.get("/")
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Route 1")

    def test_route_list_page_loads(self):
        response = self.client.get("/routes/")
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Route 3")

    def test_route_detail_page_loads(self):
        route = Route.objects.get(number="1")
        response = self.client.get(f"/routes/{route.id}/")
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Stop B")

    def test_route_detail_unknown_returns_404(self):
        response = self.client.get("/routes/999999/")
        self.assertEqual(response.status_code, 404)

    def test_plan_shows_three_options(self):
        response = self.client.get("/plan/", {"from": "Stop A", "to": "Stop D"})
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Fastest")
        self.assertContains(response, "Cheapest")
        self.assertContains(response, "Fewest transfers")
        self.assertContains(response, "PKR 70")

    def test_plan_empty_form_shows_message(self):
        response = self.client.get("/plan/", {"from": "", "to": ""})
        self.assertContains(response, "Please choose both stops.")

    def test_plan_same_stop_shows_message(self):
        response = self.client.get("/plan/", {"from": "Stop A", "to": "stop a"})
        self.assertContains(response, "must be different")

    def test_plan_unknown_stop_shows_message(self):
        response = self.client.get("/plan/", {"from": "Nowhere", "to": "Stop D"})
        self.assertContains(response, "could not find that stop")

    def test_plan_no_route_shows_message(self):
        response = self.client.get("/plan/", {"from": "Stop A", "to": "Stop F"})
        self.assertContains(response, "No route found")

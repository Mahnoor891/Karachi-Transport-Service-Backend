import heapq
from itertools import count

from django.db.models import Q

from transport.models import RouteStop, SafetyAdvisory

MODES = ["fastest", "cheapest", "fewest_transfers"]


# ---------- Building the graph from the database ----------

def build_graph():
    graph = {
        "routes": {},       # route_id -> Route
        "sequences": {},    # route_id -> [(stop_id, minutes_from_previous), ...]
        "position": {},     # (route_id, stop_id) -> index in the sequence
        "stop_routes": {},  # stop_id -> [route_id, ...]
        "stop_names": {},   # stop_id -> name
        "step_fare": {},
    }
    query = RouteStop.objects.select_related("route", "stop").order_by(
        "route_id", "sequence"
    )
    for rs in query:
        sequence = graph["sequences"].setdefault(rs.route_id, [])
        graph["position"][(rs.route_id, rs.stop_id)] = len(sequence)
        sequence.append((rs.stop_id, rs.minutes_from_previous))
        graph["routes"][rs.route_id] = rs.route
        graph["stop_routes"].setdefault(rs.stop_id, []).append(rs.route_id)
        graph["stop_names"][rs.stop_id] = rs.stop.name
    for route_id, sequence in graph["sequences"].items():
        route = graph["routes"][route_id]
        extra = max(0, route.fare - route.min_fare)
        graph["step_fare"][route_id] = extra / (len(sequence) - 1)    
    return graph


# ---------- Costs ----------

def wait_minutes(route):
    return route.frequency_minutes / 2


def board_cost(route, mode):
    extra = {
        "fastest": 0,
        "cheapest": route.min_fare * 1000,
        "fewest_transfers": 1000,
    }[mode]
    return extra + wait_minutes(route)

def ride_cost(graph, route_id, minutes, mode):
    """Cost of riding one stop. In cheapest mode the fare for that stop counts too."""
    if mode == "cheapest":
        return minutes + graph["step_fare"][route_id] * 1000
    return minutes

def ride_fare(graph, route_id, stops_ridden):
    route = graph["routes"][route_id]
    raw = route.min_fare + graph["step_fare"][route_id] * stops_ridden
    return int(round(raw / 10) * 10)  



def segment_minutes(graph, route_id, stop_a, stop_b):
    """Minutes between two adjacent stops on a route (either direction)."""
    sequence = graph["sequences"][route_id]
    i = graph["position"][(route_id, stop_a)]
    j = graph["position"][(route_id, stop_b)]
    return sequence[max(i, j)][1]


# ---------- Dijkstra ----------

def neighbours(graph, state, mode):
    stop_id, route_id = state
    result = []

    # Board a bus here, or transfer to a different one
    for other in graph["stop_routes"].get(stop_id, []):
        if other != route_id:
            cost = board_cost(graph["routes"][other], mode)
            result.append(((stop_id, other), cost))

    # Ride to the previous / next stop on the current route
    if route_id is not None:
        sequence = graph["sequences"][route_id]
        i = graph["position"][(route_id, stop_id)]
        for j in (i - 1, i + 1):
            if 0 <= j < len(sequence):
                next_stop = sequence[j][0]
                minutes = segment_minutes(graph, route_id, stop_id, next_stop)
                result.append(((next_stop, route_id), ride_cost(graph, route_id, minutes, mode)))

    return result


def rebuild_path(previous, state):
    path = [state]
    while state in previous:
        state = previous[state]
        path.append(state)
    path.reverse()
    return path


def dijkstra(graph, origin_id, destination_id, mode):
    start = (origin_id, None)
    best = {start: 0}
    previous = {}
    tie = count()                      # avoids comparing states when costs tie
    heap = [(0, next(tie), start)]

    while heap:
        cost, _, state = heapq.heappop(heap)
        if cost > best.get(state, float("inf")):
            continue
        if state[0] == destination_id and state[1] is not None:
            return rebuild_path(previous, state)
        for next_state, step in neighbours(graph, state, mode):
            new_cost = cost + step
            if new_cost < best.get(next_state, float("inf")):
                best[next_state] = new_cost
                previous[next_state] = state
                heapq.heappush(heap, (new_cost, next(tie), next_state))

    return None                        # no route found


# ---------- Turning a path into a readable result ----------

def build_legs(graph, path):
    names = graph["stop_names"]
    legs = []
    for (stop_a, route_a), (stop_b, route_b) in zip(path, path[1:]):
        if stop_a == stop_b:           # boarding a bus
            route = graph["routes"][route_b]
            legs.append({
                "route_id": route.id,
                "route_number": route.number,
                "route_name": route.name,
                "fare": route.fare,
                "from_stop": names[stop_a],
                "to_stop": names[stop_a],
                "stops": [names[stop_a]],
                "stop_ids": [stop_a],
                "wait_minutes": wait_minutes(route),
                "ride_minutes": 0,
            })
        else:                          # riding on the current bus
            leg = legs[-1]
            leg["to_stop"] = names[stop_b]
            leg["stops"].append(names[stop_b])
            leg["stop_ids"].append(stop_b)
            leg["ride_minutes"] += segment_minutes(graph, route_a, stop_a, stop_b)
    for leg in legs:
        leg["fare"] = ride_fare(graph, leg["route_id"], len(leg["stops"]) - 1)
    return legs


def find_advisories(legs):
    route_ids = {leg["route_id"] for leg in legs}
    stop_ids = {sid for leg in legs for sid in leg["stop_ids"]}
    found = SafetyAdvisory.objects.filter(
        Q(route_id__in=route_ids) | Q(stop_id__in=stop_ids)
    )
    return [{"level": a.level, "message": a.message} for a in found]


def summarise(graph, path, mode):
    legs = build_legs(graph, path)
    total_minutes = sum(l["wait_minutes"] + l["ride_minutes"] for l in legs)
    result = {
        "mode": mode,
        "legs": legs,
        "total_minutes": round(total_minutes),
        "total_fare": sum(l["fare"] for l in legs),
        "transfers": len(legs) - 1,
        "advisories": find_advisories(legs),
    }
    for leg in legs:                   # internal fields, not needed by the UI
        del leg["stop_ids"], leg["route_id"]
    return result


# ---------- Public functions ----------

def plan_with_graph(graph, origin_id, destination_id, mode):
    if origin_id == destination_id:
        return None
    path = dijkstra(graph, origin_id, destination_id, mode)
    return summarise(graph, path, mode) if path else None


def plan_route(origin_id, destination_id, mode="fastest"):
    return plan_with_graph(build_graph(), origin_id, destination_id, mode)


def compare_routes(origin_id, destination_id):
    """Fastest, cheapest and fewest-transfers options for the comparison view."""
    graph = build_graph()
    options = [plan_with_graph(graph, origin_id, destination_id, m) for m in MODES]
    return [o for o in options if o is not None]
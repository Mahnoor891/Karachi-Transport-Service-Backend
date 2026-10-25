# Karachi Public Transport Companion (Backend)

A REST API that helps commuters in Karachi plan local bus journeys. Give it a starting stop and a destination, and it returns the best bus combinations with **estimated travel time, fare, number of transfers and safety tips**.

Built as a group project for **Software Project Management (506)**, Department of Computer Science, University of Karachi. The project is managed with Scrum, Jira, Microsoft Teams and Toggl Track.

> This repository contains the **backend**. The mobile-first frontend (Django templates + Bootstrap) uses the API described below.

---

## Features

- Search for stops by name
- Find a journey between any two stops, including bus changes
- Compare three options: **fastest**, **cheapest** and **fewest transfers**
- Distance-based fares (30 PKR for a short ride, up to 200 PKR for a whole route)
- Route details with the ordered list of stops
- Safety advisories for routes and stops
- Automatic tests (20 tests)

**Not included (out of scope):** live GPS tracking, ticketing and payments, native app store deployment.

---

## Tech stack

| Tool | Purpose |
|---|---|
| Python | Programming language |
| Django | Web framework |
| Django REST Framework | JSON API |
| PostgreSQL | Database |
| Django TestCase | Automated tests |

---

## Bus routes included

Five local bus routes, all bidirectional, with 70 different stops.

| Route | Stops | From → To |
|---|---|---|
| Masood Bus | 30 | Malir Halt → Lyari 36 |
| G-17 | 18 | Badar Chowk → University Road |
| F-11 | 18 | Pakhtoonabad → Korangi No. 6 |
| A3 | 13 | Malir Halt → Kemari |
| D7 | 13 | Surjani Town → Tower |

The data is stored in [`transport/routes_data.json`](transport/routes_data.json). Stop lists come from the team's research. Travel times, bus intervals, service hours and safety messages are **estimates** and should be verified.

---

## Project structure

```
karachi_transport/
├── config/                      Project settings and main URLs
├── transport/                   Data layer
│   ├── models.py                Stop, Route, RouteStop, SafetyAdvisory
│   ├── serializers.py           Models → JSON
│   ├── admin.py                 Django admin setup
│   ├── routes_data.json         Real bus data
│   └── management/commands/
│       └── seed_data.py         Loads routes_data.json into the database
├── planner/                     Logic layer
│   ├── services.py              Route-search algorithm and fare rule
│   ├── views.py                 API endpoints
│   ├── urls.py                  API addresses
│   └── tests.py                 Automated tests
└── manage.py
```

---

## Getting started

### 1. Prerequisites

- Python 3.10 or newer
- PostgreSQL

### 2. Clone and create a virtual environment

```bash
git clone <your-repository-url>
cd karachi_transport
python -m venv venv
venv\Scripts\activate
pip install django djangorestframework psycopg2-binary
```

On macOS or Linux, activate with `source venv/bin/activate`.

### 3. Create the database

In pgAdmin or `psql`, create an empty database:

```sql
CREATE DATABASE karachi_transport;
```

### 4. Configure the database password

`config/settings.py` reads the password from an environment variable, so it is never committed to GitHub.

```bash
set DB_PASSWORD=your_postgres_password
```

On macOS or Linux, use `export DB_PASSWORD=your_postgres_password`. If your PostgreSQL user, host or port are different from the defaults (`postgres`, `localhost`, `5432`), update the `DATABASES` section in `config/settings.py`.

### 5. Create the tables and load the data

```bash
python manage.py migrate
python manage.py seed_data
python manage.py createsuperuser
```

`seed_data` prints `Loaded 70 stops and 5 routes.` It **deletes and reloads** all stops, routes and advisories each time, so edit `routes_data.json` (not the admin) when you change the data.

### 6. Run the server

```bash
python manage.py runserver
```

Open http://127.0.0.1:8000/api/stops/ to check it works. The admin site is at http://127.0.0.1:8000/admin/.

### 7. Run the tests

```bash
python manage.py test
```

You should see `Ran 20 tests` and `OK`.

---

## API

All endpoints use `GET` and return JSON. The base path is `/api/`.

| Endpoint | Description |
|---|---|
| `/api/stops/?q=text` | Stops whose name contains the text |
| `/api/routes/` | All routes |
| `/api/routes/<id>/` | One route with its ordered stops and advisories |
| `/api/plan/?from=<id>&to=<id>&mode=<mode>` | Journey options between two stops |
| `/api/safety/?route=<number>` | Safety advisories (all if no route is given) |

`mode` is optional: `fastest`, `cheapest`, `fewest_transfers` or `all` (default, returns three options).

Stop ids change whenever the data is reloaded, so always look them up first with `/api/stops/?q=`.

### Example

Find the id of the two stops:

```
GET /api/stops/?q=surjani
GET /api/stops/?q=jubilee
```

Then plan the journey (here the ids are 27 and 9):

```
GET /api/plan/?from=27&to=9&mode=cheapest
```

Response (shortened):

```json
{
  "from": "Surjani Town",
  "to": "Karachi University (Jubilee Gate)",
  "options": [
    {
      "mode": "cheapest",
      "total_minutes": 74,
      "total_fare": 140,
      "transfers": 0,
      "legs": [
        {
          "route_number": "Masood",
          "route_name": "Masood Bus (Malir Halt - Lyari 36)",
          "fare": 140,
          "from_stop": "Surjani Town",
          "to_stop": "Karachi University (Jubilee Gate)",
          "wait_minutes": 5.0,
          "ride_minutes": 69,
          "stops": ["Surjani Town", "4K Chowrangi", "..."]
        }
      ],
      "advisories": []
    }
  ]
}
```

### Errors

| Situation | Status |
|---|---|
| `from` or `to` is not a number | 400 |
| `from` and `to` are the same stop | 400 |
| Invalid `mode` | 400 |
| Unknown stop id | 404 |
| No journey exists between the stops | 404 |

---

## How it works

### Data model

- **Stop**: a place where a bus stops
- **Route**: a bus line with its fare range and how often buses come
- **RouteStop**: the ordered stops of a route, with the minutes from the previous stop
- **SafetyAdvisory**: a tip or warning for a route or a stop

Two routes are connected when they share a stop with exactly the same name. Passengers change buses there.

### Fare rule

The fare grows with the number of stops you ride on one bus:

```
fare = 30 + (200 - 30) × (stops ridden ÷ hops on the route), rounded to the nearest 10
```

Riding a whole route costs 200 PKR. When a journey needs two buses, the fares are added.

### Route search

The stops and rides are treated as a graph, and the search uses **Dijkstra's algorithm**. The search remembers two things together: the stop you are at and the bus you are on. There are only two kinds of moves:

- **Ride** to the next or previous stop on the same bus (cost: minutes between the stops)
- **Board** a bus, or change to another bus, at the current stop (cost: waiting time, which is half the bus interval)

The three modes use the same algorithm with different costs:

| Mode | Extra cost when boarding | Extra cost per stop ridden |
|---|---|---|
| fastest | none | none |
| cheapest | minimum fare × 1000 | stop fare × 1000 |
| fewest transfers | 1000 | none |

The large multiplier makes fare (or the number of buses) the main priority, and minutes only break ties. The code is in [`planner/services.py`](planner/services.py).

### Assumptions

- Routes run in both directions with the same travel times
- Estimates come from scheduled data, not live tracking
- Each stop appears only once on a route

---

## Testing

The 20 tests build a small test network of their own, so they keep working when the real data changes. They check the three modes, reverse trips, the fare rule, safety advisories, every API endpoint and error code, and that the real data loads correctly.

---

## Troubleshooting

| Problem | Fix |
|---|---|
| `database "karachi_transport" does not exist` | Create the database (step 3) |
| `psycopy2-binary` not found | The package name is `psycopg2-binary` (with a **g**) |
| `django-admin.exe` blocked by Windows policy | Use `python -m django <command>` instead of `django-admin <command>` |
| `module 'planner.views' has no attribute ...` | The file must be named `views.py` (with an **s**) |
| `/api/plan/` returns 400 "must be stop ids" | Use real numeric ids from `/api/stops/`, not placeholder text |

---

## Limitations and future work

- No live bus tracking
- Only five routes; times, intervals and safety messages need verification
- Fastest mode can suggest several bus changes, because waiting time is counted at every boarding (a fixed transfer penalty could be added)
- Stop coordinates are not filled in yet, so a map view is not possible until they are added

---

## Team

Software Project Management (506), 6th semester, University of Karachi.

| Name | Role |
|---|---|
| _add name_ | Team Lead |
| _add name_ | Backend development |
| _add name_ | Frontend / UI-UX |
| _add name_ | Data research |

## License

Academic project. Add a license here if you plan to publish it.

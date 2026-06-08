# FleetMind — Complete Project Structure

```
fleetmind/
│
├── README.md                          # Main project doc with GIF demo
├── .env.example                       # Environment variables template
├── .gitignore                         # Git ignore
├── docker-compose.yml                 # All services: FastAPI, Streamlit, Redis, DB
├── requirements.txt                   # Python deps
│
│
├── config/
│   ├── __init__.py
│   ├── settings.py                    # Environment vars, config classes
│   ├── constants.py                   # Cost configs, speed limits, penalties
│   └── database.py                    # DB connection setup
│
│
├── models/                            # SQLAlchemy domain models (from previous file)
│   ├── __init__.py
│   ├── depot.py                       # Depot model
│   ├── vehicle.py                     # Vehicle, VehicleType models
│   ├── driver.py                      # Driver model
│   ├── stop.py                        # Stop model
│   ├── route_plan.py                  # RoutePlan, RouteLeg models
│   ├── disruption.py                  # DisruptionEvent model
│   ├── gps_ping.py                    # GPSPing model
│   ├── behavior_log.py                # DriverBehaviorLog model
│   ├── cost_config.py                 # CostConfig model
│   └── base.py                        # Declarative base, common mixins
│
│
├── schemas/                           # Pydantic request/response schemas
│   ├── __init__.py
│   ├── depot.py                       # DepotCreate, DepotUpdate, DepotResponse
│   ├── vehicle.py                     # VehicleCreate, VehicleResponse, etc
│   ├── driver.py
│   ├── stop.py
│   ├── route_plan.py
│   ├── disruption.py
│   ├── cost.py
│   ├── error.py                       # ErrorResponse schema
│   └── shared.py                      # Pagination, shared schemas
│
│
├── solver/                            # VRP solver core logic
│   ├── __init__.py
│   ├── vrp_solver.py                  # OR-Tools wrapper, CVRPTW solver
│   ├── distance_matrix.py             # OpenRouteService API calls, caching
│   ├── cost_calculator.py             # Fuel, driver, vehicle costs
│   ├── multi_depot.py                 # Multi-depot assignment logic
│   └── what_if_engine.py              # Sandbox scenario solving
│
│
├── services/                          # Business logic layer
│   ├── __init__.py
│   ├── route_service.py               # RoutePlan CRUD, state management
│   ├── depot_service.py               # Depot operations
│   ├── vehicle_service.py             # Vehicle assignment, status updates
│   ├── driver_service.py              # Driver management
│   ├── disruption_service.py          # Handle disruption events, auto-replan
│   ├── route_tracker.py               # Track live route progress
│   ├── geofence_service.py            # Geofence checking, alerts
│   ├── eta_calculator.py              # ETA recalculation from GPS
│   └── cost_service.py                # Cost calculations, savings analysis
│
│
├── agents/                            # AI agents (LangGraph, LangChain)
│   ├── __init__.py
│   ├── dispatcher_agent.py            # Main dispatcher NL agent (LangGraph)
│   ├── tools.py                       # Tool definitions for agents
│   ├── disruption_monitor.py          # Background: weather alerts, auto-detect
│   ├── behavior_scorer.py             # Daily driver behavior scoring
│   └── prompts.py                     # System prompts, templates
│
│
├── api/                               # FastAPI app structure
│   ├── __init__.py
│   ├── main.py                        # App instantiation, middleware
│   ├── routes/
│   │   ├── __init__.py
│   │   ├── depots.py                  # GET/POST depots
│   │   ├── vehicles.py                # Vehicle CRUD, status
│   │   ├── drivers.py                 # Driver CRUD
│   │   ├── stops.py                   # Stop CRUD
│   │   ├── routes.py                  # GET routes, POST /replan, POST /what-if
│   │   ├── dispatcher.py              # POST /dispatcher/chat (agent NL interface)
│   │   ├── tracking.py                # WebSocket, live GPS, geofence
│   │   ├── history.py                 # GET route history, disruptions, analytics
│   │   ├── health.py                  # Health check endpoints
│   │   └── cost.py                    # GET cost dashboard, what-if costs
│   │
│   ├── middleware/
│   │   ├── __init__.py
│   │   ├── auth.py                    # JWT validation
│   │   ├── request_id.py              # Request ID propagation
│   │   └── error_handler.py           # Global error handler
│   │
│   └── websocket/
│       ├── __init__.py
│       ├── connection_manager.py      # WebSocket connection registry
│       └── handlers.py                # GPS ping broadcast, alerts
│
│
├── viz/                               # Map rendering, visualizations
│   ├── __init__.py
│   ├── map_renderer.py                # Folium: before/after, geofences, real routes
│   ├── cost_charts.py                 # Plotly: cost breakdown, savings chart
│   ├── analytics_charts.py            # Distance per driver, stops per driver
│   └── geojson_builder.py             # GeoJSON for map overlays
│
│
├── ui/                                # Streamlit frontend
│   ├── __init__.py
│   ├── app.py                         # Main Streamlit app entry
│   ├── pages/
│   │   ├── 1_🗺️_Live_Routes.py        # Tab 1: Live map, before/after
│   │   ├── 2_💬_Dispatcher.py         # Tab 2: Chat with agent
│   │   ├── 3_📊_Analytics.py          # Tab 3: Charts, metrics
│   │   ├── 4_📋_History.py            # Tab 4: Route history, disruptions
│   │   ├── 5_🎯_What_If.py            # Tab 5: Scenario planner
│   │   └── 6_⚙️_Settings.py           # Tab 6: Cost config, time windows
│   │
│   ├── components/
│   │   ├── __init__.py
│   │   ├── fleet_status.py            # Sidebar driver cards
│   │   ├── disruption_input.py        # Chat interface
│   │   ├── cost_metrics.py            # Cost cards
│   │   └── route_comparison.py        # Before/after side-by-side
│   │
│   └── utils/
│       ├── __init__.py
│       ├── api_client.py              # HTTP calls to FastAPI
│       └── formatters.py              # Time, distance, cost formatting
│
│
├── jobs/                              # Background tasks (Celery)
│   ├── __init__.py
│   ├── tasks.py                       # VRP solve, behavior score, replan
│   ├── gps_simulator.py               # Simulated driver movement along routes
│   ├── disruption_monitor.py          # Periodic weather alert check
│   └── scheduler.py                   # APScheduler for daily batch jobs
│
│
├── seeds/                             # Demo data & dataset builders
│   ├── __init__.py
│   ├── seed_data.py                   # Insert demo: depots, vehicles, stops
│   ├── dalhi_dataset.py               # Real Delhi locations
│   ├── bangalore_dataset.py           # Real Bangalore locations
│   └── clear_db.py                    # Reset database (dev only)
│
│
├── tests/                             # Pytest suite
│   ├── __init__.py
│   ├── conftest.py                    # Pytest fixtures
│   ├── test_vrp_solver.py             # Test VRP outputs
│   ├── test_api_routes.py             # Test FastAPI endpoints
│   ├── test_disruption_handler.py     # Test replan logic
│   ├── test_cost_calculator.py        # Test cost math
│   ├── test_agents.py                 # Test LangChain tools
│   └── test_geofence.py               # Test geofence detection
│
│
├── docs/                              # Architecture, API docs
│   ├── ARCHITECTURE.md                # System design deep-dive
│   ├── LLD.md                         # Low-level design (this file)
│   ├── API.md                         # OpenAPI specification walkthrough
│   ├── DATABASE.md                    # Schema diagrams, queries
│   ├── DEPLOYMENT.md                  # Docker, K8s, env setup
│   └── CONTRIBUTING.md                # Dev guidelines
│
│
├── notebooks/                         # Jupyter exploration (not in prod)
│   ├── vrp_exploration.ipynb          # VRP algorithm exploration
│   └── cost_analysis.ipynb            # Cost model analysis
│
│
└── .github/
    └── workflows/
        ├── test.yml                   # Run pytest on push
        ├── lint.yml                   # Ruff, black
        └── deploy.yml                 # Build Docker, push to registry
```

---

## Key Folder Purposes

| Folder     | Purpose |
|-----------|---------|
| `config/` | Centralized settings, env vars, constants |
| `models/` | SQLAlchemy ORM models (database schema) |
| `schemas/` | Pydantic validation for API requests/responses |
| `solver/` | Pure VRP math layer — OR-Tools wrapper, distance matrix |
| `services/` | Business logic — orchestrates solver, DB, external APIs |
| `agents/` | LangGraph/LangChain AI agents, tools, prompts |
| `api/` | FastAPI routes, WebSocket handlers, middleware |
| `viz/` | Folium maps, Plotly charts |
| `ui/` | Streamlit frontend, pages, components |
| `jobs/` | Celery tasks, background workers, scheduler |
| `seeds/` | Demo data generators, test datasets |
| `tests/` | Pytest unit/integration tests |
| `docs/` | Architecture guides, API docs, deployment |

---

## Import Style (to avoid circular imports)

**Top-level flow:**

```
ui/    → api_client → FastAPI
jobs/  → services → solver + models
api/   → services → solver + models
agents/ → services → models
```

**Never import upward:**
- Never import `ui` from `services`
- Never import `services` from `models`
- Never import `api` from `solver`

---

## File Naming Conventions

- **Models** (domain classes): `user.py`, `depot.py` (singular)
- **Services** (business logic): `user_service.py` (singular + `_service`)
- **Routes** (API endpoints): `users.py` (plural)
- **Tests**: `test_*` (prefix with `test_`)
- **Schemas** (Pydantic): match model name, `user.py`

# FleetMind — Low-Level Design (LLD)

Detailed component interactions, API contracts, data flows, and implementation specifics.

---

## 1. Core VRP Solver Module

### File: `app/services/vrp_solver.py`

```python
class VRPSolver:
    """
    Wrapper around Google OR-Tools.
    Handles CVRPTW (Capacitated Vehicle Routing with Time Windows).
    Multi-depot support: each vehicle is assigned to one depot at start.
    """
    
    def __init__(self, timeout_seconds=30):
        self.timeout_seconds = timeout_seconds
        self.solver_stats = {}
    
    def solve(
        self,
        distance_matrix: List[List[int]],      # meters between all nodes
        depots: List[Depot],                    # starting locations
        vehicles: List[Vehicle],                # with capacity, vehicle_type
        stops: List[Stop],                      # with demand, time windows
        vehicle_depot_assignment: Dict[str, str], # vehicle_id → depot_id
        locked_assignments: Optional[Dict[str, List[str]]] = None
    ) -> SolveResult:
        """
        Solves multi-depot CVRPTW.
        Returns optimized routes or raises InfeasibleError.
        
        ### Input validation
        - All vehicle capacities must be > 0
        - Total demand must fit in total capacity
        - Depots must be in distance_matrix (indices 0 to len(depots)-1)
        - Stops must be in distance_matrix (indices len(depots) to N-1)
        
        ### Node indexing strategy
        nodes = [*depots, *stops]
        
        depot_0 index = 0 (Dallas warehouse)
        depot_1 index = 1 (Houston warehouse)
        stop_0 index = 2 (Stop at Arlington)
        stop_1 index = 3 (Stop at Fort Worth)
        ...
        
        Each vehicle starts at its assigned depot, returns to same depot.
        """
        
        # Step 1: Validate inputs
        self._validate_inputs(depots, vehicles, stops)
        
        # Step 2: Build OR-Tools distance/time matrix
        # In practice, distance_matrix is in meters, time is distance/speed
        time_matrix = self._compute_time_matrix(
            distance_matrix, 
            avg_speeds={v.vehicle_type.avg_speed_kmh for v in vehicles}
        )
        
        # Step 3: Create routing index manager
        # Two options:
        # A) Single depot: RoutingIndexManager(len(matrix), num_vehicles, depot_idx)
        # B) Multi-depot: Create separate manager per depot, merge solutions
        # 
        # We use option B: solve each depot independently, then merge
        solutions_by_depot = {}
        for depot in depots:
            depot_vehicles = [v for v in vehicles if v.depot_id == depot.id]
            if not depot_vehicles:
                continue  # Skip empty depots
            
            manager = pywrapcp.RoutingIndexManager(
                len(matrix), 
                len(depot_vehicles), 
                depot.index_in_matrix  # depot is both start and end
            )
            routing = pywrapcp.RoutingModel(manager)
            
            # Register transit callbacks
            transit_callback_index = routing.RegisterTransitCallback(
                lambda f, t: distance_matrix[f][t]
            )
            routing.SetArcCostEvaluatorOfAllVehicles(transit_callback_index)
            
            # Add capacity constraint
            demand_callback_index = routing.RegisterUnaryTransitCallback(
                lambda idx: matrix[manager.IndexToNode(idx)].demand_kg
            )
            routing.AddDimensionWithVehicleCapacity(
                demand_callback_index, 0,
                [v.vehicle_type.capacity_kg for v in depot_vehicles],
                True, "Capacity"
            )
            
            # Add time windows constraint
            time_callback_index = routing.RegisterTransitCallback(
                lambda f, t: time_matrix[f][t]
            )
            time_dimension = routing.GetDimensionOrCreate("Time", time_callback_index, ...)
            for stop in stops:
                time_var = time_dimension.CumulVar(stop.index_in_matrix)
                time_var.SetRange(stop.time_window_start * 60, stop.time_window_end * 60)
            
            # Add service time at each stop
            for stop in stops:
                routing.AddDisjunction(
                    [manager.NodeToIndex(stop.index_in_matrix)],
                    penalty=stop.service_time_min * 100  # soft constraint
                )
            
            # Solve
            search_params = pywrapcp.DefaultRoutingSearchParameters()
            search_params.first_solution_strategy = routing_enums_pb2.FirstSolutionStrategy.PATH_CHEAPEST_ARC
            search_params.local_search_metaheuristic = routing_enums_pb2.LocalSearchMetaheuristic.GUIDED_LOCAL_SEARCH
            search_params.time_limit.seconds = self.timeout_seconds
            
            solution = routing.SolveWithParameters(search_params)
            
            if not solution:
                raise InfeasibleError(f"No solution for depot {depot.name}")
            
            solutions_by_depot[depot.id] = self._extract_routes(routing, manager, solution)
        
        # Step 4: Return merged solution
        return SolveResult(
            status="SUCCESS",
            routes=self._merge_solutions(solutions_by_depot, vehicles),
            total_distance_km=...,
            solve_time_ms=...,
            solver_status=...
        )
    
    def _extract_routes(self, routing, manager, solution) -> Dict[str, RouteInfo]:
        """
        Convert OR-Tools solution to readable format.
        
        Output: {
            "vehicle_uuid_1": {
                "stops": [depot_idx, stop_idx_2, stop_idx_5, depot_idx],
                "distance_m": 45000,
                "duration_min": 120,
                "load_kg": 180
            }
        }
        """
        routes = {}
        for vehicle_id in range(routing.vehicles()):
            route_indices = []
            index = routing.Start(vehicle_id)
            while not routing.IsEnd(index):
                route_indices.append(manager.IndexToNode(index))
                index = solution.Value(routing.NextVar(index))
            route_indices.append(manager.IndexToNode(index))  # return to depot
            
            distance = solution.RouteMeters(vehicle_id)
            duration = solution.RouteDurationValue(vehicle_id)
            
            routes[f"vehicle_{vehicle_id}"] = RouteInfo(
                stops=route_indices,
                distance_m=distance,
                duration_min=duration
            )
        
        return routes
    
    def _merge_solutions(self, by_depot: Dict, vehicles: List[Vehicle]) -> Dict:
        """
        Depot 1 solved separately, Depot 2 solved separately.
        Merge into single output keyed by vehicle UUID.
        """
        result = {}
        for depot_id, routes in by_depot.items():
            depot_vehicles = [v for v in vehicles if v.depot_id == depot_id]
            for i, vehicle in enumerate(depot_vehicles):
                result[vehicle.id] = routes[f"vehicle_{i}"]
        return result
```

---

## 2. Distance Matrix & Cache Layer

### File: `app/services/distance_matrix.py`

```python
class DistanceMatrixService:
    """
    Computes distance matrix from stops.
    Uses OpenRouteService API for real road distances.
    Caches results in Redis with 30-day TTL.
    """
    
    def __init__(self, redis_client, ors_api_key):
        self.redis = redis_client
        self.ors_key = ors_api_key
        self.cache_ttl = 86400 * 30  # 30 days
    
    async def get_matrix(
        self, 
        depots: List[Depot], 
        stops: List[Stop]
    ) -> List[List[int]]:
        """
        Returns NxN matrix of distances in meters.
        N = len(depots) + len(stops)
        
        All nodes = [depot_0, depot_1, ..., stop_0, stop_1, ...]
        
        For small datasets (<100 stops): compute full matrix in one ORS call.
        For large: compute in batches (ORS limits 100 locations per request).
        
        ### Caching strategy
        Cache key: f"dist_matrix:{depot_hash}:{stop_hash}"
        If all depots + stops haven't changed → cache hit → instant return.
        If new stop added → compute only new pairs (partial compute + merge).
        """
        
        nodes = depots + stops
        n = len(nodes)
        
        # Check cache first
        cache_key = self._make_cache_key(nodes)
        cached = await self.redis.get(cache_key)
        if cached:
            return json.loads(cached)  # Deserialize from JSON
        
        # Compute via ORS
        if n <= 100:
            # Single request
            matrix = await self._compute_via_ors_bulk(nodes)
        else:
            # Batch requests + merge
            matrix = await self._compute_via_ors_batch(nodes, batch_size=100)
        
        # Cache
        await self.redis.set(
            cache_key,
            json.dumps(matrix),
            ex=self.cache_ttl
        )
        
        return matrix
    
    async def _compute_via_ors_bulk(self, nodes: List[DepotOrStop]) -> List[List[int]]:
        """
        Single call to ORS Distance Matrix API.
        POST /v2/matrix/driving-car
        {
            "locations": [[lon, lat], [lon, lat], ...],
            "metrics": ["distance", "duration"],
            "units": "m"
        }
        
        Returns distances in meters, duration in seconds.
        We use distance.
        """
        coordinates = [[node.lon, node.lat] for node in nodes]
        
        response = await ors_api_client.post(
            "https://api.openrouteservice.org/v2/matrix/driving-car",
            json={"locations": coordinates, "metrics": ["distance"]},
            headers={"Authorization": self.ors_key}
        )
        
        return response.json()["distances"]  # NxN list of distances in meters
    
    async def _compute_via_ors_batch(self, nodes, batch_size=100):
        """
        For >100 stops: partition into chunks, compute batch distances.
        Then merge using triangle inequality (heuristic, not exact).
        
        In production: use OSRM self-hosted instead to avoid API costs.
        """
        # For now: call _compute_via_ors_bulk multiple times
        # Not ideal, but works for demo
        matrix = [[0] * len(nodes) for _ in range(len(nodes))]
        
        for i in range(0, len(nodes), batch_size):
            batch_i = nodes[i:i+batch_size]
            for j in range(0, len(nodes), batch_size):
                batch_j = nodes[j:j+batch_size]
                
                sub_matrix = await self._compute_via_ors_bulk(batch_i + batch_j)
                
                # Copy into full matrix
                for a, node_a in enumerate(batch_i):
                    for b, node_b in enumerate(batch_j):
                        matrix[nodes.index(node_a)][nodes.index(node_b)] = sub_matrix[a][len(batch_j) + b]
        
        return matrix
    
    async def get_directions(
        self, 
        from_node: DepotOrStop, 
        to_node: DepotOrStop
    ) -> List[Tuple[float, float]]:
        """
        Returns list of [lat, lon] waypoints along actual road.
        Used by map renderer to draw real road polylines.
        
        Cache: individual direction pairs by (from_id, to_id).
        """
        cache_key = f"directions:{from_node.id}:{to_node.id}"
        cached = await self.redis.get(cache_key)
        if cached:
            return json.loads(cached)
        
        response = await ors_api_client.get(
            f"https://api.openrouteservice.org/v2/directions/driving-car/geojson",
            params={
                "start": f"{from_node.lon},{from_node.lat}",
                "end": f"{to_node.lon},{to_node.lat}"
            },
            headers={"Authorization": self.ors_key}
        )
        
        # Extract coordinates from GeoJSON
        geom = response.json()["features"][0]["geometry"]
        waypoints = [[c[1], c[0]] for c in geom["coordinates"]]  # convert to [lat, lon]
        
        await self.redis.set(cache_key, json.dumps(waypoints), ex=86400*30)
        
        return waypoints
```

---

## 3. Route State Manager

### File: `app/services/route_manager.py`

```python
class RouteManager:
    """
    Manages route plan lifecycle.
    Persists to PostgreSQL, live state in Redis.
    """
    
    async def create_plan(
        self,
        depot: Depot,
        vehicles: List[Vehicle],
        stops: List[Stop],
        db: Session
    ) -> RoutePlan:
        """
        1. Validate inputs
        2. Call VRP solver
        3. Store RoutePlan + RouteLeg rows
        4. Cache in Redis
        5. Return plan object
        """
        
        # Validate
        if not vehicles or not stops:
            raise ValueError("Need at least 1 vehicle and 1 stop")
        
        if sum(v.vehicle_type.capacity_kg for v in vehicles) < sum(s.demand_kg for s in stops):
            raise InfeasibleError("Total vehicle capacity < total demand")
        
        # Get distance matrix
        distance_matrix = await self.distance_service.get_matrix([depot], stops)
        
        # Solve
        result = self.vrp_solver.solve(
            distance_matrix=distance_matrix,
            depots=[depot],
            vehicles=vehicles,
            stops=stops
        )
        
        if result.status != "SUCCESS":
            raise InfeasibleError(f"Solver failed: {result.status}")
        
        # Create database records
        plan = RoutePlan(
            depot_id=depot.id,
            status=RoutePlanStatus.ACTIVE,
            num_vehicles=len(vehicles),
            num_stops=len(stops),
            total_distance_km=result.total_distance_km,
            routes_json=result.routes,
            solve_time_ms=result.solve_time_ms
        )
        
        db.add(plan)
        db.flush()  # Get plan.id before adding legs
        
        # Create route legs
        for vehicle in vehicles:
            route_info = result.routes[vehicle.id]
            for seq, stop_idx in enumerate(route_info["stops"]):
                if stop_idx == depot.index:
                    continue  # Skip depot entries
                
                stop = stops[stop_idx - 1]  # Adjust for depot at index 0
                
                leg = RouteLeg(
                    route_plan_id=plan.id,
                    vehicle_id=vehicle.id,
                    stop_id=stop.id,
                    sequence_order=seq,
                    status="pending"
                )
                db.add(leg)
        
        db.commit()
        
        # Cache in Redis
        await self.redis.set(
            f"route_plan:{plan.id}",
            json.dumps(plan.to_dict()),
            ex=86400  # 1 day
        )
        
        return plan
    
    async def apply_disruption(
        self,
        current_plan: RoutePlan,
        disruption: Dict,  # {type: "driver_unavailable", driver_id: "..."}
        db: Session
    ) -> RoutePlan:
        """
        Applies disruption and returns new replanned RoutePlan.
        
        Process:
        1. Fetch current plan constraints
        2. Modify constraints based on disruption
        3. Re-solve VRP
        4. Create new RoutePlan (linked to parent via parent_plan_id)
        5. Store DisruptionEvent
        6. Return new plan
        
        ### Disruption types
        
        DRIVER_UNAVAILABLE: Set driver's vehicle capacity to 0
        → Solver auto-reassigns stops to other vehicles
        
        ROAD_BLOCKED: Set distance between nodes A and B to 9999999
        → Solver avoids this edge
        
        STOP_CANCELLED: Remove stop from stops list
        → Solver doesn't assign any vehicle to it
        
        VEHICLE_BREAKDOWN: Set vehicle capacity to 0
        → Same as driver unavailable
        """
        
        # Get parent plan details
        parent = current_plan
        stops = db.query(Stop).join(RouteLeg).filter(
            RouteLeg.route_plan_id == parent.id
        ).all()
        vehicles = db.query(Vehicle).join(RouteLeg).filter(
            RouteLeg.route_plan_id == parent.id
        ).distinct().all()
        
        # Modify constraints
        if disruption["type"] == "driver_unavailable":
            driver_id = disruption["driver_id"]
            driver = db.query(Driver).get(driver_id)
            vehicle = driver.vehicle
            vehicles.remove(vehicle)  # Remove from assignable vehicles
        
        elif disruption["type"] == "road_blocked":
            from_idx, to_idx = disruption["blocked_edge"]
            # Will handle in solver with high-cost edge
        
        # Re-solve
        new_plan = await self.create_plan(
            depot=parent.depot,
            vehicles=vehicles,
            stops=stops,
            db=db
        )
        new_plan.parent_plan_id = parent.id
        new_plan.status = RoutePlanStatus.ACTIVE
        
        # Record disruption event
        event = DisruptionEvent(
            route_plan_id=parent.id,
            disruption_type=disruption["type"],
            structured_event=disruption,
            dist_before_km=parent.total_distance_km,
            dist_after_km=new_plan.total_distance_km,
            new_plan_id=new_plan.id
        )
        db.add(event)
        db.commit()
        
        return new_plan
```

---

## 4. Cost Engine

### File: `app/services/cost_engine.py`

```python
class CostEngine:
    """
    Calculates operation costs.
    Uses configurable cost model per depot.
    """
    
    def __init__(self, db: Session):
        self.db = db
    
    def calculate(
        self,
        route_plan: RoutePlan,
        depot: Depot,
        vehicles: List[Vehicle]
    ) -> CostBreakdown:
        """
        Returns:
        {
            cost_fuel_rupees: 1200,
            cost_driver_rupees: 3000,
            cost_vehicle_rupees: 1200,
            cost_total: 5400,
            cost_baseline: 8200,  # what it would cost unoptimized
            savings: 2800
        }
        """
        
        config = self.db.query(CostConfig).filter_by(depot_id=depot.id).first()
        if not config:
            config = CostConfig(depot_id=depot.id)  # Use defaults
        
        # Fuel cost
        cost_fuel = route_plan.total_distance_km * config.fuel_cost_per_km
        
        # Driver cost
        total_hours = route_plan.total_duration_min / 60
        cost_driver = total_hours * config.driver_cost_per_hr
        
        # Vehicle fixed cost
        cost_vehicle = len(vehicles) * config.vehicle_fixed_per_day
        
        cost_optimized = cost_fuel + cost_driver + cost_vehicle
        
        # Baseline: assume unoptimized routes (naive 1 stop per vehicle + return)
        cost_baseline = self._calculate_baseline(
            len(vehicles),
            route_plan.num_stops,
            depot,
            config
        )
        
        savings = cost_baseline - cost_optimized
        
        return CostBreakdown(
            cost_fuel=cost_fuel,
            cost_driver=cost_driver,
            cost_vehicle=cost_vehicle,
            cost_total=cost_optimized,
            cost_baseline=cost_baseline,
            savings=savings,
            savings_pct=(savings / cost_baseline) * 100 if cost_baseline > 0 else 0
        )
    
    def _calculate_baseline(self, num_vehicles, num_stops, depot, config):
        """
        Naive baseline: each vehicle gets equal stops,
        calculates route distance assuming sequential visits (no optimization).
        
        Baseline distance ≈ 2 * avg_distance_per_stop * num_stops
        (out and back)
        """
        avg_distance_baseline = 1500  # meters per stop (heuristic)
        total_distance_baseline = num_stops * avg_distance_baseline * 2 / 1000  # km
        
        cost_fuel_base = total_distance_baseline * config.fuel_cost_per_km
        cost_driver_base = (num_stops * 15 / 60) * config.driver_cost_per_hr  # 15 min per stop
        cost_vehicle_base = num_vehicles * config.vehicle_fixed_per_day
        
        return cost_fuel_base + cost_driver_base + cost_vehicle_base
```

---

## 5. Map Renderer

### File: `app/services/map_renderer.py`

```python
class MapRenderer:
    """
    Generates interactive Folium maps with real road polylines.
    """
    
    def __init__(self, distance_service: DistanceMatrixService):
        self.distance_service = distance_service
    
    async def render_route_map(
        self,
        route_plan: RoutePlan,
        depot: Depot,
        vehicles_dict: Dict[str, Vehicle],
        stops_dict: Dict[str, Stop]
    ) -> str:
        """
        Returns HTML string of Folium map.
        
        ### Visual elements
        - Depot as warehouse icon (center of map)
        - Stops as numbered circles (color per vehicle)
        - Real road polylines connecting stops
        - Geofence circles around each stop
        - Popup cards with details
        """
        
        # Center map on depot
        m = folium.Map(
            location=[depot.lat, depot.lon],
            zoom_start=12,
            tiles="OpenStreetMap"
        )
        
        # Add depot marker
        folium.Marker(
            location=[depot.lat, depot.lon],
            popup=f"<b>{depot.name}</b><br>Depot",
            icon=folium.Icon(color="black", icon="warehouse", prefix="fa"),
            tooltip="Warehouse/Depot"
        ).add_to(m)
        
        # Color per vehicle
        colors = ["blue", "red", "green", "purple", "orange", "darkred", "lightblue"]
        
        # Render each vehicle's route
        for vehicle_idx, (vehicle_id, route_info) in enumerate(route_plan.routes_json.items()):
            color = colors[vehicle_idx % len(colors)]
            vehicle = vehicles_dict[vehicle_id]
            
            stops_in_route = route_info["stops"]
            
            # Draw polylines
            route_coords_list = []
            for seq, stop_idx in enumerate(stops_in_route):
                if stop_idx == 0:  # depot
                    continue
                
                stop = stops_dict[stop_idx]
                route_coords_list.append([stop.lat, stop.lon])
                
                # Draw stop marker
                folium.CircleMarker(
                    location=[stop.lat, stop.lon],
                    radius=10,
                    color=color,
                    fill=True,
                    fill_opacity=0.8,
                    weight=2,
                    popup=folium.Popup(
                        f"""
                        <div style="font-family:sans-serif;width:200px">
                            <b>Stop {seq}: {stop.name}</b><br>
                            Demand: {stop.demand_kg}kg<br>
                            Window: {stop.time_window_start}–{stop.time_window_end}<br>
                            Vehicle: {vehicle.plate_number}
                        </div>
                        """,
                        max_width=200
                    ),
                    tooltip=f"{seq}. {stop.name}",
                ).add_to(m)
                
                # Draw geofence circle
                folium.Circle(
                    location=[stop.lat, stop.lon],
                    radius=stop.geofence_radius_m,
                    color=color,
                    fill=False,
                    opacity=0.3,
                    weight=1
                ).add_to(m)
            
            # Draw actual road polylines (via ORS)
            for i in range(len(route_coords_list) - 1):
                from_node = stops_dict[stops_in_route[i+1]]
                to_node = stops_dict[stops_in_route[i+2]]
                
                # Get real road directions
                waypoints = await self.distance_service.get_directions(from_node, to_node)
                
                folium.PolyLine(
                    locations=waypoints,
                    color=color,
                    weight=4,
                    opacity=0.8,
                    smooth_factor=1
                ).add_to(m)
        
        return m._repr_html_()
```

---

## 6. LangChain Dispatcher Agent

### File: `app/agents/dispatcher_agent.py`

```python
from langgraph.graph import StateGraph, END
from langchain_openai import ChatOpenAI
from langchain.tools import Tool

class DispatcherAgent:
    """
    Stateful agent using LangGraph.
    Converts natural language disruptions to structured actions.
    """
    
    def __init__(self, llm, route_manager):
        self.llm = llm
        self.route_manager = route_manager
        self.tools = self._build_tools()
    
    def _build_tools(self) -> List[Tool]:
        """
        Tools the agent can call.
        Each tool is a function that modifies route state.
        """
        
        tools = [
            Tool(
                name="mark_driver_unavailable",
                func=self._tool_mark_driver_unavailable,
                description="Mark a driver as unavailable (sick, vehicle broken). Their stops will be reassigned.",
                args_schema=MarkDriverUnavailableSchema
            ),
            Tool(
                name="block_road_segment",
                func=self._tool_block_road,
                description="Block a road segment (accident, flooding). Routes will avoid this segment.",
                args_schema=BlockRoadSchema
            ),
            Tool(
                name="cancel_stop",
                func=self._tool_cancel_stop,
                description="Cancel a delivery stop. It will not be served today.",
                args_schema=CancelStopSchema
            ),
            Tool(
                name="get_current_routes",
                func=self._tool_get_current_routes,
                description="Get the current route assignments for all drivers.",
                args_schema=None
            ),
        ]
        
        return tools
    
    async def invoke(self, text: str, route_plan_id: str, db: Session) -> str:
        """
        Main entry point.
        Converts NL text → structured action → applies to route plan → returns summary.
        """
        
        # Build initial state
        state = {
            "input": text,
            "messages": [],
            "action": None,
            "result": None,
            "route_plan_id": route_plan_id
        }
        
        # Run LangGraph state machine
        route_plan = db.query(RoutePlan).get(route_plan_id)
        
        # Step 1: LLM parses input
        system_prompt = """
        You are a logistics dispatcher assistant. Parse natural language commands and extract structured actions.
        
        Available actions:
        - mark_driver_unavailable(driver_id) — driver is sick or unavailable
        - block_road_segment(from_stop_id, to_stop_id) — road is blocked
        - cancel_stop(stop_id) — don't deliver to this stop
        - get_current_routes() — show current route assignments
        
        Return only the action call, no explanation.
        """
        
        response = await self.llm.aparse(
            system=system_prompt,
            text=text,
            tools=self.tools
        )
        
        # Step 2: Execute action
        action_result = await self.route_manager.apply_disruption(
            current_plan=route_plan,
            disruption=response.parsed_action,
            db=db
        )
        
        # Step 3: Generate summary
        summary = f"""
        Disruption applied: {response.parsed_action['type']}
        
        Before: {route_plan.total_distance_km:.1f}km, ₹{route_plan.cost_optimized:.0f}
        After: {action_result.total_distance_km:.1f}km, ₹{action_result.cost_optimized:.0f}
        Savings: ₹{route_plan.cost_optimized - action_result.cost_optimized:.0f}
        """
        
        return summary
    
    async def _tool_mark_driver_unavailable(self, driver_id: str, db: Session):
        """Calls route_manager.apply_disruption with DRIVER_UNAVAILABLE type."""
        # Actual implementation calls route replan
        pass
```

---

## 7. Behavior Scoring Agent

### File: `app/agents/behavior_scorer.py`

```python
class BehaviorScorer:
    """
    Analyzes driver behavior from GPS pings and route assignments.
    Scores driver and generates LLM report.
    """
    
    async def score_driver_day(
        self,
        driver: Driver,
        route_plan: RoutePlan,
        db: Session,
        llm_client
    ) -> DriverBehaviorLog:
        """
        Compute metrics for a driver's day, then generate LLM report.
        """
        
        # Get all GPS pings for this driver today
        gps_pings = db.query(GPSPing).join(Vehicle).filter(
            Vehicle.id == driver.vehicle_id,
            GPSPing.route_plan_id == route_plan.id
        ).order_by(GPSPing.recorded_at).all()
        
        # Get all route legs for this driver today
        route_legs = db.query(RouteLeg).filter(
            RouteLeg.vehicle_id == driver.vehicle_id,
            RouteLeg.route_plan_id == route_plan.id
        ).order_by(RouteLeg.sequence_order).all()
        
        # Compute metrics
        metrics = self._compute_metrics(gps_pings, route_legs, db)
        
        # Generate LLM report
        report = await self._generate_llm_report(driver, metrics, llm_client)
        
        # Compute composite score
        score = self._compute_score(metrics)
        
        # Store in database
        log = DriverBehaviorLog(
            driver_id=driver.id,
            route_plan_id=route_plan.id,
            log_date=date.today(),
            stops_total=metrics["stops_total"],
            stops_on_time=metrics["stops_on_time"],
            stops_late=metrics["stops_late"],
            avg_dwell_min=metrics["avg_dwell_min"],
            route_adherence_pct=metrics["route_adherence_pct"],
            speed_compliance_pct=metrics["speed_compliance_pct"],
            behavior_score=score,
            llm_report=report
        )
        
        db.add(log)
        db.commit()
        
        return log
    
    def _compute_metrics(self, gps_pings, route_legs, db) -> Dict:
        """
        Extract metrics from raw data.
        """
        
        metrics = {
            "stops_total": len(route_legs),
            "stops_on_time": 0,
            "stops_late": 0,
            "avg_dwell_min": 0,
            "route_adherence_pct": 100.0,
            "speed_compliance_pct": 95.0
        }
        
        # Count on-time vs late
        for leg in route_legs:
            if leg.actual_arrived_at:
                planned_eta = leg.sequence_order * 10  # rough estimate
                actual_eta = (leg.actual_arrived_at - route_legs[0].actual_arrived_at).total_seconds() / 60
                
                if actual_eta <= leg.stop.time_window_end:
                    metrics["stops_on_time"] += 1
                else:
                    metrics["stops_late"] += 1
        
        # Average dwell time
        dwells = [leg.actual_dwell_min for leg in route_legs if leg.actual_dwell_min]
        metrics["avg_dwell_min"] = sum(dwells) / len(dwells) if dwells else 0
        
        # Route adherence: % of pings within 50m of planned route
        # (simplified: not implemented fully here)
        
        # Speed compliance: % of pings under speed limit
        for ping in gps_pings:
            if ping.speed_kmh > 60:  # Speed limit
                metrics["speed_compliance_pct"] -= 0.5
        
        return metrics
    
    async def _generate_llm_report(self, driver, metrics, llm_client) -> str:
        """
        Use LLM to generate natural language report.
        """
        
        prompt = f"""
        Generate a brief, professional driver behavior report based on these metrics:
        
        Driver: {driver.name}
        Stops completed: {metrics['stops_total']}
        On-time delivery: {metrics['stops_on_time']} ({metrics['stops_on_time']/metrics['stops_total']*100:.0f}%)
        Late deliveries: {metrics['stops_late']}
        Avg dwell time: {metrics['avg_dwell_min']:.1f} minutes (target: 10 min)
        Route adherence: {metrics['route_adherence_pct']:.0f}%
        Speed compliance: {metrics['speed_compliance_pct']:.0f}%
        
        Provide actionable feedback. Be concise (2-3 sentences).
        """
        
        response = await llm_client.agenerate(prompt)
        return response.text
    
    def _compute_score(self, metrics) -> float:
        """
        Weighted composite score (0–100).
        Weights: on_time=40%, speed=30%, adherence=20%, dwell=10%
        """
        
        on_time_score = (metrics["stops_on_time"] / metrics["stops_total"]) * 100 if metrics["stops_total"] > 0 else 0
        speed_score = metrics["speed_compliance_pct"]
        adherence_score = metrics["route_adherence_pct"]
        dwell_score = max(0, 100 - abs(metrics["avg_dwell_min"] - 10) * 5)
        
        composite = (
            on_time_score * 0.4 +
            speed_score * 0.3 +
            adherence_score * 0.2 +
            dwell_score * 0.1
        )
        
        return min(100, max(0, composite))
```

---

## 8. GPS Simulator

### File: `app/integrations/gps_simulator.py`

```python
class GPSSimulator:
    """
    Simulates drivers moving along planned routes.
    Interpolates position along real road polylines.
    Broadcasts GPS pings via WebSocket.
    """
    
    def __init__(self, distance_service, websocket_manager, db_session):
        self.distance_service = distance_service
        self.ws_manager = websocket_manager
        self.db = db_session
    
    async def start_simulation(self, route_plan: RoutePlan):
        """
        For each vehicle in route_plan:
        1. Get ordered stops (from route_plan.routes_json)
        2. Fetch real road polylines between consecutive stops
        3. Interpolate position every 3 seconds
        4. Emit GPS ping (update db + broadcast via WebSocket)
        5. Check geofence, update ETA
        """
        
        vehicles_routes = {}
        
        for vehicle_id_str, route_info in route_plan.routes_json.items():
            vehicle = self.db.query(Vehicle).filter_by(id=vehicle_id_str).first()
            stops = route_info["stops"]
            
            # Build full polyline for this vehicle's route
            full_polyline = []
            for i in range(len(stops) - 1):
                from_idx = stops[i]
                to_idx = stops[i+1]
                
                # Get real road coords
                segment = await self.distance_service.get_directions(from_idx, to_idx)
                full_polyline.extend(segment)
            
            vehicles_routes[vehicle_id_str] = {
                "vehicle": vehicle,
                "polyline": full_polyline,
                "current_position": 0,  # index in polyline
                "speed_m_per_sec": 15  # 54 km/h average
            }
        
        # Simulation loop
        while True:
            for vehicle_id_str, route_data in vehicles_routes.items():
                polyline = route_data["polyline"]
                current_pos = route_data["current_position"]
                speed = route_data["speed_m_per_sec"]
                
                if current_pos >= len(polyline):
                    continue  # Route completed
                
                # Move along polyline
                next_pos = min(current_pos + speed, len(polyline) - 1)
                lat, lon = polyline[int(next_pos)]
                
                # Create GPS ping
                ping = GPSPing(
                    vehicle_id=route_data["vehicle"].id,
                    route_plan_id=route_plan.id,
                    lat=lat,
                    lon=lon,
                    speed_kmh=speed * 3.6,
                    heading_deg=self._compute_heading(polyline, int(next_pos))
                )
                
                self.db.add(ping)
                
                # Check geofence
                nearest_stop = self._find_nearest_stop(lat, lon, route_plan)
                if nearest_stop and self._is_inside_geofence(lat, lon, nearest_stop):
                    ping.geofence_status = "INSIDE"
                    ping.nearest_stop_id = nearest_stop.id
                
                self.db.commit()
                
                # Broadcast via WebSocket
                await self.ws_manager.broadcast({
                    "type": "gps_ping",
                    "vehicle_id": route_data["vehicle"].id,
                    "lat": lat,
                    "lon": lon,
                    "speed_kmh": speed * 3.6,
                    "timestamp": datetime.now().isoformat()
                })
                
                vehicles_routes[vehicle_id_str]["current_position"] = next_pos
            
            await asyncio.sleep(3)  # Emit every 3 seconds
```

---

This LLD provides the complete technical blueprint for implementing FleetMind.

Each component is designed to be:
- **Testable** — clear inputs, outputs, side effects
- **Scalable** — uses async/await, background tasks, caching
- **Maintainable** — separation of concerns, clear naming
- **Extensible** — easy to add new vehicle types, cost models, disruption types


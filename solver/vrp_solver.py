# solver/vrp_solver.py
from ortools.constraint_solver import routing_enums_pb2, pywrapcp
from typing import List, Optional

def solve_vrp(
    distance_matrix: List[List[int]],
    num_vehicles: int,
    depots: List[int],  # List of depot indices per vehicle
    demands: List[int],
    vehicle_capacities: List[int],
    locked_routes: Optional[dict] = None  # {vehicle_id: [stop_indices]}
) -> dict:
    """
    Core VRP solver. Returns routes per vehicle.
    locked_routes lets us pin some stops to specific drivers
    (used during disruption replanning).
    """
    data = {
        "distance_matrix": distance_matrix,
        "num_vehicles": num_vehicles,
        "depots": depots,
        "demands": demands,
        "vehicle_capacities": vehicle_capacities,
    }

    manager = pywrapcp.RoutingIndexManager(
        len(data["distance_matrix"]),
        data["num_vehicles"],
        data["depots"], # Starts
        data["depots"]  # Ends (vehicles return to their own depot)
    )
    routing = pywrapcp.RoutingModel(manager)

    # Distance callback
    def distance_callback(from_index, to_index):
        from_node = manager.IndexToNode(from_index)
        to_node = manager.IndexToNode(to_index)
        return data["distance_matrix"][from_node][to_node]

    transit_callback_index = routing.RegisterTransitCallback(distance_callback)
    routing.SetArcCostEvaluatorOfAllVehicles(transit_callback_index)

    # Capacity constraint
    def demand_callback(from_index):
        from_node = manager.IndexToNode(from_index)
        return data["demands"][from_node]

    demand_callback_index = routing.RegisterUnaryTransitCallback(demand_callback)
    routing.AddDimensionWithVehicleCapacity(
        demand_callback_index, 0,
        data["vehicle_capacities"],
        True, "Capacity"
    )

    # Lock stops to specific vehicles (for disruption handling)
    if locked_routes:
        for vehicle_id, stops in locked_routes.items():
            for stop in stops:
                routing.SetAllowedVehiclesForIndex(
                    [vehicle_id],
                    manager.NodeToIndex(stop)
                )

    # Search parameters
    search_parameters = pywrapcp.DefaultRoutingSearchParameters()
    search_parameters.first_solution_strategy = (
        routing_enums_pb2.FirstSolutionStrategy.PATH_CHEAPEST_ARC
    )
    search_parameters.local_search_metaheuristic = (
        routing_enums_pb2.LocalSearchMetaheuristic.GUIDED_LOCAL_SEARCH
    )
    search_parameters.time_limit.seconds = 5

    solution = routing.SolveWithParameters(search_parameters)

    if not solution:
        return {"status": "FAILED", "routes": {}}

    routes = {}
    total_distance = 0
    for vehicle_id in range(data["num_vehicles"]):
        index = routing.Start(vehicle_id)
        route = []
        route_distance = 0
        while not routing.IsEnd(index):
            node = manager.IndexToNode(index)
            route.append(node)
            previous_index = index
            index = solution.Value(routing.NextVar(index))
            route_distance += routing.GetArcCostForVehicle(
                previous_index, index, vehicle_id
            )
        route.append(manager.IndexToNode(index))  # back to depot
        routes[vehicle_id] = {
            "stops": route,
            "distance": route_distance
        }
        total_distance += route_distance

    return {
        "status": "SUCCESS",
        "routes": routes,
        "total_distance": total_distance
    }

# if __name__ == "__main__":    
#     # Sample data
#     distance_matrix = [
#         [0, 10, 15, 20],
#         [10, 0, 35, 25],
#         [15, 35, 0, 30],
#         [20, 25, 30, 0],
#     ]

#     num_vehicles = 3
#     depot = 0
#     demands = [0, 1, 1, 2]  # depot needs 0, others need 1-2 units
#     vehicle_capacities = [2, 2,1]  # each vehicle can carry 2 units

#     result = solve_vrp(distance_matrix, num_vehicles, depot, demands, vehicle_capacities)
#     print("Result: " + str(result))
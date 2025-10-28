"""
VRP Solver using Google OR-Tools.
Solves Capacitated Vehicle Routing Problem with Time Windows (CVRPTW).
"""
from ortools.constraint_solver import routing_enums_pb2
from ortools.constraint_solver import pywrapcp
import numpy as np
from typing import List, Tuple
import time as time_module

from ..models.order import Order
from ..models.vehicle import VehicleFleet
from ..models.location import Location, Depot
from ..models.route import Route, RouteStop, RoutingSolution


class VRPSolverError(Exception):
    """Custom exception for VRP solver errors."""
    pass


class VRPSolver:
    """
    Solver for Vehicle Routing Problem with Time Windows and Capacity constraints.

    Uses Google OR-Tools to optimize delivery routes.
    """

    # Service time per location (in minutes)
    SERVICE_TIME = 15

    def __init__(
        self,
        orders: List[Order],
        fleet: VehicleFleet,
        depot: Depot,
        distance_matrix: np.ndarray,
        duration_matrix: np.ndarray,
    ):
        """
        Initialize VRP solver.

        Args:
            orders: List of orders to deliver
            fleet: Vehicle fleet
            depot: Depot location
            distance_matrix: Distance matrix in kilometers
            duration_matrix: Duration matrix in minutes
        """
        self.orders = orders
        self.fleet = fleet
        self.depot = depot
        self.distance_matrix = distance_matrix
        self.duration_matrix = duration_matrix

        # Create locations list: depot + customer locations
        self.locations = [depot] + [
            Location(
                name=order.display_name,
                coordinates=order.coordinates,
                address=order.alamat,
            )
            for order in orders
        ]

        # Validate matrix dimensions
        n_locations = len(self.locations)
        if distance_matrix.shape != (n_locations, n_locations):
            raise VRPSolverError(
                f"Distance matrix shape {distance_matrix.shape} doesn't match "
                f"number of locations {n_locations}"
            )

        # Get all vehicles from fleet
        self.vehicles = fleet.get_all_vehicles()

        # Create a list of unique cities and a mapping from location to city index
        self.cities = sorted(list(set(o.kota for o in orders if o.kota)))
        self.city_map = {city: i for i, city in enumerate(self.cities)}
        self.location_to_city = [-1] + [
            self.city_map.get(o.kota, -1) for o in orders
        ]  # -1 for depot or if city not found

        # Initialize OR-Tools components
        self.manager = None
        self.routing = None
        self.solution = None

    def solve(
        self,
        optimization_strategy: str = "balanced",
        time_limit: int = 300,
    ) -> RoutingSolution:
        """
        Solve the VRP problem.

        Args:
            optimization_strategy: One of "minimize_vehicles", "minimize_cost", "balanced"
            time_limit: Time limit in seconds

        Returns:
            RoutingSolution object

        Raises:
            VRPSolverError: If solving fails
        """
        start_time = time_module.time()

        # Determine number of vehicles to use
        # Start with fixed vehicles, add buffer if unlimited available
        num_vehicles = len(self.vehicles)
        if self.fleet.has_unlimited():
            # Add extra capacity if we have unlimited vehicles
            num_vehicles = min(num_vehicles + len(self.orders), num_vehicles + 50)

        # Create routing index manager
        self.manager = pywrapcp.RoutingIndexManager(
            len(self.locations),  # number of locations
            num_vehicles,  # number of vehicles
            0,  # depot index
        )

        # Create routing model
        self.routing = pywrapcp.RoutingModel(self.manager)

        # Register callbacks and constraints
        self._register_distance_callback()
        self._register_time_callback()
        self._register_demand_callback()

        # Add constraints
        self._add_capacity_constraint()
        self._add_time_window_constraint()
        self._add_city_constraint()

        # Allow dropping nodes (orders) if they can't be satisfied
        # This prevents the solver from failing completely
        penalty = 1000000  # High penalty for dropping orders
        for node in range(1, len(self.locations)):
            self.routing.AddDisjunction([self.manager.NodeToIndex(node)], penalty)

        # Set search parameters
        search_parameters = self._get_search_parameters(
            optimization_strategy, time_limit
        )

        # Solve
        self.solution = self.routing.SolveWithParameters(search_parameters)

        if not self.solution:
            # Get status code for better error message
            status = self.routing.status()
            status_names = {
                0: "ROUTING_NOT_SOLVED",
                1: "ROUTING_SUCCESS",
                2: "ROUTING_FAIL",
                3: "ROUTING_FAIL_TIMEOUT",
                4: "ROUTING_INVALID",
            }
            status_name = status_names.get(status, f"UNKNOWN({status})")

            raise VRPSolverError(
                f"No solution found (Status: {status_name}).\n"
                f"Possible causes:\n"
                f"  - Time window constraints too tight (check delivery_time ranges)\n"
                f"  - Insufficient vehicles (currently using {num_vehicles} vehicles)\n"
                f"  - Distance/time matrix has unreachable locations\n"
                f"  - Capacity constraints impossible to satisfy\n"
                f"Try: Increase time_limit, relax time windows, or check input data."
            )

        # Extract solution
        computation_time = time_module.time() - start_time
        routing_solution = self._extract_solution(
            optimization_strategy, computation_time
        )

        return routing_solution

    def _register_distance_callback(self):
        """Register distance callback for OR-Tools."""

        def distance_callback(from_index, to_index):
            """Returns the distance between two nodes."""
            from_node = self.manager.IndexToNode(from_index)
            to_node = self.manager.IndexToNode(to_index)
            # Convert km to meters for OR-Tools (use integers)
            return int(self.distance_matrix[from_node, to_node] * 1000)

        self.distance_callback_index = self.routing.RegisterTransitCallback(
            distance_callback
        )

        # Set cost of travel (arc cost evaluator)
        self.routing.SetArcCostEvaluatorOfAllVehicles(self.distance_callback_index)

    def _register_time_callback(self):
        """Register time callback for OR-Tools."""

        def time_callback(from_index, to_index):
            """Returns travel time + service time."""
            from_node = self.manager.IndexToNode(from_index)
            to_node = self.manager.IndexToNode(to_index)

            # Travel time in minutes
            travel_time = int(self.duration_matrix[from_node, to_node])

            # Add service time if not returning to depot
            service_time = self.SERVICE_TIME if to_node != 0 else 0

            return travel_time + service_time

        self.time_callback_index = self.routing.RegisterTransitCallback(
            time_callback
        )

    def _register_demand_callback(self):
        """Register demand (weight) callback for OR-Tools."""

        def demand_callback(from_index):
            """Returns the demand (weight) of the node."""
            from_node = self.manager.IndexToNode(from_index)
            if from_node == 0:  # depot
                return 0
            # Convert to grams for integer precision
            return int(self.orders[from_node - 1].load_weight_in_kg * 1000)

        self.demand_callback_index = self.routing.RegisterUnaryTransitCallback(
            demand_callback
        )

    def _add_capacity_constraint(self):
        """Add vehicle capacity constraint."""
        # Get capacities for each vehicle (in grams)
        capacities = [
            int(self.fleet.get_vehicle_by_index(i).capacity * 1000)
            for i in range(self.routing.vehicles())
        ]

        self.routing.AddDimensionWithVehicleCapacity(
            self.demand_callback_index,
            0,  # null capacity slack
            capacities,  # vehicle maximum capacities
            True,  # start cumul to zero
            "Capacity",
        )

    def _add_time_window_constraint(self):
        """Add time window constraint with tolerance for non-priority orders."""
        # Time dimension
        self.routing.AddDimension(
            self.time_callback_index,
            60,  # allow waiting time up to 60 minutes
            1440,  # maximum time per vehicle (24 hours in minutes)
            False,  # don't force start cumul to zero
            "Time",
        )

        time_dimension = self.routing.GetDimensionOrDie("Time")

        # Add time window constraints for each location
        for loc_idx, order in enumerate(self.orders):
            index = self.manager.NodeToIndex(loc_idx + 1)  # +1 because depot is 0

            time_window_start = order.time_window_start
            time_window_end = order.time_window_end

            # Apply tolerance based on priority
            if order.is_priority:
                # Priority orders: strict time window (no tolerance)
                tolerance = self.fleet.priority_time_tolerance
            else:
                # Non-priority orders: allow up to 20 minutes late
                tolerance = self.fleet.non_priority_time_tolerance

            # Adjust time window end with tolerance
            time_window_end_adjusted = time_window_end + tolerance

            if self.fleet.relax_time_windows:
                time_window_end_adjusted += self.fleet.time_window_relaxation_minutes

            time_dimension.CumulVar(index).SetRange(
                time_window_start, time_window_end_adjusted
            )

        # Set time windows for depot (always available)
        depot_index = self.manager.NodeToIndex(0)
        time_dimension.CumulVar(depot_index).SetRange(0, 1440)

        # Minimize the time of the routes
        for i in range(self.routing.vehicles()):
            self.routing.AddVariableMinimizedByFinalizer(
                time_dimension.CumulVar(self.routing.Start(i))
            )

    def _add_city_constraint(self):
        """Add constraint to limit the number of cities per vehicle to 2."""
        num_cities = len(self.cities)
        if num_cities == 0:
            return

        solver = self.routing.solver()

        for vehicle_id in range(self.routing.vehicles()):
            cities_visited_for_vehicle = []
            for city_index in range(num_cities):
                nodes_in_city = [
                    self.manager.NodeToIndex(loc_idx)
                    for loc_idx, loc_city_index in enumerate(self.location_to_city)
                    if loc_city_index == city_index
                ]

                if not nodes_in_city:
                    continue

                node_visited_by_vehicle_vars = []
                for node in nodes_in_city:
                    is_node_visited_by_vehicle = solver.BoolVar(f"node_{node}_visited_by_vehicle_{vehicle_id}")
                    
                    # is_node_visited_by_vehicle = ActiveVar(node) AND (VehicleVar(node) == vehicle_id)
                    # We can use multiplication for AND since they are 0/1 variables.
                    solver.Add(
                        is_node_visited_by_vehicle == self.routing.ActiveVar(node) * (self.routing.VehicleVar(node) == vehicle_id)
                    )
                    node_visited_by_vehicle_vars.append(is_node_visited_by_vehicle)

                is_city_visited = solver.BoolVar(f"city_{city_index}_visited_by_vehicle_{vehicle_id}")
                # is_city_visited = OR(node_visited_by_vehicle_vars)
                # This is equivalent to Max(node_visited_by_vehicle_vars)
                solver.Add(is_city_visited == solver.Max(node_visited_by_vehicle_vars))
                cities_visited_for_vehicle.append(is_city_visited)

            if cities_visited_for_vehicle:
                solver.Add(solver.Sum(cities_visited_for_vehicle) <= 2)

    def _get_search_parameters(
        self, optimization_strategy: str, time_limit: int
    ) -> pywrapcp.DefaultRoutingSearchParameters:
        """
        Get search parameters for OR-Tools.

        Args:
            optimization_strategy: Optimization strategy
            time_limit: Time limit in seconds

        Returns:
            Search parameters
        """
        search_parameters = pywrapcp.DefaultRoutingSearchParameters()

        # Set time limit
        search_parameters.time_limit.seconds = time_limit

        # Set first solution strategy
        # PARALLEL_CHEAPEST_INSERTION is more robust for problems with time windows
        search_parameters.first_solution_strategy = (
            routing_enums_pb2.FirstSolutionStrategy.PARALLEL_CHEAPEST_INSERTION
        )

        # Set local search metaheuristic
        if optimization_strategy == "minimize_vehicles":
            # Guided local search - good for minimizing vehicles
            search_parameters.local_search_metaheuristic = (
                routing_enums_pb2.LocalSearchMetaheuristic.GUIDED_LOCAL_SEARCH
            )
        elif optimization_strategy == "minimize_cost":
            # Simulated annealing - good for cost optimization
            search_parameters.local_search_metaheuristic = (
                routing_enums_pb2.LocalSearchMetaheuristic.SIMULATED_ANNEALING
            )
        else:  # balanced
            # Automatic - let OR-Tools decide
            search_parameters.local_search_metaheuristic = (
                routing_enums_pb2.LocalSearchMetaheuristic.AUTOMATIC
            )

        # Enable logging for debugging (can be disabled in production)
        search_parameters.log_search = True

        return search_parameters

    def _extract_solution(
        self, optimization_strategy: str, computation_time: float
    ) -> RoutingSolution:
        """
        Extract solution from OR-Tools solver.

        Args:
            optimization_strategy: Optimization strategy used
            computation_time: Time taken to compute solution

        Returns:
            RoutingSolution object
        """
        routes = []
        time_dimension = self.routing.GetDimensionOrDie("Time")

        # Extract routes for each vehicle
        for vehicle_id in range(self.routing.vehicles()):
            route = self._extract_vehicle_route(vehicle_id, time_dimension)
            if route.num_stops > 0:  # Only add routes with stops
                routes.append(route)

        # Check for unassigned orders
        unassigned_orders = []
        for node in range(1, len(self.locations)):  # Skip depot (node 0)
            index = self.manager.NodeToIndex(node)
            if self.routing.IsStart(index) or self.routing.IsEnd(index):
                continue
            if self.solution.Value(self.routing.NextVar(index)) == index:
                unassigned_orders.append(self.orders[node - 1])

        # Create solution
        solution = RoutingSolution(
            routes=routes,
            unassigned_orders=unassigned_orders,
            optimization_strategy=optimization_strategy,
            computation_time=computation_time,
        )

        return solution

    def _extract_vehicle_route(
        self, vehicle_id: int, time_dimension
    ) -> Route:
        """
        Extract route for a specific vehicle.

        Args:
            vehicle_id: Vehicle ID
            time_dimension: Time dimension from OR-Tools

        Returns:
            Route object
        """
        vehicle = self.fleet.get_vehicle_by_index(vehicle_id)
        route = Route(vehicle=vehicle)

        index = self.routing.Start(vehicle_id)
        sequence = 0
        cumulative_weight = 0
        prev_node = 0

        while not self.routing.IsEnd(index):
            node = self.manager.IndexToNode(index)
            time_var = time_dimension.CumulVar(index)
            arrival_time = self.solution.Min(time_var)

            if node != 0:  # Skip depot
                order = self.orders[node - 1]
                cumulative_weight += order.load_weight_in_kg

                # Calculate distance from previous stop
                distance_from_prev = self.distance_matrix[prev_node, node]

                # Create route stop
                stop = RouteStop(
                    order=order,
                    arrival_time=arrival_time,
                    departure_time=arrival_time + self.SERVICE_TIME,
                    distance_from_prev=distance_from_prev,
                    cumulative_weight=cumulative_weight,
                    sequence=sequence,
                )

                route.add_stop(stop)
                sequence += 1

            prev_node = node
            index = self.solution.Value(self.routing.NextVar(index))

        # Add return distance to depot
        if route.num_stops > 0:
            last_node = self.manager.IndexToNode(
                self.solution.Value(
                    self.routing.NextVar(
                        self.manager.NodeToIndex(prev_node)
                    )
                )
            )
            # Since last_node should be the end node, we use prev_node to get back to depot
            return_distance = self.distance_matrix[prev_node, 0]
            route.total_distance = sum(
                stop.distance_from_prev for stop in route.stops
            ) + return_distance

            # Set departure time (earliest order time - 30 minutes)
            if route.stops:
                earliest_time = min(stop.order.time_window_start for stop in route.stops)
                route.departure_time = max(0, earliest_time - 30)

        # Calculate metrics
        route.calculate_metrics()

        return route

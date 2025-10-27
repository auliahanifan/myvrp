# 🚚 Segarloka VRP Solver

A Vehicle Routing Problem (VRP) solver for optimizing delivery routes for Segarloka's vegetable delivery service. Built with Google OR-Tools, this application handles capacity constraints, time windows, and multiple optimization strategies.

## ✅ Phase 1 - COMPLETED

All Phase 1 components have been successfully implemented:

### 📦 Project Structure

```
seg-vrp/
├── src/
│   ├── models/              # Data models
│   │   ├── order.py        # Order model with time windows
│   │   ├── vehicle.py      # Vehicle and fleet models
│   │   ├── route.py        # Route and solution models
│   │   └── location.py     # Location and depot models
│   ├── solver/             # VRP solver logic
│   │   └── vrp_solver.py   # OR-Tools CVRPTW implementation
│   ├── utils/              # Helper utilities
│   │   ├── csv_parser.py   # CSV order data parser
│   │   ├── yaml_parser.py  # YAML vehicle config parser
│   │   └── distance_calculator.py  # OSRM API integration
│   ├── output/             # Excel output generator (Phase 2)
│   └── config/             # Configuration files
├── example/
│   ├── example_input.csv           # Sample order data
│   └── example_input_vehicle.yaml  # Sample vehicle config
├── results/                # Output Excel files
├── tests/                  # Unit tests
├── .env.example           # Environment variables template
├── pyproject.toml         # Project configuration
└── requirements.txt       # Python dependencies
```

### 🎯 Features Implemented

#### 1.1 Project Setup ✅
- Python project with `pyproject.toml` and `requirements.txt`
- Dependencies: OR-Tools, Pandas, NumPy, openpyxl, PyYAML, requests, streamlit
- Complete folder structure with all required directories

#### 1.2 Data Models ✅
- **Order Model** (`src/models/order.py`)
  - Full order information with validation
  - Time window properties (start, end, departure time)
  - Coordinate validation
  - Priority order support

- **Vehicle Model** (`src/models/vehicle.py`)
  - Vehicle type definition with capacity and cost
  - Vehicle fleet management
  - Unlimited fleet support with auto-cloning

- **Route Model** (`src/models/route.py`)
  - Route stop with arrival/departure times
  - Route with vehicle assignment and stops
  - Complete solution with multiple routes
  - Validation for capacity and time windows

- **Location Model** (`src/models/location.py`)
  - Location with coordinates
  - Depot as special location type

#### 1.3 Input Parsers ✅
- **CSV Parser** (`src/utils/csv_parser.py`)
  - Parses order CSV files with all required columns
  - Validates coordinates, weights, dates, times
  - Handles priority orders
  - Comprehensive error reporting

- **YAML Parser** (`src/utils/yaml_parser.py`)
  - Parses vehicle configuration YAML
  - Validates vehicle specs (capacity, cost)
  - Supports unlimited fleet configuration

#### 1.4 OSRM API Integration ✅
- **Distance Calculator** (`src/utils/distance_calculator.py`)
  - OSRM Distance Matrix API client
  - Calculates distance and duration matrices
  - Intelligent caching to minimize API calls
  - Comprehensive error handling

#### 1.5 VRP Solver (OR-Tools) ✅
- **CVRPTW Solver** (`src/solver/vrp_solver.py`)
  - Capacitated VRP with Time Windows
  - **Capacity constraint**: Enforces vehicle max capacity
  - **Time window constraint**: HARD constraint (must be met)
  - **Service time**: 15 minutes per location
  - **Departure time**: 30 minutes before earliest delivery
  - **Depot constraint**: All routes start/end at depot
  - **3 optimization strategies**:
    - `minimize_vehicles`: Minimize number of vehicles used
    - `minimize_cost`: Minimize total cost (distance × cost_per_km)
    - `balanced`: Balance between vehicles and cost
  - **Unlimited vehicle fleet**: Auto-adds vehicles as needed
  - Complete solution extraction with route details

## 🚀 Quick Start

### 1. Setup Environment

```bash
# Install dependencies using uv (recommended)
uv pip install -r requirements.txt

# Or sync from pyproject.toml
uv sync

# Configure environment
cp .env.example .env
```

### 2. Prepare Input Files

**Order CSV** (`example/example_input.csv`):
```csv
sale_order_id,delivery_date,delivery_time,load_weight_in_kg,partner_id,display_name,alamat,coordinates,is_priority
SO001,2025-10-10,08:00,25.5,C001,Toko Segar Jaya,Jl. Sudirman No. 123,-6.2088,106.8456,0
```

**Vehicle YAML** (`example/example_input_vehicle.yaml`):
```yaml
vehicles:
  - name: "L300"
    capacity: 800  # kg
    cost_per_km: 5000  # Rupiah
unlimited: true
```

### 3. Run Solver (Coming in Phase 3)

```python
from src.utils.csv_parser import CSVParser
from src.utils.yaml_parser import YAMLParser
from src.utils.distance_calculator import DistanceCalculator
from src.solver.vrp_solver import VRPSolver
from src.models.location import Depot

# Parse inputs
orders = CSVParser("example/example_input.csv").parse()
fleet = YAMLParser("example/example_input_vehicle.yaml").parse()

# Setup depot
depot = Depot("Segarloka Warehouse", (-6.2088, 106.8456))

# Calculate distances
calculator = DistanceCalculator()
locations = [depot] + [order to Location for each order]
distance_matrix, duration_matrix = calculator.calculate_matrix(locations)

# Solve VRP
solver = VRPSolver(orders, fleet, depot, distance_matrix, duration_matrix)
solution = solver.solve(optimization_strategy="balanced", time_limit=300)

# View results
print(solution)
```

## 📋 Next Steps - Phase 2

Phase 2 will implement the Excel output generator:
- Generate routes by vehicle sheet
- Generate summary sheet
- Color coding for priority orders
- Professional formatting

## 🔧 Technical Details

### Constraints
- **Capacity**: HARD - Vehicle capacity cannot be exceeded
- **Time Windows**: HARD - Must arrive at exact delivery time
- **Service Time**: 15 minutes per stop for unloading
- **Depot**: All vehicles start and end at depot

### Optimization Strategies
1. **Minimize Vehicles**: Reduces fleet size (uses Guided Local Search)
2. **Minimize Cost**: Reduces total distance/cost (uses Simulated Annealing)
3. **Balanced**: Balances both objectives (uses Automatic metaheuristic)

### API Integration
- OSRM Distance Matrix API for accurate distances
- Caching system to minimize API calls and costs

## 📝 Environment Variables

Required in `.env` file:

```env
DEPOT_LATITUDE=-6.2088
DEPOT_LONGITUDE=106.8456
DEPOT_NAME=Segarloka Warehouse
```

## 🧪 Testing

Testing suite will be implemented in Phase 4.

## 📄 License

Proprietary - Segarloka Internal Use Only

## 👥 Contributors

- Segarloka Development Team

---

**Status**: Phase 1 Complete ✅ | Ready for Phase 2 Development

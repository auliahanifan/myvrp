# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

Segarloka VRP Solver - A Vehicle Routing Problem solver for optimizing vegetable delivery routes. Uses Google OR-Tools to solve Capacitated VRP with Time Windows (CVRPTW), supporting two-tier hub-based consolidation routing.

## Commands

```bash
# Install dependencies
uv sync

# Run the Streamlit web app
uv run streamlit run app.py

# Run tests
uv run pytest tests/

# Run a specific test file
uv run pytest tests/unit/test_order.py -v

# Run tests with coverage
uv run pytest --cov=src tests/

# Docker build and run
./docker_run.sh
```

## Architecture

### Two-Tier Routing System

The solver implements a two-tier hub-based delivery strategy:

1. **Tier 1 (Blind Van)**: Bulk consolidation from DEPOT to HUB (05:30-06:00)
2. **Tier 2a (Motors from HUB)**: Hub-zone orders served from HUB
3. **Tier 2b (Motors from DEPOT)**: Direct-zone orders served from DEPOT

Orders are classified by zone (configured in `conf.yaml` under `hub.zones_via_hub`).

### Key Modules

- **`src/solver/vrp_solver.py`**: Core OR-Tools CVRPTW solver with capacity, time windows, and optimization strategies
- **`src/solver/two_tier_vrp_solver.py`**: Orchestrates two-tier routing, coordinating Blind Van consolidation and motor deliveries
- **`src/utils/distance_calculator.py`**: OSRM API integration for distance/duration matrices
- **`src/utils/hub_routing.py`**: Zone classification and hub order management
- **`app.py`**: Streamlit web interface for the operations team

### Data Models

- **Order** (`src/models/order.py`): Delivery with time windows, coordinates, weight, priority
- **Vehicle/VehicleFleet** (`src/models/vehicle.py`): Vehicle types with capacity, cost, fleet management
- **Route/RoutingSolution** (`src/models/route.py`): Route stops with arrival/departure times
- **Location/Depot/Hub** (`src/models/location.py`): Geographic locations

### Configuration

- **`conf.yaml`**: Vehicle fleet, routing constraints, solver parameters, hub configuration
- **`.env`**: Depot coordinates (see `.env.example`)

## Constraints

- **Capacity**: HARD - Vehicle capacity cannot be exceeded
- **Time Windows**: Configurable (HARD for priority, soft for non-priority with tolerance)
- **Service Time**: 15 minutes per stop
- **Return to Depot**: Configurable in `conf.yaml`

## Coding Rules

1. Always use `uv` for dependency management
2. Keep it simple

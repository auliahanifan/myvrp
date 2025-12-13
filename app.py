"""
Streamlit Web Interface for Segarloka VRP Solver

This is the main web application that provides a user-friendly interface
for the operations team to upload orders, configure routing parameters,
and download optimized routing results.
"""

import os
import streamlit as st
import pandas as pd
from pathlib import Path
from datetime import datetime
from dotenv import load_dotenv
import tempfile
import io
from streamlit_folium import st_folium
import streamlit.components.v1 as components

# Load environment variables
load_dotenv()

# Import project modules
from src.models.location import Depot, Location, Hub
from src.models.order import Order
from src.models.vehicle import Vehicle, VehicleFleet
from src.models.hub_config import MultiHubConfig, HubConfig
from src.utils.csv_parser import CSVParser
from src.utils.yaml_parser import YAMLParser
from src.utils.distance_calculator import DistanceCalculator
from src.utils.hub_routing import MultiHubRoutingManager
from src.solver.two_tier_vrp_solver import MultiHubVRPSolver
from src.output.excel_generator import ExcelGenerator
from src.output.csv_generator import CSVGenerator
from src.visualization.map_visualizer import MapVisualizer


# Page configuration
st.set_page_config(
    page_title="Segarloka VRP Solver",
    page_icon="🚚",
    layout="wide",
    initial_sidebar_state="expanded",
)


# Custom CSS for better styling
st.markdown("""
    <style>
    .main-header {
        font-size: 2.5rem;
        font-weight: bold;
        color: #366092;
        margin-bottom: 0.5rem;
    }
    .sub-header {
        font-size: 1.2rem;
        color: #666;
        margin-bottom: 2rem;
    }
    .metric-card {
        background-color: #f0f2f6;
        padding: 1rem;
        border-radius: 0.5rem;
        border-left: 4px solid #366092;
    }
    .success-box {
        background-color: #d4edda;
        border: 1px solid #c3e6cb;
        border-radius: 0.5rem;
        padding: 1rem;
        margin: 1rem 0;
    }
    .error-box {
        background-color: #f8d7da;
        border: 1px solid #f5c6cb;
        border-radius: 0.5rem;
        padding: 1rem;
        margin: 1rem 0;
    }
    .info-box {
        background-color: #d1ecf1;
        border: 1px solid #bee5eb;
        border-radius: 0.5rem;
        padding: 1rem;
        margin: 1rem 0;
    }
    </style>
""", unsafe_allow_html=True)


def initialize_session_state():
    """Initialize session state variables"""
    if 'orders' not in st.session_state:
        st.session_state.orders = None
    if 'fleet' not in st.session_state:
        st.session_state.fleet = None
    if 'solution' not in st.session_state:
        st.session_state.solution = None
    if 'excel_path' not in st.session_state:
        st.session_state.excel_path = None
    if 'csv_path' not in st.session_state:
        st.session_state.csv_path = None
    if 'csv_summary_path' not in st.session_state:
        st.session_state.csv_summary_path = None
    if 'depot' not in st.session_state:
        st.session_state.depot = None
    # Multi-hub support
    if 'hubs_config' not in st.session_state:
        st.session_state.hubs_config = None  # MultiHubConfig object
    if 'hub_routing_manager' not in st.session_state:
        st.session_state.hub_routing_manager = None  # MultiHubRoutingManager
    if 'map_html_cache' not in st.session_state:
        st.session_state.map_html_cache = {}  # Cache map HTML by route filter
    if 'rate_overrides' not in st.session_state:
        st.session_state.rate_overrides = {}  # {vehicle_name: rate_per_km}


def get_depot_from_env():
    """Load depot configuration from environment variables"""
    depot_lat = float(os.getenv("DEPOT_LATITUDE", "-6.2088"))
    depot_lon = float(os.getenv("DEPOT_LONGITUDE", "106.8456"))
    depot_name = os.getenv("DEPOT_NAME", "Segarloka Warehouse")
    depot_address = os.getenv("DEPOT_ADDRESS", "Jakarta, Indonesia")

    return Depot(
        name=depot_name,
        coordinates=(depot_lat, depot_lon),
        address=depot_address
    )


def get_hubs_from_yaml() -> MultiHubConfig:
    """Load multi-hub configuration from conf.yaml"""
    try:
        parser = YAMLParser("conf.yaml")
        parser.parse()  # Load data first
        hubs_config = parser.get_hubs_config()
        return hubs_config
    except Exception as e:
        st.warning(f"⚠️ Could not load hub configuration: {str(e)}")
        return MultiHubConfig(enabled=False)


def render_header():
    """Render the application header"""
    st.markdown('<p class="main-header">🚚 Segarloka VRP Solver</p>', unsafe_allow_html=True)
    st.markdown('<p class="sub-header">Optimasi Routing Pengiriman Sayur dengan OR-Tools</p>', unsafe_allow_html=True)
    st.markdown("---")


def render_upload_section():
    """Render the file upload section"""
    st.header("📤 1. Upload Data")

    col1, col2 = st.columns(2)

    with col1:
        st.subheader("Order CSV File")
        csv_file = st.file_uploader(
            "Upload file CSV dengan data order harian",
            type=['csv'],
            help="Format CSV harus sesuai template: sale_order_id, delivery_date, delivery_time, load_weight_in_kg, partner_id, display_name, alamat, coordinates, is_priority"
        )

        if csv_file is not None:
            try:
                # Save to temporary file
                with tempfile.NamedTemporaryFile(delete=False, suffix='.csv', mode='wb') as tmp_file:
                    tmp_file.write(csv_file.getvalue())
                    tmp_path = tmp_file.name

                # Parse CSV
                parser = CSVParser(tmp_path)
                orders = parser.parse()
                st.session_state.orders = orders

                # Clean up temp file
                os.unlink(tmp_path)

                # Show success message
                st.markdown(
                    f'<div class="success-box">✅ Berhasil memuat {len(orders)} orders</div>',
                    unsafe_allow_html=True
                )

                # Preview data
                st.subheader("Preview Data (10 rows pertama)")
                df = pd.read_csv(io.StringIO(csv_file.getvalue().decode('utf-8')))
                st.dataframe(df.head(10), width=1000)

                # Show statistics
                total_weight = sum(o.load_weight_in_kg for o in orders)
                priority_count = sum(1 for o in orders if o.is_priority)

                col1_stat, col2_stat, col3_stat = st.columns(3)
                with col1_stat:
                    st.metric("Total Orders", len(orders))
                with col2_stat:
                    st.metric("Total Berat", f"{total_weight:.1f} kg")
                with col3_stat:
                    st.metric("Priority Orders", priority_count)

            except Exception as e:
                st.markdown(
                    f'<div class="error-box">❌ Error parsing CSV: {str(e)}</div>',
                    unsafe_allow_html=True
                )
                st.session_state.orders = None

    with col2:
        st.subheader("Vehicle Configuration YAML")

        # Option to use default or upload custom
        use_default = st.checkbox("Gunakan konfigurasi vehicle default", value=True)

        if use_default:
            default_yaml_path = "conf.yaml"
            if os.path.exists(default_yaml_path):
                try:
                    parser = YAMLParser(default_yaml_path)
                    fleet = parser.parse()
                    st.session_state.fleet = fleet

                    st.markdown(
                        f'<div class="success-box">✅ Menggunakan konfigurasi default</div>',
                        unsafe_allow_html=True
                    )

                    # Display vehicle types
                    st.subheader("Tipe Kendaraan")
                    for vehicle_type, count, unlimited in fleet.vehicle_types:
                        unlimited_str = " (+ unlimited on-demand)" if unlimited else ""
                        st.write(f"**{vehicle_type.name}**: {vehicle_type.capacity} kg @ Rp {vehicle_type.cost_per_km:,}/km × {count} unit{unlimited_str}")

                    st.write(f"**Total fixed vehicles**: {fleet.get_max_vehicles()} units")

                    # Display routing config
                    st.subheader("Routing Configuration")
                    st.write(f"**Return to depot**: {'Yes' if fleet.return_to_depot else 'No'}")
                    st.write(f"**Priority time tolerance**: {fleet.priority_time_tolerance} min")
                    st.write(f"**Non-priority time tolerance**: {fleet.non_priority_time_tolerance} min")
                    st.write(f"**Multiple trips**: {'Yes' if fleet.multiple_trips else 'No'}")

                except Exception as e:
                    st.markdown(
                        f'<div class="error-box">❌ Error loading default config: {str(e)}</div>',
                        unsafe_allow_html=True
                    )
        else:
            yaml_file = st.file_uploader(
                "Upload file YAML konfigurasi vehicle",
                type=['yaml', 'yml'],
                help="Format YAML dengan vehicles list (name, capacity, cost_per_km)"
            )

            if yaml_file is not None:
                try:
                    # Save to temporary file
                    with tempfile.NamedTemporaryFile(delete=False, suffix='.yaml', mode='wb') as tmp_file:
                        tmp_file.write(yaml_file.getvalue())
                        tmp_path = tmp_file.name

                    # Parse YAML
                    parser = YAMLParser(tmp_path)
                    fleet = parser.parse()
                    st.session_state.fleet = fleet

                    # Clean up temp file
                    os.unlink(tmp_path)

                    st.markdown(
                        '<div class="success-box">✅ Konfigurasi vehicle berhasil dimuat</div>',
                        unsafe_allow_html=True
                    )

                    # Display vehicle types
                    st.subheader("Tipe Kendaraan")
                    for vehicle_type, count, unlimited in fleet.vehicle_types:
                        unlimited_str = " (+ unlimited on-demand)" if unlimited else ""
                        st.write(f"**{vehicle_type.name}**: {vehicle_type.capacity} kg @ Rp {vehicle_type.cost_per_km:,}/km × {count} unit{unlimited_str}")

                    st.write(f"**Total fixed vehicles**: {fleet.get_max_vehicles()} units")

                    # Display routing config
                    st.subheader("Routing Configuration")
                    st.write(f"**Return to depot**: {'Yes' if fleet.return_to_depot else 'No'}")
                    st.write(f"**Priority time tolerance**: {fleet.priority_time_tolerance} min")
                    st.write(f"**Non-priority time tolerance**: {fleet.non_priority_time_tolerance} min")
                    st.write(f"**Multiple trips**: {'Yes' if fleet.multiple_trips else 'No'}")

                except Exception as e:
                    st.markdown(
                        f'<div class="error-box">❌ Error parsing YAML: {str(e)}</div>',
                        unsafe_allow_html=True
                    )
                    st.session_state.fleet = None


def render_configuration_section():
    """Render the configuration section"""
    st.header("⚙️ 2. Konfigurasi Routing")

    col1, col2 = st.columns(2)

    with col1:
        st.subheader("Strategi Optimasi")

        optimization_strategy = st.radio(
            "Pilih strategi optimasi:",
            options=["minimize_vehicles", "minimize_cost", "balanced"],
            format_func=lambda x: {
                "minimize_vehicles": "⚙️ Minimize Vehicles - Kurangi jumlah kendaraan (route lebih panjang)",
                "minimize_cost": "💰 Minimize Cost - Kurangi total biaya (lebih banyak kendaraan)",
                "balanced": "⚖️ Balanced - Seimbang antara jumlah kendaraan dan biaya"
            }[x],
            index=2  # Default to balanced
        )

        st.markdown(
            '<div class="info-box"><strong>ℹ️ Rekomendasi:</strong><br>'
            '• Gunakan <strong>Minimize Vehicles</strong> jika driver terbatas<br>'
            '• Gunakan <strong>Minimize Cost</strong> jika driver banyak tersedia<br>'
            '• Gunakan <strong>Balanced</strong> untuk hasil optimal umum</div>',
            unsafe_allow_html=True
        )

        time_limit = st.slider(
            "Time Limit (detik)",
            min_value=60,
            max_value=600,
            value=60,
            step=30,
            help="Maksimal waktu untuk solver mencari solusi optimal"
        )

    with col2:
        st.subheader("Lokasi Depot & Hubs")

        depot = get_depot_from_env()
        st.session_state.depot = depot

        st.write(f"**Depot - Nama:** {depot.name}")
        st.write(f"**Depot - Alamat:** {depot.address}")
        st.write(f"**Depot - Koordinat:** {depot.coordinates[0]:.6f}, {depot.coordinates[1]:.6f}")

        # Load and display multi-hub configuration
        hubs_config = get_hubs_from_yaml()
        st.session_state.hubs_config = hubs_config

        st.markdown("---")

        if hubs_config.is_zero_hub_mode:
            st.markdown(
                '<div class="info-box">📦 Zero Hub Mode: All orders routed directly from DEPOT</div>',
                unsafe_allow_html=True
            )
        else:
            st.markdown(
                f'<div class="info-box">✅ Multi-Hub Mode: {hubs_config.num_hubs} hub(s) configured</div>',
                unsafe_allow_html=True
            )

            # Display each hub
            for hub_cfg in hubs_config.hubs:
                with st.expander(f"📦 {hub_cfg.hub.name} ({hub_cfg.hub_id})"):
                    st.write(f"**Alamat:** {hub_cfg.hub.address}")
                    st.write(f"**Koordinat:** {hub_cfg.hub.coordinates[0]:.6f}, {hub_cfg.hub.coordinates[1]:.6f}")
                    st.write(f"**Zones:** {', '.join(hub_cfg.zones_via_hub) if hub_cfg.zones_via_hub else 'None'}")

            # Schedule info
            st.write(f"**Blind Van Depart:** {hubs_config.blind_van_departure} min")
            st.write(f"**Blind Van Arrival:** {hubs_config.blind_van_arrival} min")
            st.write(f"**Motor Start:** {hubs_config.motor_start_time} min")
            st.write(f"**Unassigned Zone Behavior:** {hubs_config.unassigned_zone_behavior}")

    return optimization_strategy, time_limit


def apply_rate_overrides(fleet: VehicleFleet, rate_overrides: dict) -> VehicleFleet:
    """
    Create a new VehicleFleet with overridden cost_per_km values.

    Args:
        fleet: Original VehicleFleet
        rate_overrides: Dict of {vehicle_name: new_rate}

    Returns:
        New VehicleFleet with updated rates
    """
    if not rate_overrides:
        return fleet

    new_vehicle_types = []
    for vehicle_type, count, unlimited in fleet.vehicle_types:
        new_rate = rate_overrides.get(vehicle_type.name, vehicle_type.cost_per_km)

        # Create new Vehicle with overridden rate
        new_vehicle = Vehicle(
            name=vehicle_type.name,
            capacity=vehicle_type.capacity,
            cost_per_km=new_rate,
            fixed_cost=new_rate * 10,  # Match calculation from yaml_parser.py
        )
        new_vehicle_types.append((new_vehicle, count, unlimited))

    # Create new fleet with same settings but updated vehicles
    return VehicleFleet(
        vehicle_types=new_vehicle_types,
        return_to_depot=fleet.return_to_depot,
        priority_time_tolerance=fleet.priority_time_tolerance,
        non_priority_time_tolerance=fleet.non_priority_time_tolerance,
        multiple_trips=fleet.multiple_trips,
        relax_time_windows=fleet.relax_time_windows,
        time_window_relaxation_minutes=fleet.time_window_relaxation_minutes,
    )


def render_processing_section(optimization_strategy, time_limit):
    """Render the processing section with generate button"""
    st.header("🔄 3. Generate Routes")

    # Check if all prerequisites are met
    can_generate = (
        st.session_state.orders is not None and
        st.session_state.fleet is not None and
        st.session_state.depot is not None
    )

    if not can_generate:
        st.warning("⚠️ Harap upload CSV orders dan konfigurasi vehicle terlebih dahulu")
        return

    # Generate button
    if st.button("🚀 Generate Routing Optimal", type="primary", width="stretch"):
        try:
            # Progress tracking
            progress_bar = st.progress(0)
            status_text = st.empty()

            # Step 1: Prepare data
            status_text.text("📋 Mempersiapkan data...")
            progress_bar.progress(10)

            orders = st.session_state.orders
            fleet = st.session_state.fleet
            depot = st.session_state.depot
            hubs_config = st.session_state.hubs_config

            # Apply rate overrides if configured
            if st.session_state.get('rate_overrides'):
                fleet = apply_rate_overrides(fleet, st.session_state.rate_overrides)

            # Create MultiHubRoutingManager
            hub_routing_manager = MultiHubRoutingManager(hubs_config, depot)
            st.session_state.hub_routing_manager = hub_routing_manager

            # Display hub routing summary
            if not hubs_config.is_zero_hub_mode:
                try:
                    summary = hub_routing_manager.get_routing_summary(orders)
                    with st.expander("📊 Multi-Hub Routing Summary"):
                        col_summary1, col_summary2, col_summary3 = st.columns(3)
                        with col_summary1:
                            st.metric("Hub Orders", summary.get("total_hub_orders", 0))
                        with col_summary2:
                            st.metric("Direct Orders", summary.get("direct_orders_count", 0))
                        with col_summary3:
                            st.metric("Hub %", f"{summary.get('hub_percentage', 0):.1f}%")

                        col_weight1, col_weight2 = st.columns(2)
                        with col_weight1:
                            st.metric("Hub Weight (kg)", f"{summary.get('total_hub_weight_kg', 0):.1f}")
                        with col_weight2:
                            st.metric("Direct Weight (kg)", f"{summary.get('direct_weight_kg', 0):.1f}")

                        # Per-hub breakdown
                        if summary.get("hub_breakdown"):
                            st.markdown("**Per-Hub Breakdown:**")
                            for hub_id, hub_info in summary["hub_breakdown"].items():
                                st.write(f"- {hub_info['name']}: {hub_info['count']} orders, {hub_info['weight_kg']:.1f} kg")

                except Exception as e:
                    st.warning(f"⚠️ Hub routing summary failed: {str(e)}")

            # Create locations list
            # Multi-hub: [DEPOT, HUB_1, HUB_2, ..., customer_1, customer_2, ...]
            # Zero-hub: [DEPOT, customer_1, customer_2, ...]
            locations = [depot]

            # Add all hubs to locations list
            if not hubs_config.is_zero_hub_mode:
                for hub_cfg in hubs_config.hubs:
                    locations.append(hub_cfg.hub)

            # Add all customer locations
            locations.extend([
                Location(o.display_name, o.coordinates, o.alamat)
                for o in orders
            ])

            # Step 2: Calculate distance matrix with cache
            status_text.text("🗺️ Menghitung distance matrix via OSRM API...")
            progress_bar.progress(20)

            # Get cache config from YAML
            parser = YAMLParser("conf.yaml")
            parser.parse()  # Load data
            cache_config = parser.get_cache_config()

            calculator = DistanceCalculator(
                cache_dir=cache_config.get("directory", ".cache"),
                cache_ttl_hours=cache_config.get("ttl_hours", 24),
                enable_cache=cache_config.get("enabled", True)
            )

            with st.spinner("Fetching distances from OSRM (with cache)..."):
                distance_matrix, duration_matrix = calculator.calculate_matrix(locations)

            # Show cache statistics
            cache_stats = calculator.get_cache_stats()
            if cache_stats["cache_hits"] > 0:
                status_text.text(f"✅ Distance matrix loaded (🔥 cache hit! Saved {cache_stats['api_calls']} API calls)")
            else:
                status_text.text(f"✅ Distance matrix calculated ({len(locations)}x{len(locations)} locations, cached for reuse)")

            progress_bar.progress(40)

            # Step 3: Solve VRP using Multi-Hub Routing
            status_text.text(f"🧮 Solving VRP dengan strategi: {optimization_strategy}...")
            progress_bar.progress(50)

            if hubs_config.is_zero_hub_mode:
                st.info("📦 Zero Hub Mode: All orders routed directly from DEPOT")
            else:
                hub_names = ", ".join([h.hub.name for h in hubs_config.hubs])
                st.info(f"🎯 Multi-Hub Routing: Blind Van → [{hub_names}], Motors from each hub/DEPOT")

            # Load solver configuration
            config = parser.get_config()

            solver = MultiHubVRPSolver(
                orders=orders,
                fleet=fleet,
                depot=depot,
                multi_hub_config=hubs_config,
                hub_routing_manager=hub_routing_manager,
                full_distance_matrix=distance_matrix,
                full_duration_matrix=duration_matrix,
                config=config
            )

            with st.spinner(f"Optimizing routes (max {time_limit}s)..."):
                solution = solver.solve(
                    optimization_strategy=optimization_strategy,
                    time_limit=time_limit
                )

            st.session_state.solution = solution

            # Clear map HTML cache for new solution
            st.session_state.map_html_cache = {}

            status_text.text(f"✅ Solusi ditemukan! {len(solution.routes)} routes generated")
            progress_bar.progress(70)

            # Step 4: Generate Excel and CSV
            status_text.text("📊 Generating Excel and CSV outputs...")
            progress_bar.progress(80)

            # Ensure results directory exists
            results_dir = Path("results")
            results_dir.mkdir(exist_ok=True)

            # Generate Excel
            excel_generator = ExcelGenerator(depot=depot)
            excel_path = excel_generator.generate(
                solution=solution,
                output_dir=str(results_dir)
            )
            st.session_state.excel_path = excel_path

            # Generate CSV with same timestamp
            timestamp = datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
            csv_generator = CSVGenerator(depot=depot, hubs_config=hubs_config)
            csv_path = csv_generator.generate(
                solution=solution,
                output_dir=str(results_dir),
                filename=f"routing_result_{timestamp}"
            )
            st.session_state.csv_path = csv_path

            # Generate CSV summary
            csv_summary_path = csv_generator.generate_summary_csv(
                solution=solution,
                output_dir=str(results_dir),
                filename=f"routing_summary_{timestamp}"
            )
            st.session_state.csv_summary_path = csv_summary_path

            status_text.text("✅ Excel and CSV files berhasil dibuat!")
            progress_bar.progress(100)

            # Show success message
            st.markdown(
                '<div class="success-box">'
                f'<strong>✅ Routing berhasil di-generate!</strong><br>'
                f'📁 Excel: {Path(excel_path).name}<br>'
                f'📁 CSV: {Path(csv_path).name}<br>'
                f'⏱️ Computation time: {solution.computation_time:.2f} detik'
                '</div>',
                unsafe_allow_html=True
            )

        except Exception as e:
            st.markdown(
                f'<div class="error-box">'
                f'<strong>❌ Error saat generating routes:</strong><br>'
                f'{str(e)}'
                '</div>',
                unsafe_allow_html=True
            )
            import traceback
            with st.expander("🔍 Detail Error (untuk debugging)"):
                st.code(traceback.format_exc())


def render_results_section():
    """Render the results section"""
    st.header("📊 4. Hasil Routing")

    if st.session_state.solution is None:
        st.info("ℹ️ Belum ada hasil routing. Silakan generate routes terlebih dahulu.")
        return

    solution = st.session_state.solution

    # Display summary metrics
    st.subheader("Summary Metrics")

    col1, col2, col3, col4 = st.columns(4)

    with col1:
        st.metric("Total Vehicles", solution.total_vehicles_used)

    with col2:
        st.metric("Total Orders", solution.total_orders_delivered)

    with col3:
        st.metric("Total Distance", f"{solution.total_distance:.1f} km")

    with col4:
        st.metric("Total Cost (Estimation)", f"Rp {solution.total_cost:,.0f}")

    # Additional metrics
    col5, col6, col7, col8 = st.columns(4)

    with col5:
        avg_distance = solution.total_distance / solution.total_vehicles_used if solution.total_vehicles_used > 0 else 0
        st.metric("Avg Distance/Vehicle", f"{avg_distance:.1f} km")

    with col6:
        avg_orders = solution.total_orders_delivered / solution.total_vehicles_used if solution.total_vehicles_used > 0 else 0
        st.metric("Avg Orders/Vehicle", f"{avg_orders:.1f}")

    with col7:
        st.metric("Optimization Strategy", solution.optimization_strategy.replace("_", " ").title())

    # Unassigned orders section
    if solution.unassigned_orders:
        st.markdown("---")
        st.subheader("⚠️ Unassigned Orders")
        st.warning(
            f"**{len(solution.unassigned_orders)} orders could not be assigned to any vehicle.** "
            f"This might be due to tight time windows, capacity limits, or unreachable locations."
        )

        unassigned_data = []
        for order in solution.unassigned_orders:
            unassigned_data.append({
                "Customer": order.display_name,
                "Address": order.alamat,
                "Delivery Time": order.delivery_time,
                "Weight (kg)": order.load_weight_in_kg,
                "Priority": "✅" if order.is_priority else ""
            })
        
        df_unassigned = pd.DataFrame(unassigned_data)
        st.dataframe(df_unassigned, width=1000)

    st.markdown("---")

    # Interactive Map Visualization
    st.subheader("🗺️ Interactive Route Map")

    # Route filter selector
    col_filter1, col_filter2, col_filter3 = st.columns([2, 2, 1])

    with col_filter1:
        route_options = ["All Routes"] + [f"{i+1}. {route.vehicle.name} ({route.num_stops} stops)"
                                           for i, route in enumerate(solution.routes) if route.num_stops > 0]
        selected_route_display = st.selectbox(
            "🚚 Filter by Courier/Vehicle:",
            options=route_options,
            help="Select a specific courier to view only their route"
        )

        # Parse selection
        if selected_route_display == "All Routes":
            selected_route_idx = None
        else:
            # Extract route number from "1. Vehicle Name (X stops)"
            selected_route_idx = int(selected_route_display.split(".")[0]) - 1

    # Show route-specific metrics if filtered
    if selected_route_idx is not None:
        selected_route = solution.routes[selected_route_idx]

        with col_filter2:
            st.metric("Route Distance", f"{selected_route.total_distance:.1f} km")

        with col_filter3:
            st.metric("Route Cost", f"Rp {selected_route.total_cost:,.0f}")

        # Additional route details
        st.info(
            f"📦 **Route #{selected_route_idx + 1} Details:** "
            f"{selected_route.vehicle.name} • "
            f"{selected_route.num_stops} stops • "
            f"{selected_route.total_weight:.1f}/{selected_route.vehicle.capacity} kg • "
            f"Depart: {selected_route.departure_time_str}"
        )

    try:
        depot = st.session_state.depot
        hubs_config = st.session_state.hubs_config

        # Create cache key based on selected route
        cache_key = f"route_{selected_route_idx}" if selected_route_idx is not None else "all_routes"

        # Check if map HTML is already cached
        if cache_key in st.session_state.map_html_cache:
            # Use cached HTML (instant display, no regeneration)
            map_html = st.session_state.map_html_cache[cache_key]
            st.success("✅ Map loaded from cache (instant)")
            components.html(map_html, height=600, scrolling=True)
        else:
            # Generate map (first time for this filter)
            visualizer = MapVisualizer(
                depot=depot,
                hubs_config=hubs_config,  # Pass multi-hub config to visualizer
                enable_road_routing=True  # Use actual road paths
            )

            if visualizer.enable_road_routing:
                with st.spinner("🛣️ Generating map with actual road paths (this will be cached)..."):
                    if selected_route_idx is not None:
                        # Single route view
                        route_map = visualizer.create_single_route_map(
                            solution,
                            selected_route_idx,
                            zoom_start=12
                        )
                    else:
                        # All routes view
                        route_map = visualizer.create_map(solution, zoom_start=12)
                st.success("✅ Map generated and cached for instant future access!")
            else:
                # No spinner needed for straight lines
                if selected_route_idx is not None:
                    route_map = visualizer.create_single_route_map(
                        solution,
                        selected_route_idx,
                        zoom_start=12
                    )
                else:
                    route_map = visualizer.create_map(solution, zoom_start=12)
                st.warning("⚠️ Using straight-line paths (OSRM URL not configured for road routing)")

            # Save map as HTML and cache it
            map_html = route_map._repr_html_()
            st.session_state.map_html_cache[cache_key] = map_html

            # Display the map
            components.html(map_html, height=600, scrolling=True)

        # Option to download map as HTML
        col_map1, col_map2 = st.columns([3, 1])
        with col_map2:
            if st.button("💾 Save Map as HTML", width="stretch"):
                results_dir = Path("results")
                results_dir.mkdir(exist_ok=True)

                timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
                if selected_route_idx is not None:
                    map_filename = f"route_map_vehicle{selected_route_idx+1}_{timestamp}.html"
                else:
                    map_filename = f"route_map_all_{timestamp}.html"
                map_path = results_dir / map_filename

                # Use cached HTML if available, otherwise generate
                if cache_key in st.session_state.map_html_cache:
                    map_html_content = st.session_state.map_html_cache[cache_key]
                    with open(map_path, 'w', encoding='utf-8') as f:
                        f.write(map_html_content)
                else:
                    # Fallback: generate map if not cached (shouldn't happen)
                    visualizer = MapVisualizer(depot=depot, hubs_config=hubs_config, enable_road_routing=True)
                    if selected_route_idx is not None:
                        visualizer.save_single_route_map(solution, selected_route_idx, str(map_path))
                    else:
                        visualizer.save_map(solution, str(map_path))

                    with open(map_path, 'r', encoding='utf-8') as f:
                        map_html_content = f.read()

                st.success(f"✅ Map saved: {map_filename}")

                # Download button
                st.download_button(
                    label="📥 Download Map HTML",
                    data=map_html_content,
                    file_name=map_filename,
                    mime="text/html",
                    width="stretch"
                )

        # Build map features text based on hub status
        map_features = """
        **💡 Map Features:**
        - 🚚 Filter by courier to view individual routes
        - 🏭 Red marker = Depot
        """
        if st.session_state.hub:
            map_features += "- 📦 Blue marker = Hub (consolidation point)\n"
        map_features += """- ⭐ Orange markers = Priority orders
        - ⚫ Blue markers = Regular orders
        - Click markers for detailed info
        - Use layer control (top right) to toggle routes
        - Zoom and pan to explore
        """
        st.markdown(map_features)

    except Exception as e:
        st.error(f"❌ Error creating map: {str(e)}")
        import traceback
        with st.expander("🔍 Debug info"):
            st.code(traceback.format_exc())

    st.markdown("---")

    # Route preview
    st.subheader("📋 Route Details Table")

    # Create DataFrame for display
    route_data = []
    for route in solution.routes:
        # Set starting location based on route source
        if route.source == "HUB" and st.session_state.hub:
            previous_location = st.session_state.hub.name
        else:
            previous_location = depot.name

        for stop in route.stops:
            if stop.order is not None:  # Skip depot
                # Check if this is a HUB consolidation stop
                is_hub = stop.order.sale_order_id == "HUB_CONSOLIDATION"

                # Current location name
                current_location = stop.order.display_name

                route_data.append({
                    "Source": route.source,
                    "Trip #": route.trip_number,
                    "From": previous_location,
                    "To": current_location,
                    "Vehicle": route.vehicle.name,
                    "Sequence": stop.sequence + 1,
                    "Location": "📦 HUB" if is_hub else "🏠 Customer",
                    "Customer": stop.order.display_name if stop.order else "-",
                    "Address": stop.order.alamat if stop.order else "-",
                    "City/Zone": stop.order.kota if stop.order else "-",
                    "Delivery Time": stop.order.delivery_time if stop.order else "-",
                    "Arrival": stop.arrival_time_str,
                    "Departure": stop.departure_time_str,
                    "Weight (kg)": f"{stop.order.load_weight_in_kg:.1f}" if stop.order else "-",
                    "Cumulative Weight (kg)": f"{stop.cumulative_weight:.1f}",
                    "Distance (km)": f"{stop.distance_from_prev:.2f}",
                    "Priority": "✅" if (stop.order and stop.order.is_priority) else ""
                })

                # Update previous location for next iteration
                previous_location = current_location

    df_routes = pd.DataFrame(route_data)

    # Filter by vehicle
    # Get unique vehicles from routes, with special handling for Blind Van
    vehicle_options = []
    for route in solution.routes:
        vehicle_name = route.vehicle.name
        if vehicle_name not in vehicle_options:
            vehicle_options.append(vehicle_name)

    # Sort to put Blind Van first if present
    if "Blind Van" in vehicle_options:
        vehicle_options.remove("Blind Van")
        vehicle_options.insert(0, "Blind Van")

    selected_vehicle = st.selectbox(
        "🚚 Filter by Vehicle",
        options=["All"] + vehicle_options,
        help="Select a vehicle to see its routes, or 'All' to see all routes"
    )

    if selected_vehicle != "All":
        df_display = df_routes[df_routes["Vehicle"] == selected_vehicle]
    else:
        df_display = df_routes

    # Show warning if no routes for selected vehicle
    if len(df_display) == 0:
        st.warning(f"No routes found for {selected_vehicle}")
    else:
        st.dataframe(df_display, width="stretch", height=400)

        # Show statistics for selected vehicle
        if selected_vehicle != "All":
            vehicle_route = [r for r in solution.routes if r.vehicle.name == selected_vehicle]
            if vehicle_route:
                route = vehicle_route[0]
                col_stat1, col_stat2, col_stat3, col_stat4 = st.columns(4)
                with col_stat1:
                    st.metric("Stops", len(route.stops))
                with col_stat2:
                    st.metric("Distance (km)", f"{route.total_distance:.1f}")
                with col_stat3:
                    st.metric("Weight (kg)", f"{route.total_weight:.1f}")
                with col_stat4:
                    st.metric("Cost", f"Rp {route.total_cost:,.0f}")

    # Note about Blind Van visibility
    if "Blind Van" not in [r.vehicle.name for r in solution.routes]:
        if st.session_state.hub and st.session_state.hub_config:
            st.info(
                "ℹ️ **Blind Van Note:** Blind Van consolidation route will appear when:\n"
                "1. ✅ Hub is enabled (configured in settings)\n"
                "2. ✅ There are orders from hub-zones (JAKARTA UTARA, JAKARTA BARAT, TANGERANG, BEKASI UTARA)\n"
                "\nCurrently: No hub-zone orders found, so Blind Van is not needed."
            )

    # Add HUB routing summary if hub is enabled
    if st.session_state.hub and st.session_state.hub_manager:
        st.markdown("---")
        st.subheader("🎯 Hub Routing Summary")

        hub_orders_delivered = len([stop.order for route in solution.routes
                                   for stop in route.stops
                                   if stop.order and stop.order.kota in st.session_state.hub_config.get("zones_via_hub", [])])
        direct_orders_delivered = solution.total_orders_delivered - hub_orders_delivered

        col_hub1, col_hub2, col_hub3 = st.columns(3)
        with col_hub1:
            st.metric("Hub Orders Delivered", hub_orders_delivered)
        with col_hub2:
            st.metric("Direct Orders Delivered", direct_orders_delivered)
        with col_hub3:
            hub_pct = (hub_orders_delivered / solution.total_orders_delivered * 100) if solution.total_orders_delivered > 0 else 0
            st.metric("Hub %", f"{hub_pct:.1f}%")

        # Show Blind Van consolidation details
        blind_van_routes = [r for r in solution.routes if r.vehicle.name == "Blind Van"]
        if blind_van_routes:
            st.info(
                f"🚚 **Blind Van Consolidation:**\n"
                f"• Route: DEPOT → 📦 HUB → DEPOT\n"
                f"• {len(blind_van_routes)} consolidation route(s)\n"
                f"• Total weight consolidated: {sum(r.total_weight for r in blind_van_routes):.1f} kg"
            )

    st.markdown("---")

    # Download section
    st.subheader("Download Reports")

    col_dl1, col_dl2, col_dl3 = st.columns(3)

    # Download Excel
    with col_dl1:
        st.write("**Excel Report**")
        if st.session_state.excel_path and os.path.exists(st.session_state.excel_path):
            with open(st.session_state.excel_path, 'rb') as f:
                excel_bytes = f.read()

            st.download_button(
                label="📥 Download Excel",
                data=excel_bytes,
                file_name=Path(st.session_state.excel_path).name,
                mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                type="primary",
                width="stretch"
            )

    # Download CSV Routes
    with col_dl2:
        st.write("**CSV Routes**")
        if 'csv_path' in st.session_state and st.session_state.csv_path and os.path.exists(st.session_state.csv_path):
            with open(st.session_state.csv_path, 'rb') as f:
                csv_bytes = f.read()

            st.download_button(
                label="📥 Download CSV",
                data=csv_bytes,
                file_name=Path(st.session_state.csv_path).name,
                mime="text/csv",
                type="primary",
                width="stretch"
            )

    # Download CSV Summary
    with col_dl3:
        st.write("**CSV Summary**")
        if 'csv_summary_path' in st.session_state and st.session_state.csv_summary_path and os.path.exists(st.session_state.csv_summary_path):
            with open(st.session_state.csv_summary_path, 'rb') as f:
                csv_summary_bytes = f.read()

            st.download_button(
                label="📥 Download Summary",
                data=csv_summary_bytes,
                file_name=Path(st.session_state.csv_summary_path).name,
                mime="text/csv",
                type="primary",
                width="stretch"
            )

    st.markdown(
        f'<div class="info-box">'
        f'📁 Files saved to results directory'
        '</div>',
        unsafe_allow_html=True
    )


def render_historical_results():
    """Render the historical results viewer"""
    st.header("📜 5. Historical Results")

    results_dir = Path("results")

    if not results_dir.exists():
        st.info("ℹ️ Belum ada hasil routing yang tersimpan.")
        return

    # Get all Excel files
    excel_files = list(results_dir.glob("routing_result_*.xlsx"))
    excel_files.sort(reverse=True)  # Newest first

    if not excel_files:
        st.info("ℹ️ Belum ada hasil routing yang tersimpan.")
        return

    st.write(f"Ditemukan **{len(excel_files)}** hasil routing:")

    # Create DataFrame for historical results
    historical_data = []
    for filepath in excel_files:
        stat = filepath.stat()
        historical_data.append({
            "Filename": filepath.name,
            "Created": datetime.fromtimestamp(stat.st_mtime).strftime("%Y-%m-%d %H:%M:%S"),
            "Size": f"{stat.st_size / 1024:.1f} KB",
            "Path": str(filepath)
        })

    df_historical = pd.DataFrame(historical_data)

    # Display table
    st.dataframe(df_historical[["Filename", "Created", "Size"]], width="stretch")

    # Download section
    st.subheader("Download Historical Result")

    selected_file = st.selectbox(
        "Pilih file untuk download:",
        options=[f["Filename"] for f in historical_data]
    )

    if selected_file:
        filepath = results_dir / selected_file

        if filepath.exists():
            with open(filepath, 'rb') as f:
                excel_bytes = f.read()

            st.download_button(
                label=f"📥 Download {selected_file}",
                data=excel_bytes,
                file_name=selected_file,
                mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                width="stretch"
            )


def render_sidebar():
    """Render the sidebar with additional info"""
    with st.sidebar:
        st.header("⚙️ Configuration")

        # Time tolerance configuration
        with st.expander("⏱️ Time Tolerance", expanded=False):
            st.write("Configure delivery time window tolerances:")
            priority_tolerance = st.number_input(
                "Priority orders tolerance (min)",
                min_value=0,
                max_value=120,
                value=0,
                step=5,
                help="Minutes of tolerance for priority orders (0 = strict)"
            )
            non_priority_tolerance = st.number_input(
                "Non-priority orders tolerance (min)",
                min_value=0,
                max_value=180,
                value=60,
                step=15,
                help="Minutes of tolerance for non-priority orders"
            )
            st.session_state.priority_tolerance = priority_tolerance
            st.session_state.non_priority_tolerance = non_priority_tolerance

        # Rate per KM configuration
        with st.expander("💰 Rate per KM", expanded=False):
            st.write("Configure delivery rate per kilometer:")

            if st.session_state.fleet is not None:
                # Initialize rate_overrides from fleet defaults if empty
                if not st.session_state.rate_overrides:
                    for vehicle_type, count, unlimited in st.session_state.fleet.vehicle_types:
                        st.session_state.rate_overrides[vehicle_type.name] = vehicle_type.cost_per_km

                # Create input for each vehicle type
                for vehicle_type, count, unlimited in st.session_state.fleet.vehicle_types:
                    default_rate = vehicle_type.cost_per_km
                    current_rate = st.session_state.rate_overrides.get(vehicle_type.name, default_rate)

                    new_rate = st.number_input(
                        f"{vehicle_type.name} (Rp/km)",
                        min_value=0,
                        max_value=100000,
                        value=int(current_rate),
                        step=500,
                        key=f"rate_{vehicle_type.name}",
                        help=f"Default: Rp {default_rate:,.0f}/km"
                    )
                    st.session_state.rate_overrides[vehicle_type.name] = float(new_rate)

                # Reset button
                if st.button("🔄 Reset to Default", key="reset_rates"):
                    for vehicle_type, count, unlimited in st.session_state.fleet.vehicle_types:
                        st.session_state.rate_overrides[vehicle_type.name] = vehicle_type.cost_per_km
                    st.rerun()
            else:
                st.info("📋 Upload vehicle configuration to set rates")

        # Debug mode configuration
        with st.expander("🐛 Debug Mode", expanded=False):
            debug_enabled = st.checkbox("Enable debug logging", value=False)
            if debug_enabled:
                save_distance_matrix = st.checkbox("Save distance matrix to CSV", value=False)
                st.session_state.debug_mode = True
                st.session_state.save_distance_matrix = save_distance_matrix
            else:
                st.session_state.debug_mode = False
                st.session_state.save_distance_matrix = False

        st.markdown("---")

        st.header("ℹ️ About")

        st.markdown("""
        **Segarloka VRP Solver**

        Aplikasi ini menggunakan Google OR-Tools untuk mengoptimalkan routing pengiriman sayur Segarloka.

        **Fitur:**
        - ✅ Time window constraints (HARD)
        - ✅ Vehicle capacity constraints
        - ✅ Unlimited fleet auto-scaling
        - ✅ 3 optimization strategies
        - ✅ OSRM Distance Matrix API
        - ✅ Professional Excel output
        - ✅ Interactive map visualization
        - ✅ Historical results tracking

        **Constraints:**
        - Service time: 15 min/lokasi
        - Departure: 30 min sebelum earliest delivery
        - Time windows: MUST be met (hard constraint)
        """)

        st.markdown("---")

        st.header("🔧 System Status")

        # Check OSRM API
        osrm_url = os.getenv("OSRM_URL", "https://osrm.segarloka.cc")
        if osrm_url:
            st.success(f"✅ OSRM API at {osrm_url}")
        else:
            st.error("❌ OSRM API not configured")

        # Check depot config
        depot_lat = os.getenv("DEPOT_LATITUDE")
        depot_lon = os.getenv("DEPOT_LONGITUDE")
        if depot_lat and depot_lon:
            st.success("✅ Depot Configuration")
        else:
            st.warning("⚠️ Depot Configuration")

        # Check cache directory
        cache_dir = Path(".cache")
        if cache_dir.exists():
            cache_files = list(cache_dir.glob("*.json"))
            st.info(f"💾 Cache: {len(cache_files)} files")

        # Check results directory
        results_dir = Path("results")
        if results_dir.exists():
            result_files = list(results_dir.glob("*.xlsx"))
            st.info(f"📊 Results: {len(result_files)} files")

        st.markdown("---")

        st.markdown("""
        **📚 Documentation:**
        - [README.md](README.md)
        - [ABOUT.md](ABOUT.md)
        - [PLAN.md](PLAN.md)

        **🔗 Powered by:**
        - Google OR-Tools
        - Streamlit
        - OSRM
        """)


def main():
    """Main application entry point"""

    # Initialize session state
    initialize_session_state()

    # Render sidebar
    render_sidebar()

    # Render header
    render_header()

    # Render upload section
    render_upload_section()

    st.markdown("---")

    # Render configuration section
    optimization_strategy, time_limit = render_configuration_section()

    st.markdown("---")

    # Render processing section
    render_processing_section(optimization_strategy, time_limit)

    st.markdown("---")

    # Render results section
    render_results_section()

    st.markdown("---")

    # Render historical results
    render_historical_results()

    # Footer
    st.markdown("---")
    st.markdown(
        '<p style="text-align: center; color: #666; font-size: 0.9rem;">'
        '🚚 Segarloka VRP Solver v0.1.0 | Built with ❤️ using Streamlit & OR-Tools'
        '</p>',
        unsafe_allow_html=True
    )


if __name__ == "__main__":
    main()
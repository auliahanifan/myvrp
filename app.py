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

# Load environment variables
load_dotenv()

# Import project modules
from src.models.location import Depot, Location
from src.models.order import Order
from src.utils.csv_parser import CSVParser
from src.utils.yaml_parser import YAMLParser
from src.utils.distance_calculator import DistanceCalculator
from src.solver.vrp_solver import VRPSolver
from src.output.excel_generator import ExcelGenerator
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
    if 'depot' not in st.session_state:
        st.session_state.depot = None


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
                st.dataframe(df.head(10), use_container_width=True)

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
        st.subheader("Lokasi Depot")

        depot = get_depot_from_env()
        st.session_state.depot = depot

        st.write(f"**Nama:** {depot.name}")
        st.write(f"**Alamat:** {depot.address}")
        st.write(f"**Koordinat:** {depot.coordinates[0]:.6f}, {depot.coordinates[1]:.6f}")

        st.markdown(
            '<div class="info-box">ℹ️ Lokasi depot dikonfigurasi via .env file</div>',
            unsafe_allow_html=True
        )

        # Radar API status
        api_key = os.getenv("RADAR_API_KEY")
        if api_key and api_key != "your_api_key_here":
            st.markdown(
                '<div class="success-box">✅ Radar API Key configured</div>',
                unsafe_allow_html=True
            )
        else:
            st.markdown(
                '<div class="error-box">❌ Radar API Key not configured!<br>'
                'Set RADAR_API_KEY in .env file</div>',
                unsafe_allow_html=True
            )

    return optimization_strategy, time_limit


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
    if st.button("🚀 Generate Routing Optimal", type="primary", use_container_width=True):
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

            # Create locations list
            locations = [depot] + [
                Location(o.display_name, o.coordinates, o.alamat)
                for o in orders
            ]

            # Step 2: Calculate distance matrix with cache
            status_text.text("🗺️ Menghitung distance matrix via Radar API...")
            progress_bar.progress(20)

            api_key = os.getenv("RADAR_API_KEY")
            if not api_key or api_key == "your_api_key_here":
                raise ValueError("Radar API key tidak dikonfigurasi. Set RADAR_API_KEY di .env file")

            # Get cache config from YAML
            parser = YAMLParser("conf.yaml")
            parser.parse()  # Load data
            cache_config = parser.get_cache_config()

            calculator = DistanceCalculator(
                api_key=api_key,
                cache_dir=cache_config.get("directory", ".cache"),
                cache_ttl_hours=cache_config.get("ttl_hours", 24),
                enable_cache=cache_config.get("enabled", True)
            )

            with st.spinner("Fetching distances from Radar (with cache)..."):
                distance_matrix, duration_matrix = calculator.calculate_matrix(locations)

            # Show cache statistics
            cache_stats = calculator.get_cache_stats()
            if cache_stats["cache_hits"] > 0:
                status_text.text(f"✅ Distance matrix loaded (🔥 cache hit! Saved {cache_stats['api_calls']} API calls)")
            else:
                status_text.text(f"✅ Distance matrix calculated ({len(locations)}x{len(locations)} locations, cached for reuse)")

            progress_bar.progress(40)

            # Step 3: Solve VRP
            status_text.text(f"🧮 Solving VRP dengan strategi: {optimization_strategy}...")
            progress_bar.progress(50)

            solver = VRPSolver(
                orders=orders,
                fleet=fleet,
                depot=depot,
                distance_matrix=distance_matrix,
                duration_matrix=duration_matrix
            )

            with st.spinner(f"Optimizing routes (max {time_limit}s)..."):
                solution = solver.solve(
                    optimization_strategy=optimization_strategy,
                    time_limit=time_limit
                )

            st.session_state.solution = solution

            status_text.text(f"✅ Solusi ditemukan! {len(solution.routes)} routes generated")
            progress_bar.progress(70)

            # Step 4: Generate Excel
            status_text.text("📊 Generating Excel output...")
            progress_bar.progress(80)

            generator = ExcelGenerator(depot=depot)

            # Ensure results directory exists
            results_dir = Path("results")
            results_dir.mkdir(exist_ok=True)

            excel_path = generator.generate(
                solution=solution,
                output_dir=str(results_dir)
            )

            st.session_state.excel_path = excel_path

            status_text.text("✅ Excel file berhasil dibuat!")
            progress_bar.progress(100)

            # Show success message
            st.markdown(
                '<div class="success-box">'
                f'<strong>✅ Routing berhasil di-generate!</strong><br>'
                f'📁 File: {Path(excel_path).name}<br>'
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

    with col8:
        st.metric("Computation Time", f"{solution.computation_time:.2f}s")

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
        radar_api_key = os.getenv("RADAR_API_KEY")
        visualizer = MapVisualizer(
            depot=depot,
            radar_api_key=radar_api_key,
            enable_road_routing=True  # Use actual road paths
        )

        # Show routing mode status and create map
        if visualizer.enable_road_routing:
            with st.spinner("🛣️ Generating map with actual road paths (may take a few seconds)..."):
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
            st.success("✅ Map generated with actual road paths!")
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
            st.warning("⚠️ Using straight-line paths (set RADAR_API_KEY for road routing)")

        # Display map
        st_folium(route_map, width=1400, height=600)

        # Option to download map as HTML
        col_map1, col_map2 = st.columns([3, 1])
        with col_map2:
            if st.button("💾 Save Map as HTML", use_container_width=True):
                results_dir = Path("results")
                results_dir.mkdir(exist_ok=True)

                timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
                if selected_route_idx is not None:
                    map_filename = f"route_map_vehicle{selected_route_idx+1}_{timestamp}.html"
                else:
                    map_filename = f"route_map_all_{timestamp}.html"
                map_path = results_dir / map_filename

                if selected_route_idx is not None:
                    visualizer.save_single_route_map(solution, selected_route_idx, str(map_path))
                else:
                    visualizer.save_map(solution, str(map_path))

                st.success(f"✅ Map saved: {map_filename}")

                # Download button
                with open(map_path, 'r', encoding='utf-8') as f:
                    html_content = f.read()

                st.download_button(
                    label="📥 Download Map HTML",
                    data=html_content,
                    file_name=map_filename,
                    mime="text/html",
                    use_container_width=True
                )

        st.markdown("""
        **💡 Map Features:**
        - 🚚 Filter by courier to view individual routes
        - 🏭 Red marker = Depot
        - ⭐ Orange markers = Priority orders
        - ⚫ Blue markers = Regular orders
        - Click markers for detailed info
        - Use layer control (top right) to toggle routes
        - Zoom and pan to explore
        """)

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
        for stop in route.stops:
            if stop.order is not None:  # Skip depot
                route_data.append({
                    "Vehicle": route.vehicle.name,
                    "Sequence": stop.sequence + 1,
                    "Customer": stop.order.display_name if stop.order else "-",
                    "Address": stop.order.alamat if stop.order else "-",
                    "Delivery Time": stop.order.delivery_time if stop.order else "-",
                    "Arrival": stop.arrival_time_str,
                    "Departure": stop.departure_time_str,
                    "Weight (kg)": f"{stop.order.load_weight_in_kg:.1f}" if stop.order else "-",
                    "Cumulative Weight (kg)": f"{stop.cumulative_weight:.1f}",
                    "Distance (km)": f"{stop.distance_from_prev:.2f}",
                    "Priority": "✅" if (stop.order and stop.order.is_priority) else ""
                })

    df_routes = pd.DataFrame(route_data)

    # Filter by vehicle
    selected_vehicle = st.selectbox(
        "Filter by Vehicle",
        options=["All"] + [route.vehicle.name for route in solution.routes]
    )

    if selected_vehicle != "All":
        df_display = df_routes[df_routes["Vehicle"] == selected_vehicle]
    else:
        df_display = df_routes

    st.dataframe(df_display, use_container_width=True, height=400)

    st.markdown("---")

    # Download Excel
    st.subheader("Download Excel Report")

    if st.session_state.excel_path and os.path.exists(st.session_state.excel_path):
        with open(st.session_state.excel_path, 'rb') as f:
            excel_bytes = f.read()

        st.download_button(
            label="📥 Download Excel Report",
            data=excel_bytes,
            file_name=Path(st.session_state.excel_path).name,
            mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            type="primary",
            use_container_width=True
        )

        st.markdown(
            f'<div class="info-box">'
            f'📁 File tersimpan di: <code>{st.session_state.excel_path}</code>'
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
    st.dataframe(df_historical[["Filename", "Created", "Size"]], use_container_width=True)

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
                use_container_width=True
            )


def render_sidebar():
    """Render the sidebar with additional info"""
    with st.sidebar:
        st.header("ℹ️ About")

        st.markdown("""
        **Segarloka VRP Solver**

        Aplikasi ini menggunakan Google OR-Tools untuk mengoptimalkan routing pengiriman sayur Segarloka.

        **Fitur:**
        - ✅ Time window constraints (HARD)
        - ✅ Vehicle capacity constraints
        - ✅ Unlimited fleet auto-scaling
        - ✅ 3 optimization strategies
        - ✅ Radar Distance Matrix API
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

        # Check API key
        api_key = os.getenv("RADAR_API_KEY")
        if api_key and api_key != "your_api_key_here":
            st.success("✅ Radar API")
        else:
            st.error("❌ Radar API")

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
        - Radar API
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

"""Streamlit UI shell for Segarloka Auto-Route Service."""

from __future__ import annotations

from pathlib import Path

import streamlit as st
import streamlit.components.v1 as components

from src.application.configuration_service import ConfigurationService
from src.application.contracts import DebugOptions, MapRenderRequest, RoutePlanningRequest
from src.application.history_service import HistoryService
from src.application.map_service import MapService
from src.application.results_service import ResultsService
from src.application.route_planning_service import RoutePlanningService
from src.presentation.streamlit_state import StreamlitState
from src.presentation.streamlit_view_models import (
    preview_dataframe,
    records_dataframe,
    vehicle_editor_rows,
    vehicle_summary_lines,
)


configuration_service = ConfigurationService()
route_planning_service = RoutePlanningService(configuration_service=configuration_service)
results_service = ResultsService()
history_service = HistoryService()
map_service = MapService()


st.set_page_config(
    page_title="Segarloka VRP Solver",
    page_icon="🚚",
    layout="wide",
    initial_sidebar_state="expanded",
)

st.markdown(
    """
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
    """,
    unsafe_allow_html=True,
)


def initialize_session_state():
    snapshot = configuration_service.load_snapshot()
    state = StreamlitState.initialize(snapshot)
    if state.config_snapshot is None:
        state.config_snapshot = snapshot
    if state.vehicle_config is None:
        state.vehicle_config = snapshot.vehicle_config
    return state


def render_header():
    st.markdown('<p class="main-header">🚚 Segarloka VRP Solver</p>', unsafe_allow_html=True)
    st.markdown(
        '<p class="sub-header">Optimasi Routing Pengiriman Sayur dengan OR-Tools</p>',
        unsafe_allow_html=True,
    )
    st.markdown("---")


def _render_vehicle_editor(state):
    config = state.vehicle_config
    vehicles_to_remove = []
    rows = vehicle_editor_rows(config["vehicles"])

    st.markdown("**Tipe Kendaraan**")
    if any(row["capacity_locked"] for row in rows):
        st.caption(
            "Sepeda motor ditampilkan sebagai dua varian berbagi pool armada yang sama: "
            "80 kg untuk order fragile dan 120 kg untuk order non-fragile."
        )

    for row in rows:
        source_index = row["source_index"]
        vehicle_config = config["vehicles"][source_index]
        widget_key = row["display_key"]
        with st.container():
            header_cols = st.columns([4, 1])
            with header_cols[0]:
                st.markdown(f"**{row['display_name']}**")
                new_name = st.text_input(
                    "Nama",
                    value=vehicle_config["name"],
                    key=f"vehicle_name_{widget_key}",
                    label_visibility="collapsed",
                    disabled=row["capacity_locked"] and not row["remove_allowed"],
                )
                if new_name != vehicle_config["name"]:
                    config["vehicles"][source_index]["name"] = new_name
                    state.config_modified = True

            with header_cols[1]:
                if row["remove_allowed"]:
                    if st.button(
                        "X",
                        key=f"remove_vehicle_{widget_key}",
                        help="Remove this vehicle type",
                    ):
                        vehicles_to_remove.append(source_index)

            prop_cols = st.columns(4)
            with prop_cols[0]:
                if row["capacity_locked"]:
                    st.number_input(
                        "Capacity (kg)",
                        min_value=1.0,
                        max_value=10000.0,
                        value=float(row["capacity"]),
                        step=10.0,
                        key=f"vehicle_capacity_{widget_key}",
                        disabled=True,
                    )
                else:
                    new_capacity = st.number_input(
                        "Capacity (kg)",
                        min_value=1.0,
                        max_value=10000.0,
                        value=float(vehicle_config["capacity"]),
                        step=10.0,
                        key=f"vehicle_capacity_{widget_key}",
                    )
                    if new_capacity != vehicle_config["capacity"]:
                        config["vehicles"][source_index]["capacity"] = new_capacity
                        state.config_modified = True
            with prop_cols[1]:
                new_rate = st.number_input(
                    "Rate (Rp/km)",
                    min_value=0.0,
                    max_value=1000000.0,
                    value=float(vehicle_config["cost_per_km"]),
                    step=100.0,
                    key=f"vehicle_rate_{widget_key}",
                    disabled=row["capacity_locked"] and not row["remove_allowed"],
                )
                if new_rate != vehicle_config["cost_per_km"]:
                    config["vehicles"][source_index]["cost_per_km"] = new_rate
                    state.config_modified = True
            with prop_cols[2]:
                new_count = st.number_input(
                    "Count",
                    min_value=1,
                    max_value=1000,
                    value=int(vehicle_config["fixed_count"]),
                    step=1,
                    key=f"vehicle_count_{widget_key}",
                    disabled=row["capacity_locked"] and not row["remove_allowed"],
                )
                if new_count != vehicle_config["fixed_count"]:
                    config["vehicles"][source_index]["fixed_count"] = new_count
                    state.config_modified = True
            with prop_cols[3]:
                new_unlimited = st.checkbox(
                    "Unlimited",
                    value=bool(vehicle_config.get("unlimited", False)),
                    key=f"vehicle_unlimited_{widget_key}",
                    disabled=row["capacity_locked"] and not row["remove_allowed"],
                )
                if new_unlimited != vehicle_config.get("unlimited", False):
                    config["vehicles"][source_index]["unlimited"] = new_unlimited
                    state.config_modified = True
            st.divider()

    if vehicles_to_remove:
        for idx in sorted(vehicles_to_remove, reverse=True):
            if len(config["vehicles"]) > 1:
                config["vehicles"].pop(idx)
                state.config_modified = True
        st.rerun()

    if st.button("+ Add Vehicle Type", key="add_vehicle"):
        config["vehicles"].append(
            {
                "name": f"New Vehicle {len(config['vehicles']) + 1}",
                "capacity": 100.0,
                "cost_per_km": 2000.0,
                "fixed_count": 1,
                "unlimited": False,
            }
        )
        state.config_modified = True
        st.rerun()

    total_vehicles = sum(vehicle["fixed_count"] for vehicle in config["vehicles"])
    st.caption(f"Total fixed vehicles: {total_vehicles} units")
    st.markdown("---")
    st.markdown("**Routing Settings**")

    routing = config.get("routing", {})
    col1, col2 = st.columns(2)
    with col1:
        return_to_depot = st.checkbox(
            "Return to depot",
            value=routing.get("return_to_depot", True),
            key="routing_return_to_depot",
        )
        if return_to_depot != routing.get("return_to_depot", True):
            routing["return_to_depot"] = return_to_depot
            state.config_modified = True

        multiple_trips = st.checkbox(
            "Multiple trips",
            value=routing.get("multiple_trips", True),
            key="routing_multiple_trips",
        )
        if multiple_trips != routing.get("multiple_trips", True):
            routing["multiple_trips"] = multiple_trips
            state.config_modified = True

    with col2:
        priority_tolerance = st.number_input(
            "Priority time tolerance (min)",
            min_value=0,
            max_value=120,
            value=routing.get("priority_time_tolerance", 0),
            step=5,
            key="routing_priority_tolerance",
        )
        if priority_tolerance != routing.get("priority_time_tolerance", 0):
            routing["priority_time_tolerance"] = priority_tolerance
            state.config_modified = True

        non_priority_tolerance = st.number_input(
            "Non-priority time tolerance (min)",
            min_value=0,
            max_value=180,
            value=routing.get("non_priority_time_tolerance", 60),
            step=5,
            key="routing_non_priority_tolerance",
        )
        if non_priority_tolerance != routing.get("non_priority_time_tolerance", 60):
            routing["non_priority_time_tolerance"] = non_priority_tolerance
            state.config_modified = True

    relax_time_windows = st.checkbox(
        "Relax time windows",
        value=routing.get("relax_time_windows", False),
        key="routing_relax_windows",
    )
    if relax_time_windows != routing.get("relax_time_windows", False):
        routing["relax_time_windows"] = relax_time_windows
        state.config_modified = True

    if routing.get("relax_time_windows", False):
        relaxation_minutes = st.number_input(
            "Relaxation (minutes)",
            min_value=0,
            max_value=120,
            value=routing.get("time_window_relaxation_minutes", 15),
            step=5,
            key="routing_relax_minutes",
        )
        if relaxation_minutes != routing.get("time_window_relaxation_minutes", 15):
            routing["time_window_relaxation_minutes"] = relaxation_minutes
            state.config_modified = True

    config["routing"] = routing
    state.vehicle_config = config

    status_cols = st.columns(2)
    with status_cols[0]:
        if state.config_modified:
            st.caption("Configuration modified")
    with status_cols[1]:
        if st.button("Reset to Defaults", key="reset_config"):
            snapshot = configuration_service.load_snapshot()
            state.config_snapshot = snapshot
            state.vehicle_config = snapshot.vehicle_config
            state.config_modified = False
            st.rerun()


def render_upload_section(state):
    st.header("📤 1. Upload Data")
    col1, col2 = st.columns(2)

    with col1:
        uploaded_file = st.file_uploader(
            "Upload file CSV dengan data order harian",
            type=["csv"],
            help="Format CSV mengikuti template order Segarloka.",
        )
        if uploaded_file is not None:
            file_bytes = uploaded_file.getvalue()
            if (
                state.upload_bytes != file_bytes
                or state.upload_filename != uploaded_file.name
                or state.upload_result is None
            ):
                try:
                    state.upload_result = route_planning_service.parse_uploaded_orders(
                        file_bytes,
                        uploaded_file.name,
                    )
                    state.upload_bytes = file_bytes
                    state.upload_filename = uploaded_file.name
                    st.markdown(
                        f'<div class="success-box">✅ Berhasil memuat {state.upload_result.total_orders} orders</div>',
                        unsafe_allow_html=True,
                    )
                except Exception as exc:
                    st.markdown(
                        f'<div class="error-box">❌ Error parsing CSV: {exc}</div>',
                        unsafe_allow_html=True,
                    )
                    state.upload_result = None

        if state.upload_result is not None:
            preview_df = preview_dataframe(state.upload_result.preview_rows)
            st.subheader("Preview Data (10 rows pertama)")
            st.dataframe(preview_df, use_container_width=True)

            stats_cols = st.columns(3)
            with stats_cols[0]:
                st.metric("Total Orders", state.upload_result.total_orders)
            with stats_cols[1]:
                st.metric("Total Berat", f"{state.upload_result.total_weight_kg:.1f} kg")
            with stats_cols[2]:
                st.metric("Priority Orders", state.upload_result.priority_orders)

    with col2:
        st.subheader("Vehicle Configuration")
        _render_vehicle_editor(state)


def render_configuration_section(state):
    st.header("⚙️ 2. Konfigurasi Routing")
    col1, col2 = st.columns(2)
    snapshot = state.config_snapshot

    with col1:
        optimization_strategy = st.radio(
            "Pilih strategi optimasi:",
            options=["minimize_vehicles", "minimize_cost", "balanced"],
            format_func=lambda value: {
                "minimize_vehicles": "⚙️ Minimize Vehicles",
                "minimize_cost": "💰 Minimize Cost",
                "balanced": "⚖️ Balanced",
            }[value],
            index=2,
        )
        time_limit = st.slider(
            "Time Limit (detik)",
            min_value=60,
            max_value=600,
            value=60,
            step=30,
        )

    with col2:
        st.subheader("Lokasi Depot & Hubs")
        depot = snapshot.depot
        st.write(f"**Depot - Nama:** {depot.name}")
        st.write(f"**Depot - Alamat:** {depot.address}")
        st.write(f"**Depot - Koordinat:** {depot.coordinates[0]:.6f}, {depot.coordinates[1]:.6f}")
        st.markdown("---")

        hubs_config = snapshot.hubs_config
        if hubs_config.is_zero_hub_mode:
            st.markdown(
                '<div class="info-box">📦 Zero Hub Mode: All orders routed directly from DEPOT</div>',
                unsafe_allow_html=True,
            )
        else:
            st.markdown(
                f'<div class="info-box">✅ Multi-Hub Mode: {hubs_config.num_hubs} hub(s) configured</div>',
                unsafe_allow_html=True,
            )
            for hub_cfg in hubs_config.hubs:
                with st.expander(f"📦 {hub_cfg.hub.name} ({hub_cfg.hub_id})"):
                    st.write(f"**Alamat:** {hub_cfg.hub.address}")
                    st.write(
                        f"**Koordinat:** {hub_cfg.hub.coordinates[0]:.6f}, {hub_cfg.hub.coordinates[1]:.6f}"
                    )
                    st.write(
                        f"**Zones:** {', '.join(hub_cfg.zones_via_hub) if hub_cfg.zones_via_hub else 'None'}"
                    )

    return optimization_strategy, time_limit


def render_processing_section(state, optimization_strategy: str, time_limit: int):
    st.header("🔄 3. Generate Routes")
    if state.upload_bytes is None or state.upload_filename is None or state.vehicle_config is None:
        st.warning("⚠️ Harap upload CSV orders dan konfigurasi vehicle terlebih dahulu")
        return

    if st.button("🚀 Generate Routing Optimal", type="primary", use_container_width=True):
        try:
            config_snapshot = configuration_service.with_vehicle_config(
                state.config_snapshot,
                state.vehicle_config,
            )
            state.config_snapshot = config_snapshot
            request = RoutePlanningRequest(
                orders_file_bytes=state.upload_bytes,
                orders_filename=state.upload_filename,
                vehicle_config=state.vehicle_config,
                optimization_strategy=optimization_strategy,
                time_limit_seconds=time_limit,
                debug_options=DebugOptions(
                    debug_mode=state.debug_mode,
                    save_distance_matrix=state.save_distance_matrix,
                ),
            )

            with st.spinner(f"Optimizing routes (max {time_limit}s)..."):
                state.plan_result = route_planning_service.plan(request, config_snapshot)
            state.map_html_cache = {}

            st.markdown(
                '<div class="success-box">'
                f"<strong>✅ Routing berhasil di-generate!</strong><br>"
                f"📁 Excel: {state.plan_result.excel_path.name}<br>"
                f"📁 CSV: {state.plan_result.csv_path.name}<br>"
                f"⏱️ Computation time: {state.plan_result.summary.computation_time_seconds:.2f} detik"
                "</div>",
                unsafe_allow_html=True,
            )
        except Exception as exc:
            st.markdown(
                f'<div class="error-box"><strong>❌ Error saat generating routes:</strong><br>{exc}</div>',
                unsafe_allow_html=True,
            )


def render_results_section(state):
    st.header("📊 4. Hasil Routing")
    if state.plan_result is None:
        st.info("ℹ️ Belum ada hasil routing. Silakan generate routes terlebih dahulu.")
        return

    plan_result = state.plan_result
    solution = plan_result.solution
    metrics = results_service.build_summary_metrics(solution)

    st.subheader("Summary Metrics")
    metric_cols = st.columns(4)
    metric_items = [
        ("Total Vehicles", metrics["total_vehicles"]),
        ("Total Orders", metrics["total_orders"]),
        ("Total Distance", f"{metrics['total_distance_km']:.1f} km"),
        ("Total Cost (Estimation)", f"Rp {metrics['total_cost']:,.0f}"),
    ]
    for col, (label, value) in zip(metric_cols, metric_items):
        with col:
            st.metric(label, value)

    extra_cols = st.columns(4)
    extra_items = [
        ("Avg Distance/Vehicle", f"{metrics['avg_distance_per_vehicle']:.1f} km"),
        ("Avg Orders/Vehicle", f"{metrics['avg_orders_per_vehicle']:.1f}"),
        ("Optimization Strategy", metrics["optimization_strategy"].replace("_", " ").title()),
        ("Unassigned Orders", metrics["unassigned_orders"]),
    ]
    for col, (label, value) in zip(extra_cols, extra_items):
        with col:
            st.metric(label, value)

    if solution.unassigned_orders:
        st.markdown("---")
        st.subheader("⚠️ Unassigned Orders")
        st.dataframe(
            records_dataframe(results_service.build_unassigned_rows(solution)),
            use_container_width=True,
        )

    st.markdown("---")
    st.subheader("🗺️ Interactive Route Map")
    route_options = ["All Routes"] + [
        f"{index + 1}. {route.vehicle.name} ({route.num_stops} stops)"
        for index, route in enumerate(solution.routes)
        if route.num_stops > 0
    ]
    selected_route_display = st.selectbox(
        "🚚 Filter by Courier/Vehicle:",
        options=route_options,
    )
    selected_route_index = (
        None if selected_route_display == "All Routes" else int(selected_route_display.split(".")[0]) - 1
    )
    cache_key = f"{plan_result.map_cache_seed}:{selected_route_index if selected_route_index is not None else 'all'}"

    if cache_key not in state.map_html_cache:
        with st.spinner("🛣️ Generating map with actual road paths..."):
            map_result = map_service.render_map_html(
                MapRenderRequest(
                    solution=solution,
                    selected_route_index=selected_route_index,
                    depot=plan_result.depot,
                    hubs_config=plan_result.hubs_config,
                    cache_key=cache_key,
                )
            )
        state.map_html_cache[cache_key] = map_result.html

    map_html = state.map_html_cache[cache_key]
    components.html(map_html, height=600, scrolling=True)

    if st.button("💾 Save Map as HTML", use_container_width=True):
        map_path = map_service.save_map_html(map_html, selected_route_index)
        st.success(f"✅ Map saved: {map_path.name}")
        st.download_button(
            label="📥 Download Map HTML",
            data=map_html,
            file_name=map_path.name,
            mime="text/html",
            use_container_width=True,
        )

    st.markdown("---")
    st.subheader("📋 Route Details Table")
    route_rows = results_service.build_route_rows(solution, plan_result.depot, plan_result.hubs_config)
    vehicle_options = results_service.build_vehicle_options(solution)
    selected_vehicle = st.selectbox("🚚 Filter by Vehicle", options=["All"] + vehicle_options)

    if selected_vehicle == "All":
        filtered_rows = route_rows
    else:
        filtered_rows = [row for row in route_rows if row["Vehicle"] == selected_vehicle]

    if filtered_rows:
        st.dataframe(records_dataframe(filtered_rows), use_container_width=True, height=400)
    else:
        st.info("No routes found for selected vehicle.")

    st.markdown("---")
    st.subheader("Download Reports")
    download_cols = st.columns(3)
    download_items = [
        ("Excel Report", plan_result.excel_path, "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"),
        ("CSV Routes", plan_result.csv_path, "text/csv"),
        ("CSV Summary", plan_result.csv_summary_path, "text/csv"),
    ]
    for col, (label, path, mime) in zip(download_cols, download_items):
        with col:
            st.write(f"**{label}**")
            if path and path.exists():
                data = path.read_bytes()
                st.download_button(
                    label=f"📥 Download {label}",
                    data=data,
                    file_name=path.name,
                    mime=mime,
                    use_container_width=True,
                )


def render_historical_results():
    st.header("📜 5. Historical Results")
    items = history_service.list_results()
    if not items:
        st.info("ℹ️ Belum ada hasil routing yang tersimpan.")
        return

    st.write(f"Ditemukan **{len(items)}** hasil routing:")
    df = records_dataframe(
        [
            {
                "Filename": item.filename,
                "Created": item.created_at.strftime("%Y-%m-%d %H:%M:%S"),
                "Size": f"{item.size_kb:.1f} KB",
                "Path": str(item.path),
            }
            for item in items
        ]
    )
    st.dataframe(df[["Filename", "Created", "Size"]], use_container_width=True)

    selected_filename = st.selectbox(
        "Pilih file untuk download:",
        options=[item.filename for item in items],
    )
    selected_item = next(item for item in items if item.filename == selected_filename)
    st.download_button(
        label=f"📥 Download {selected_item.filename}",
        data=selected_item.path.read_bytes(),
        file_name=selected_item.filename,
        mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        use_container_width=True,
    )


def render_sidebar(state):
    with st.sidebar:
        st.header("⚙️ Configuration")
        if state.vehicle_config is not None:
            with st.expander("🚗 Vehicle & Routing Summary", expanded=False):
                for line in vehicle_summary_lines(state.vehicle_config["vehicles"]):
                    st.write(line)
                st.download_button(
                    label="📥 Export Config",
                    data=configuration_service.export_config_yaml(state.vehicle_config),
                    file_name="vehicle_config.yaml",
                    mime="text/yaml",
                    use_container_width=True,
                )

        with st.expander("🐛 Debug Mode", expanded=False):
            state.debug_mode = st.checkbox("Enable debug logging", value=state.debug_mode)
            if state.debug_mode:
                state.save_distance_matrix = st.checkbox(
                    "Save distance matrix to CSV",
                    value=state.save_distance_matrix,
                )

        st.markdown("---")
        st.header("ℹ️ About")
        st.markdown(
            """
            **Segarloka VRP Solver**

            Aplikasi ini menggunakan OR-Tools untuk mengoptimalkan routing pengiriman Segarloka.
            """
        )
        st.markdown("---")
        st.header("🔧 System Status")
        st.success("✅ Application layer active")
        st.info(f"💾 Cached maps: {len(state.map_html_cache)}")
        results_dir = Path("results")
        if results_dir.exists():
            st.info(f"📊 Results: {len(list(results_dir.glob('*.xlsx')))} files")


def main():
    state = initialize_session_state()
    render_sidebar(state)
    render_header()
    render_upload_section(state)
    st.markdown("---")
    optimization_strategy, time_limit = render_configuration_section(state)
    st.markdown("---")
    render_processing_section(state, optimization_strategy, time_limit)
    st.markdown("---")
    render_results_section(state)
    st.markdown("---")
    render_historical_results()
    st.markdown("---")
    st.markdown(
        '<p style="text-align: center; color: #666; font-size: 0.9rem;">'
        "Segarloka VRP Solver v0.1.0 | Streamlit UI shell + application services"
        "</p>",
        unsafe_allow_html=True,
    )


if __name__ == "__main__":
    main()

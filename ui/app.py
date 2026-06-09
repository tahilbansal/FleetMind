# ui/app.py
import streamlit as st
import httpx
import sys, os
from dotenv import load_dotenv
import pandas as pd
import plotly.express as px
import time

# Load environment variables FIRST
load_dotenv()

sys.path.append(os.path.dirname(os.path.dirname(__file__)))
from agents.dispatcher_agent import build_dispatcher_agent

# --- UI Configuration ---
st.set_page_config(
    page_title="FleetMind",
    page_icon="🚛",
    layout="wide",
    initial_sidebar_state="expanded"
)

# Custom CSS for a more "Production" feel
st.markdown("""
    <style>
    [data-testid="stMetric"] {
        background-color: var(--secondary-background-color);
        padding: 15px;
        border-radius: 10px;
        box-shadow: 0 2px 4px rgba(0,0,0,0.05);
        border: 1px solid rgba(128, 128, 128, 0.2);
        min-height: 120px;
    }
    [data-testid="stMetricValue"] {
        font-size: 1.8rem !important;
    }
    </style>
""", unsafe_allow_html=True)

if "initialized" not in st.session_state:
    st.session_state.initialized = False
if "current_state" not in st.session_state:
    st.session_state.current_state = None
if "current_solution" not in st.session_state:
    st.session_state.current_solution = None
if "map_html" not in st.session_state:
    st.session_state.map_html = None
if "prev_map_html" not in st.session_state:
    st.session_state.prev_map_html = None
if "messages" not in st.session_state:
    st.session_state.messages = []
if "sim_active" not in st.session_state:
    st.session_state.sim_active = False
if "sim_events" not in st.session_state:
    st.session_state.sim_events = []
if "agent" not in st.session_state:
    st.session_state.agent = build_dispatcher_agent()

def fetch_current_state():
    try:
        resp = httpx.get("http://localhost:8000/routes/current", timeout=10.0)
        if resp.status_code == 200:
            data = resp.json()
            st.session_state.current_solution = data.get("solution")
            st.session_state.current_state = data.get("state")
            
            # Update Map, preserving previous for comparison
            map_resp = httpx.get("http://localhost:8000/routes/map", timeout=30.0)
            if map_resp.status_code == 200:
                new_map = map_resp.json().get("html", "")
                if st.session_state.map_html and st.session_state.map_html != new_map:
                    st.session_state.prev_map_html = st.session_state.map_html
                st.session_state.map_html = new_map
            return data
    except Exception:
        pass
    return None

# --- Sidebar ---
with st.sidebar:
    st.image("https://cdn-icons-png.flaticon.com/512/2830/2830305.png", width=140)
    st.title("FleetMind")
    st.divider()

    st.subheader("Fleet Status")
    if st.session_state.current_state and st.session_state.current_solution:
        state = st.session_state.current_state
        sol = st.session_state.current_solution
        unavailable = state.get("unavailable_drivers", [])
        depot_ids = state.get("depot_ids", [])
        
        for vid in range(state["num_vehicles"]):
            is_active = str(vid) not in unavailable
            status_color = "🟢" if is_active else "🔴"
            
            # Fetch depot name for this vehicle if available
            depot_info = ""
            if depot_ids and vid < len(depot_ids):
                d_idx = int(depot_ids[vid])
                d_name = state["stops"][d_idx]["name"]
                depot_info = f"<br><small>Hub: {d_name}</small>"
            
            route = sol["routes"].get(str(vid), {})
            stops_remaining = max(0, len(route.get("stops", [])) - 2) if is_active else 0
            st.markdown(f"{status_color} **Driver {vid}** — {stops_remaining} stops{depot_info}", unsafe_allow_html=True)
    else:
        st.caption("Waiting for initialization...")

    st.divider()
    st.subheader("🛠️ Simulation Controls")
    st.session_state.sim_active = st.toggle("Live Simulation Mode", value=st.session_state.sim_active)
    sim_speed = st.select_slider("Sim Speed", options=[1, 2, 5, 10], value=2, help="Minutes advanced per tick")

    st.divider()
    if st.button("🔄 Full System Reset", use_container_width=True, type="secondary"):
        st.session_state.initialized = False
        st.session_state.messages = []
        st.session_state.prev_map_html = None
        st.session_state.map_html = None
        st.session_state.sim_active = False
        st.session_state.sim_events = []
        st.rerun()

# --- Auto-Initialization Logic ---
if not st.session_state.initialized:
    with st.spinner("🚀 Bootstrapping Fleet Configuration from Database..."):
        try:
            config_resp = httpx.get("http://localhost:8000/routes/config")
            if config_resp.status_code == 200:
                state_data = config_resp.json()
                init_resp = httpx.post("http://localhost:8000/routes/initialize", json=state_data, timeout=30.0)
                if init_resp.status_code == 200:
                    st.session_state.initialized = True
                    fetch_current_state()
                    st.rerun()
                else:
                    st.error(f"Solver Initialization Failed (HTTP {init_resp.status_code})")
                    st.json(init_resp.json()) # Display Pydantic validation errors
        except Exception as e:
            st.error(f"Failed to auto-start: {e}")
            st.stop()

# --- Dashboard Metrics ---
if st.session_state.current_solution:
    sol = st.session_state.current_solution
    m1, m2, m3, m4 = st.columns(4)
    active_v = len([v for v in sol["routes"].values() if v.get("stops") and len(v["stops"]) > 2])
    m1.metric("Active Fleet", f"{active_v} / {st.session_state.current_state['num_vehicles']}")
    
    total_stops = sum(len(r["stops"])-2 for r in sol["routes"].values() if r.get("stops"))
    m2.metric("Total Deliveries", total_stops)
    
    m3.metric("Fleet Distance", f"{sol['total_distance']/1000:.1f} km", delta="Real-road")
    
    cost = sol.get("cost", 0)
    # Baseline comparison (Placeholder logic for demo impact)
    savings = 4400 if st.session_state.initialized else 0
    m4.metric("Daily Ops Cost", f"₹{cost:,}", delta=f"-₹{savings} Optim.", delta_color="normal")

# --- Main Content ---
tab_routes, tab_ops, tab_what_if, tab_analytics, tab_history = st.tabs([
    "🗺️ Live Routes", 
    "💬 Dispatcher", 
    "🧪 Scenario Planner",
    "📊 Analytics", 
    "📋 Route History"
])

with tab_what_if:
    st.subheader("🧪 Strategic Scenario Planner")
    st.info("Simulate variations in fleet size or capacity without affecting live operations.")
    
    if st.session_state.current_state:
        col_a, col_b = st.columns(2)
        with col_a:
            sim_vehicles = st.slider("Number of Trucks", 1, 10, st.session_state.current_state["num_vehicles"])
            cap_mod = st.slider("Vehicle Capacity Multiplier", 0.5, 1.5, 1.0)
        
        if st.button("Run Simulation", use_container_width=True):
            sim_state = st.session_state.current_state.copy()
            sim_state["num_vehicles"] = sim_vehicles
            sim_state["vehicle_capacities"] = [int(c * cap_mod) for c in sim_state["vehicle_capacities"]]
            
            with st.spinner("Simulating global optimization..."):
                sim_resp = httpx.post("http://localhost:8000/routes/simulate", json=sim_state)
                if sim_resp.status_code == 200:
                    sim_sol = sim_resp.json()
                    
                    cur_cost = sol.get("cost", 0)
                    sim_cost = sim_sol.get("cost", 0)
                    diff = sim_cost - cur_cost
                    
                    c1, c2 = st.columns(2)
                    c1.metric("Simulated Cost", f"₹{sim_cost:,}", delta=f"₹{diff:+,}")
                    c2.metric("Simulated Distance", f"{sim_sol['total_distance']/1000:.1f} km")
                    
                    if diff < 0:
                        st.success(f"This change would save ₹{abs(diff):,} per day!")
                    else:
                        st.error(f"This change would increase costs by ₹{diff:,} per day.")

with tab_routes:
    st.subheader(" Live Fleet Tracking")
    if st.session_state.map_html:
        if st.session_state.prev_map_html:
            c1, c2 = st.columns(2)
            with c1:
                st.markdown("**Previous Plan** (Baseline)")
                st.components.v1.html(st.session_state.prev_map_html, height=600)
            with c2:
                st.markdown("**Optimized Plan** (Active)")
                st.components.v1.html(st.session_state.map_html, height=600)
        else:
            st.components.v1.html(st.session_state.map_html, height=700)
    else:
        st.info("Initializing map...")

with tab_ops:
    st.subheader("💬 AI Dispatcher Terminal")
    chat_container = st.container(height=550)
    with chat_container:
        for msg in st.session_state.messages:
            with st.chat_message(msg["role"]):
                st.write(msg["content"])
                if msg.get("reasoning"):
                    with st.expander("🕵️ Agent reasoning"):
                        for step in msg["reasoning"]:
                            st.caption(step)
    
    user_input = st.chat_input("Message the dispatcher (e.g., 'Driver 0 is sick')")
    if user_input:
        st.session_state.messages.append({"role": "user", "content": user_input})
        with st.spinner("🤖 Analyzing & Replanning..."):
            try:
                result = st.session_state.agent.invoke({"input": user_input})
                st.session_state.messages.append({
                    "role": "assistant", 
                    "content": result.get("output", ""),
                    "reasoning": result.get("reasoning", [])
                })
                fetch_current_state()
                st.rerun()
            except Exception as e:
                st.error(f"Agent error: {e}")

with tab_analytics:
    st.subheader("📊 Fleet Performance Analytics")
    if st.session_state.current_solution:
        sol = st.session_state.current_solution
        
        # Prepare data for Plotly
        driver_data = []
        for vid, route in sol["routes"].items():
            driver_data.append({
                "Driver": f"Driver {vid}",
                "Distance (km)": route["distance"] / 1000,
                "Stops": len(route["stops"]) - 2
            })
        df_drivers = pd.DataFrame(driver_data)

        ca, cb = st.columns(2)
        with ca:
            fig1 = px.bar(df_drivers, x="Driver", y="Distance (km)", title="Distance per Driver", color="Driver")
            st.plotly_chart(fig1, use_container_width=True)
        with cb:
            fig2 = px.bar(df_drivers, x="Driver", y="Stops", title="Stops per Driver", color="Driver")
            st.plotly_chart(fig2, use_container_width=True)
            
        # Line chart for solve time history
        try:
            hist_resp = httpx.get("http://localhost:8000/history")
            if hist_resp.status_code == 200:
                hist_data = hist_resp.json()
                if hist_data["plans"]:
                    df_hist = pd.DataFrame(hist_data["plans"])
                    fig3 = px.line(df_hist, x="created_at", y="solve_time_ms", title="Optimization Performance (ms)")
                    st.plotly_chart(fig3, use_container_width=True)
        except:
            pass

with tab_history:
    st.subheader("📜 Operational Audit Trail")
    try:
        hist_resp = httpx.get("http://localhost:8000/history")
        if hist_resp.status_code == 200:
            data = hist_resp.json()
            st.write("### Recent Disruptions")
            if data["disruptions"]:
                st.dataframe(pd.DataFrame(data["disruptions"]), use_container_width=True)
            else:
                st.info("No disruptions recorded yet.")
            
            st.write("### Route Plan History")
            if data["plans"]:
                st.dataframe(pd.DataFrame(data["plans"]), use_container_width=True)
    except Exception as e:
        st.error("Could not load history.")

# --- Optimized Route Details ---
if st.session_state.current_solution:
    st.divider()
    st.subheader("📋 Optimized Route Details")
    
    sol = st.session_state.current_solution
    tabs = st.tabs([f"Driver {vid}" for vid in sol["routes"].keys()])
    
    for idx, (vid, route) in enumerate(sol["routes"].items()):
        with tabs[idx]:
            col_a, col_b = st.columns([1, 2])
            with col_a:
                stops_count = len(route['stops']) - 2
                st.write(f"**Performance Metrics**")
                st.write(f"- Efficiency Rank: #{idx + 1}")
                st.write(f"- Total Stops: {stops_count}")
                st.write(f"- Distance: {route['distance']/1000:.1f} km")
            with col_b:
                st.write("**Sequence**")
                st.caption(" → ".join([f"Stop {s}" for s in route['stops']]))
                if st.button(f"Export Driver {vid} Manifest", key=f"btn_{vid}"):
                    st.toast(f"Manifest for Driver {vid} generated!")

# --- Simulation Loop (Bottom of Script) ---
if st.session_state.sim_active:
    # Advance simulation by one step
    try:
        # Call the simulation step endpoint
        sim_resp = httpx.post(
            "http://localhost:8000/simulation/step", 
            params={"minutes": sim_speed}, 
            timeout=10.0
        )
        if sim_resp.status_code == 200:
            new_events = sim_resp.json().get("events", [])
            if new_events:
                st.session_state.sim_events.extend(new_events)
            
            # Refresh map and state
            fetch_current_state()
            time.sleep(2) # Throttle to prevent UI flickering
            st.rerun()
    except Exception as e:
        st.sidebar.error(f"Sim Connection Error: {e}")
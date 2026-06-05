# ui/app.py
import streamlit as st
import httpx
import sys, os
from dotenv import load_dotenv
import pandas as pd
import plotly.express as px

# Load environment variables FIRST
load_dotenv()

sys.path.append(os.path.dirname(os.path.dirname(__file__)))
from agent.dispatcher_agent import build_dispatcher_agent

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
    }
    [data-testid="stMetricValue"] {
        font-size: 1.5rem !important;
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
    st.markdown("---")
    
    st.subheader("Fleet Status")
    if st.session_state.current_state and st.session_state.current_solution:
        state = st.session_state.current_state
        sol = st.session_state.current_solution
        unavailable = state.get("unavailable_drivers", [])
        for vid in range(state["num_vehicles"]):
            active = vid not in unavailable
            status_color = "🟢" if active else "🔴"
            # Calculate remaining stops (excluding depot start/end)
            route = sol["routes"].get(str(vid), {})
            stops_remaining = max(0, len(route.get("stops", [])) - 2) if active else 0
            st.markdown(f"{status_color} **Driver {vid}** — {stops_remaining} stops")
    else:
        st.caption("Waiting for initialization...")

    st.markdown("---")
    if st.button("🔄 Reset & Re-initialize", use_container_width=True):
        st.session_state.initialized = False
        st.session_state.messages = []
        st.session_state.prev_map_html = None
        st.session_state.map_html = None
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
        except Exception as e:
            st.error(f"Failed to auto-start: {e}")
            st.stop()

# --- Dashboard Metrics ---
if st.session_state.current_solution:
    sol = st.session_state.current_solution
    m1, m2, m3, m4 = st.columns(4)
    m1.metric("Active Vehicles", len(sol["routes"]))
    m2.metric("Total Stops", sum(len(r["stops"])-2 for r in sol["routes"].values()))
    m3.metric("Fleet Distance", f"{sol['total_distance']/1000:.1f} km")
    m4.metric("Status", "Optimized", delta="Ready")

# --- Main Content ---
tab_routes, tab_ops, tab_analytics, tab_history = st.tabs([
    "🗺️ Live Routes", 
    "💬 Dispatcher", 
    "📊 Analytics", 
    "📋 Route History"
])

with tab_routes:
    st.subheader("🗺️ Live Route Visualization")
    if st.session_state.map_html:
        if st.session_state.prev_map_html:
            c1, c2 = st.columns(2)
            with c1:
                st.caption("Previous Route Plan")
                st.components.v1.html(st.session_state.prev_map_html, height=600)
            with c2:
                st.caption("Updated Optimization")
                st.components.v1.html(st.session_state.map_html, height=600)
        else:
            st.components.v1.html(st.session_state.map_html, height=600)
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
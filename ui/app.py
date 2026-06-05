# ui/app.py
import streamlit as st
import httpx
import sys, os
from dotenv import load_dotenv

# Load environment variables FIRST
load_dotenv()

sys.path.append(os.path.dirname(os.path.dirname(__file__)))
from agent.dispatcher_agent import build_dispatcher_agent

# --- UI Configuration ---
st.set_page_config(
    page_title="FleetMind | AI Dispatcher",
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
    </style>
""", unsafe_allow_html=True)

if "initialized" not in st.session_state:
    st.session_state.initialized = False
if "current_solution" not in st.session_state:
    st.session_state.current_solution = None
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
            return data
    except Exception:
        pass
    return None

# --- Sidebar ---
with st.sidebar:
    st.image("https://cdn-icons-png.flaticon.com/512/2830/2830305.png", width=80)
    st.title("FleetMind AI")
    st.markdown("---")
    st.subheader("System Control")
    if st.button("🔄 Reset & Re-initialize", use_container_width=True):
        st.session_state.initialized = False
        st.session_state.messages = []
        st.rerun()
    
    st.markdown("---")
    st.info("Dispatcher AI is active and monitoring road conditions & driver availability.")

# --- Auto-Initialization Logic ---
if not st.session_state.initialized:
    sample_state = {
        "stops": [
            {"id": 0, "name": "Manhattan Logistics Center", "lat": 40.735, "lon": -74.006, "demand": 0},
            {"id": 1, "name": "Hell's Kitchen Delivery", "lat": 40.763, "lon": -73.992, "demand": 2},
            {"id": 2, "name": "UWS Apartments", "lat": 40.783, "lon": -73.980, "demand": 1},
            {"id": 3, "name": "UES Medical Center", "lat": 40.773, "lon": -73.956, "demand": 3},
            {"id": 4, "name": "Midtown Office Hub", "lat": 40.754, "lon": -73.972, "demand": 2},
            {"id": 5, "name": "Chelsea Market Drop-off", "lat": 40.746, "lon": -74.001, "demand": 4},
            {"id": 6, "name": "Washington Square Park", "lat": 40.733, "lon": -73.997, "demand": 1},
            {"id": 7, "name": "East Village Cafe", "lat": 40.729, "lon": -73.987, "demand": 2},
            {"id": 8, "name": "LES Retail Store", "lat": 40.715, "lon": -73.988, "demand": 3},
            {"id": 9, "name": "FiDi Tech Office", "lat": 40.707, "lon": -74.011, "demand": 2}
        ],
        "num_vehicles": 4,
        "vehicle_capacities": [10, 10, 10, 10],
        "depot_id": 0
    }
    with st.spinner("🚀 Initializing Optimized Fleet Routes..."):
        try:
            resp = httpx.post("http://localhost:8000/routes/initialize", json=sample_state, timeout=30.0)
            if resp.status_code == 200:
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

st.divider()

# --- Main Content ---
col1, col2 = st.columns([3, 1.5])

with col1:
    st.subheader("📍 Fleet Operations Map")
    try:
        map_resp = httpx.get("http://localhost:8000/routes/map", timeout=30.0)
        if map_resp.status_code == 200:
            html = map_resp.json().get("html", "")
            st.components.v1.html(html, height=600)
    except Exception as e:
        st.warning(f"Map temporarily unavailable: {e}")

with col2:
    st.subheader("💬 AI Dispatcher")
    
    chat_container = st.container(height=500)
    with chat_container:
        for msg in st.session_state.messages:
            with st.chat_message(msg["role"]):
                st.write(msg["content"])
    
    user_input = st.chat_input("Inform dispatcher of disruptions...")
    
    if user_input:
        st.session_state.messages.append({"role": "user", "content": user_input})
        with st.spinner("🤖 Analyzing & Replanning..."):
            try:
                result = st.session_state.agent.invoke({"input": user_input})
                response = result.get("output", "Processing complete.")
                st.session_state.messages.append({"role": "assistant", "content": response})
                fetch_current_state()
                st.rerun()
            except Exception as e:
                st.error(f"Agent error: {e}")

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
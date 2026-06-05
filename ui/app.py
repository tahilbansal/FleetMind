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
    [data-testid="stMetricValue"] {
        font-size: 1.5rem !important;
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

st.divider()

# --- Main Content ---
col1, col2 = st.columns([3, 1.5])

tab_ops, tab_history = st.tabs(["🚀 Live Operations", "📜 Operational History"])

with tab_ops:
    col1, col2 = st.columns([3, 1.5])
    with col1:
        st.subheader("📍 Fleet Operations Map")
        try:
            map_resp = httpx.get("http://localhost:8000/routes/map", timeout=30.0)
            if map_resp.status_code == 200:
                html = map_resp.json().get("html", "")
                st.components.v1.html(html, height=600)
        except Exception as e:
            st.warning(f"Map temporarily unavailable")

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

with tab_history:
    st.subheader("Optimization & Disruption Logs")
    try:
        hist_resp = httpx.get("http://localhost:8000/history")
        if hist_resp.status_code == 200:
            data = hist_resp.json()
            
            st.write("### Recent Disruptions")
            if data["disruptions"]:
                st.table(data["disruptions"])
            else:
                st.info("No disruptions recorded yet.")
                
            st.write("### Route Plan Performance")
            if data["plans"]:
                plan_data = [{
                    "Time": p["created_at"],
                    "Vehicles": p["num_vehicles"],
                    "Distance (km)": f"{p['total_distance_km']:.2f}",
                    "Solve Time (ms)": f"{p['solve_time_ms']:.1f}"
                } for p in data["plans"]]
                st.dataframe(plan_data, use_container_width=True)
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
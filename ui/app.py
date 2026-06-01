# ui/app.py
import streamlit as st
import httpx
import sys, os
from dotenv import load_dotenv

# Load environment variables FIRST
load_dotenv()

sys.path.append(os.path.dirname(os.path.dirname(__file__)))
from agent.dispatcher_agent import build_dispatcher_agent

st.set_page_config(page_title="AI Fleet Dispatcher", layout="wide")
st.title("🚛 AI Route Optimization — Disruption Handler")

# Initialize API state once
if "initialized" not in st.session_state:
    st.session_state.initialized = False

# Sidebar: initialization & controls
with st.sidebar:
    st.header("Fleet Setup")
    
    if not st.session_state.initialized:
        st.info("Initialize routes to begin")
        if st.button("Initialize Sample Routes"):
            sample_state = {
                "stops": [
                    {"id": 0, "name": "Depot", "lat": 40.7, "lon": -74.0, "demand": 0},
                    {"id": 1, "name": "Stop A", "lat": 40.75, "lon": -73.95, "demand": 3},
                    {"id": 2, "name": "Stop B", "lat": 40.72, "lon": -74.02, "demand": 3},
                    {"id": 3, "name": "Stop C", "lat": 40.68, "lon": -73.98, "demand": 2},
                    {"id": 4, "name": "Stop D", "lat": 40.74, "lon": -74.05, "demand": 2},
                ],
                "num_vehicles": 2,
                "vehicle_capacities": [5, 5],
                "depot_id": 0
            }
            try:
                with st.spinner("Initializing routes..."):
                    resp = httpx.post(
                        "http://localhost:8000/routes/initialize", 
                        json=sample_state,
                        timeout=30.0  # Increased timeout
                    )
                if resp.status_code == 200:
                    st.session_state.initialized = True
                    st.success("Routes initialized!")
                    st.rerun()
                else:
                    st.error(f"API returned {resp.status_code}: {resp.text}")
            except httpx.TimeoutException:
                st.error("Timeout! Make sure FastAPI server is running on port 8000")
            except Exception as e:
                st.error(f"Failed to initialize: {str(e)}")
    else:
        st.success("Routes initialized ✓")
        if st.button("Refresh Routes"):
            try:
                resp = httpx.get("http://localhost:8000/routes/current")
                data = resp.json()
                sol = data.get("solution", {})
                if sol and sol.get("routes"):
                    for vid, r in sol["routes"].items():
                        st.write(f"**Driver {vid}:** {len(r['stops'])-2} stops | "
                                 f"{r['distance']/1000:.1f}km")
            except Exception as e:
                st.error(f"Error: {e}")

# Main area: split into map + chat
col1, col2 = st.columns([3, 2])

with col1:
    st.subheader("Live Route Map")
    if st.session_state.initialized:
        if st.button("Load Map"):
            try:
                resp = httpx.get("http://localhost:8000/routes/map", timeout=10.0)
                if resp.status_code == 200:
                    html = resp.json().get("html", "")
                    st.components.v1.html(html, height=500, scrolling=True)
                else:
                    st.error(f"API error: {resp.status_code}")
            except Exception as e:
                st.error(f"Failed to load map: {e}")
    else:
        st.info("Initialize routes first in the sidebar")

with col2:
    st.subheader("Dispatcher Chat")
    
    if "agent" not in st.session_state:
        st.session_state.agent = build_dispatcher_agent()
    if "messages" not in st.session_state:
        st.session_state.messages = []
    
    # Display chat history
    for msg in st.session_state.messages:
        with st.chat_message(msg["role"]):
            st.write(msg["content"])
    
    # Input
    user_input = st.chat_input(
        "e.g. 'Driver 2 called in sick, reassign their stops'"
    )
    
    if user_input:
        st.session_state.messages.append({"role": "user", "content": user_input})
        with st.chat_message("user"):
            st.write(user_input)
        
        with st.chat_message("assistant"):
            with st.spinner("Replanning routes..."):
                try:
                    result = st.session_state.agent.invoke({"input": user_input})
                    response = result.get("output", "No response")
                    st.write(response)
                    st.session_state.messages.append(
                        {"role": "assistant", "content": response}
                    )
                except Exception as e:
                    st.error(f"Error: {str(e)}")
                    response = f"Error processing request: {str(e)}"
        
        # Auto-refresh map after replanning
        try:
            resp = httpx.get("http://localhost:8000/routes/map", timeout=10.0)
            html = resp.json().get("html", "")
            if html:
                st.components.v1.html(html, height=500, scrolling=True)
        except Exception as e:
            st.warning(f"Could not update map: {e}")
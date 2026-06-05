# FleetMind: AI-Powered Fleet Dispatch & Route Optimization

FleetMind is a production-ready Vehicle Routing Problem (VRP) management system. It combines Google OR-Tools for heavy-duty mathematical optimization with LLM-based agents to handle real-world disruptions like driver sickness or road closures through natural language.

## 🚀 Features

- **Advanced VRP Solver**: Utilizes Google OR-Tools to solve Capacitated Vehicle Routing Problems (CVRP).
- **AI Dispatcher Agent**: A LangChain-powered agent using Google Gemini to interpret dispatcher commands and call system tools.
- **Real-Road Routing**: Integration with OpenRouteService (ORS) for actual road geometries instead of straight-line distances.
- **Interactive Visualization**: Live-updating maps using Folium and Streamlit.
- **Dynamic Replanning**: Support for real-time disruptions (blocking roads, removing drivers) with instant route recalculation.

---

## 🛠️ Tech Stack

- **Backend**: FastAPI (Python)
- **Frontend**: Streamlit
- **Optimization**: Google OR-Tools
- **AI/LLM**: LangChain, Google Gemini API
- **Mapping**: Folium, OpenRouteService API
- **Data Validation**: Pydantic

---

## 📋 Prerequisites

- Python 3.9+
- A Google AI Studio API Key (for Gemini)
- An OpenRouteService API Key (for road-network maps)

---

## 🔧 Installation & Setup

1. **Clone the repository**:
   ```bash
   git clone https://github.com/your-repo/fleetmind.git
   cd fleetmind
   ```

2. **Create a virtual environment**:
   ```bash
   python -m venv venv
   source venv/bin/activate  # On Windows: venv\Scripts\activate
   ```

3. **Install dependencies**:
   ```bash
   pip install --upgrade pip && pip install -r requirements.txt
   ```

4. **Configure Environment Variables**:
   Create a `.env` file in the root directory:
   ```env
   GOOGLE_API_KEY=your_gemini_api_key_here
   ORS_API_KEY=your_openrouteservice_api_key_here
   ```

---

## 🚦 Running the Project

### 1. Start the Backend (FastAPI)
The backend handles the VRP logic and the agent tools.
```bash
python -m uvicorn api.main:app --reload --port 8000
```
The API will be available at `http://localhost:8000`. You can view the interactive documentation at `http://localhost:8000/docs`.

### 2. Start the Frontend (Streamlit)
The UI provides the dispatcher dashboard and map view.
```bash
streamlit run ui/app.py
```
The dashboard will open in your browser at `http://localhost:8501`.

---

## 📖 Usage Guide

1. **Initialize**: Use the sidebar in the Streamlit app to "Initialize Sample Routes". This sends the depot and stop data to the solver.
2. **View Map**: Click "Load Map" to see the optimized routes on a real-world map.
3. **Chat with Dispatcher**: Use the chat box to manage the fleet. 
   - *Example:* "Driver 0's truck broke down, reassign his stops."
   - *Example:* "The road between Stop 1 and Stop 2 is closed due to an accident."
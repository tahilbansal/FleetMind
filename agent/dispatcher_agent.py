# agent/dispatcher_agent.py
from langchain_google_genai import ChatGoogleGenerativeAI
from langchain_core.messages import HumanMessage
from agent.tools import (
    get_current_routes, mark_driver_unavailable,
    block_road_segment, get_stop_info
)
from dotenv import load_dotenv
load_dotenv()

def build_dispatcher_agent():
    """Simple agent wrapper that uses Gemini with tool binding"""
    
    tools = [
        get_current_routes,
        mark_driver_unavailable,
        block_road_segment,
        get_stop_info,
    ]
    
    llm = ChatGoogleGenerativeAI(
        model="gemini-3-flash-preview", 
        temperature=0
    )
    
    # Bind tools to LLM
    llm_with_tools = llm.bind_tools(tools)
    
    class SimpleAgent:
        def __init__(self, llm):
            self.llm = llm
            self.tools_dict = {tool.name: tool for tool in tools}
        
        def invoke(self, input_dict):
            user_input = input_dict.get("input", "")
            
            # Create message
            msg = HumanMessage(content=user_input)
            
            # Call LLM
            response = self.llm.invoke([msg])
            
            # Extract text response
            output = response.content if hasattr(response, 'content') else str(response)
            
            return {"output": output}
    
    return SimpleAgent(llm_with_tools)

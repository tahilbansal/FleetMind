# agent/dispatcher_agent.py
from langchain_google_genai import ChatGoogleGenerativeAI
from langchain_core.messages import HumanMessage, AIMessage, ToolMessage
from langchain_core.tools import tool
from agent.tools import get_current_routes, mark_driver_unavailable, block_road_segment, get_stop_info
import os

class DispatcherAgent:
    def __init__(self):
        api_key = os.getenv("GOOGLE_API_KEY")
        if not api_key:
            raise ValueError("GOOGLE_API_KEY not set in .env")
        
        self.llm = ChatGoogleGenerativeAI(model="gemini-2.5-flash", api_key=api_key)
        self.tools = {
            "get_current_routes": get_current_routes,
            "mark_driver_unavailable": mark_driver_unavailable,
            "block_road_segment": block_road_segment,
            "get_stop_info": get_stop_info,
        }
        self.llm_with_tools = self.llm.bind_tools([
            get_current_routes, 
            mark_driver_unavailable, 
            block_road_segment, 
            get_stop_info
        ])

    def invoke(self, input_dict):
        user_message = input_dict.get("input", "")
        messages = [HumanMessage(content=user_message)]
        
        max_iterations = 10
        iteration = 0
        
        while iteration < max_iterations:
            iteration += 1
            print(f"\n[Agent Iteration {iteration}]")
            
            response = self.llm_with_tools.invoke(messages)
            print(f"Response type: {type(response)}")
            print(f"Response content: {response.content if hasattr(response, 'content') else 'N/A'}")
            print(f"Tool calls present: {hasattr(response, 'tool_calls') and len(response.tool_calls) > 0}")
            
            messages.append(response)
            
            if not hasattr(response, 'tool_calls') or not response.tool_calls:
                final_text = response.content if hasattr(response, 'content') else str(response)
                print(f"[Agent] Final response: {final_text}")
                return {"output": final_text}
            
            tool_results_added = False
            for tool_call in response.tool_calls:
                tool_name = tool_call.get("name")
                tool_args = tool_call.get("args", {})
                tool_id = tool_call.get("id")
                
                print(f"  Calling: {tool_name}({tool_args})")
                
                if tool_name not in self.tools:
                    error_msg = f"Tool {tool_name} not found"
                    print(f"  ✗ {error_msg}")
                    messages.append(ToolMessage(content=error_msg, tool_call_id=tool_id))
                    tool_results_added = True
                    continue
                
                try:
                    tool = self.tools[tool_name]
                    if isinstance(tool_args, dict) and tool_args:
                        result = tool.invoke(tool_args)
                    else:
                        result = tool.invoke({})
                    print(f"  ✓ Result: {str(result)[:100]}...")
                except Exception as e:
                    result = f"Error: {str(e)}"
                    print(f"  ✗ {result}")
                
                messages.append(ToolMessage(content=str(result), tool_call_id=tool_id))
                tool_results_added = True
            
            if not tool_results_added:
                print("[Agent] No tools were called. Breaking to avoid infinite loop.")
                return {"output": response.content if hasattr(response, 'content') else "No response"}
        
        return {"output": f"Max iterations ({max_iterations}) reached without final response"}

def build_dispatcher_agent():
    return DispatcherAgent()

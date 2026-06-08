# agent/dispatcher_agent.py
from langchain_google_genai import ChatGoogleGenerativeAI
from langchain_core.messages import HumanMessage, AIMessage, ToolMessage
from langchain_core.tools import tool
from agents.tools import get_current_routes, mark_drivers_unavailable, block_road_segment, get_stop_info
import os

class DispatcherAgent:
    def __init__(self):
        api_key = os.getenv("GOOGLE_API_KEY")
        if not api_key:
            raise ValueError("GOOGLE_API_KEY not set in .env")
        
        # Keep gemini-3.5-flash as per your current configuration.
        self.llm = ChatGoogleGenerativeAI(model="gemini-3.5-flash", api_key=api_key)
        
        self.tools = {
            "get_current_routes": get_current_routes,
            "mark_drivers_unavailable": mark_drivers_unavailable,
            "block_road_segment": block_road_segment,
            "get_stop_info": get_stop_info,
        }
        self.llm_with_tools = self.llm.bind_tools([
            get_current_routes, 
            mark_drivers_unavailable, 
            block_road_segment, 
            get_stop_info
        ])

    def _get_clean_text(self, response):
        """Extracts plain text from LangChain message content, handling both strings and lists."""
        content = response.content if hasattr(response, 'content') else str(response)
        
        if isinstance(content, str):
            return content
        
        if isinstance(content, list):
            # Join all text parts, ignoring non-text components like signatures or metadata
            return "".join([part.get("text", "") if isinstance(part, dict) else str(part) for part in content])
            
        return str(content)

    def invoke(self, input_dict):
        user_message = input_dict.get("input", "")
        messages = [HumanMessage(content=user_message)]
        
        max_iterations = 10
        iteration = 0
        reasoning = []
        
        while iteration < max_iterations:
            iteration += 1
            
            response = self.llm_with_tools.invoke(messages)
            # Ensure the agent has time to process between potentially heavy tool calls
            
            messages.append(response)
            
            if not hasattr(response, 'tool_calls') or not response.tool_calls:
                final_text = self._get_clean_text(response)
                print(f"[Agent] Final response: {final_text}")
                return {"output": final_text, "reasoning": reasoning}
            
            tool_results_added = False
            for tool_call in response.tool_calls:
                tool_name = tool_call.get("name")
                tool_args = tool_call.get("args", {})
                tool_id = tool_call.get("id")
                
                reasoning.append(f"Calling tool: {tool_name}({tool_args})")
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
                
                reasoning.append(f"Tool result: {str(result)}")
                
                messages.append(ToolMessage(content=str(result), tool_call_id=tool_id))
                tool_results_added = True
            
            if not tool_results_added:
                print("[Agent] No tools were called. Breaking to avoid infinite loop.")
                final_text = self._get_clean_text(response)
                return {"output": final_text, "reasoning": reasoning}
        
        return {"output": f"Max iterations ({max_iterations}) reached without final response", "reasoning": reasoning}

def build_dispatcher_agent():
    return DispatcherAgent()

from typing import TypedDict, Sequence, Annotated
from dotenv import load_dotenv
from langchain_core.messages import AIMessage, HumanMessage, BaseMessage, ToolMessage, SystemMessage
from langchain_ollama import ChatOllama
from langchain_core.tools import tool
from langgraph.graph.message import add_messages
from langgraph.graph import StateGraph, START, END
import json, re
from pathlib import Path
from src.goal_interpretation.raw_prompt import prompt
from src.task_generation.task_generation import generate_graph_and_task
from src.goal_interpretation.prompt_specification import specificate_prompt

load_dotenv()

class AgentState(TypedDict):
    messages: Annotated[Sequence[BaseMessage], add_messages]
    scene_graph: dict
    task_description: str

@tool
def find_object(object_name: str, graph: dict = None) -> str:
    """Finds an object on scene by it's name (with synonims) and returns it's id, states, properties."""

    base_folder = Path.cwd() / "../../virtualhome/resources/"
    base_folder.resolve()
    all_states_path = base_folder / "object_states.json"
    all_properties_path = base_folder / "properties_data.json"
    synonyms_path = base_folder / "class_name_equivalence.json"
    with open (all_states_path, "r", encoding = 'utf-8') as f:
        all_states = json.load(f)
    with open (all_properties_path, "r", encoding = 'utf-8') as f:
        all_properties = json.load(f)
    with open (synonyms_path, "r", encoding = 'utf-8') as f:
        synonyms = json.load(f)

    object = ""
    known_ids = {}
    for node in graph['nodes']:
        raw_name, obj_id = node['class_name'], node['id']
        candidate_names = [raw_name] + synonyms.get(raw_name, [])
        if object_name not in candidate_names:
            continue

        states = [s.upper() for s in node.get('states', [])]

        known_ids[obj_id] = raw_name
        possible_states, properties = [], []
        
        for name in candidate_names:
            if name in all_states:
                possible_states = [s.upper() for s in all_states[name]]
                break
        for name in candidate_names:
            if name in all_properties:
                properties = [s.upper() for s in all_properties[name]]
                break  

        object = f"{raw_name}, id: {obj_id}, states: {states}, possible states: {possible_states}, properties: {properties}\n"

    return object

@tool
def get_relations(object_id: int, graph: dict = None) -> str:
    """Return all edges, connected with this node by id (both directions)"""

    connections = []

    for edge in graph['edges']:
        if edge['from_id'] == object_id or edge['to_id'] == object_id:
            to_node = edge['to_id'] if edge['from_id'] == object_id else object_id
            from_node = edge['from_id'] if edge['to_id'] == object_id else object_id
            
            connection = f"{to_node} IS {edge['relation_type']} TO {from_node}"
            connections.append(connection)
    return "\n".join(connections) or [{"info": "No relations found."}]
    
tools = [find_object, get_relations]
llm = ChatOllama(
    model="qwen3:8b",
    temperature=0.0,
    reasoning=False,
).bind_tools(tools)

def my_agent(state: AgentState):
    system_prompt = SystemMessage(content=specificate_prompt("3_1", 30, 20))
    goal_message = HumanMessage(content=f"Goal: {state['task_description']}")
                                
    all_messages = [system_prompt, goal_message] + list(state["messages"]) 
    
    response = llm.invoke(all_messages)

    # print(f"\n AI: {response.content}")
    # if hasattr(response, "tool_calls") and response.tool_calls:
        # print(f"USING TOOLS: {[tc['name'] for tc in response.tool_calls]}")

    return {"messages": [response]}

def should_continue(state : AgentState) -> str:
    """Determine if we should continue or end the reasoning."""
    last_message = state["messages"][-1]
    if isinstance(last_message, AIMessage):
        try:
            content = last_message.content.strip()
            content = re.sub(r"<think>.*?</think>", "", content, flags=re.DOTALL)
            content = content.strip()
            
            parsed = json.loads(content)
            node_goals = "node_goals" if "node_goals" in parsed else "node goals" if "node goals" in parsed else None
            edge_goals = "edge_goals" if "edge_goals" in parsed else "edge goals" if "edge goals" in parsed else None
            action_goals = "action_goals" if "action_goals" in parsed else "action goals" if "action goals" in parsed else None

            if node_goals and edge_goals and action_goals:
                # print(f"Found keys: {node_goals}, {edge_goals}, {action_goals} — GOAL INTERPRETATION COMPLETE")
                return "end"
            else:
                missing = []
                if not node_goals: missing.append("node_goals / node goals")
                if not edge_goals: missing.append("edge_goals / edge goals")
                if not action_goals: missing.append("action_goals / action goals")
                # print(f"Missing keys: {missing}. Found: {list(parsed.keys())}")
        except Exception as e:
            # print(f"JSON parse error: {e}")
            pass
    return "continue"

def tool_executor_node(state: AgentState) -> dict:
    """Custom tool node that injects scene_graph from state into tool calls."""
    messages = state["messages"]
    last_message = messages[-1]

    if not hasattr(last_message, "tool_calls") or not last_message.tool_calls:
        return {"messages": []}

    tool_outputs = []
    for tool_call in last_message.tool_calls:
        tool_name = tool_call["name"]
        args = tool_call["args"]

        if tool_name == "find_object":
            result = find_object.invoke({**args, "graph" :state["scene_graph"]})
        elif tool_name == "get_relations":
            args["object_id"] = int(args["object_id"])
            result = get_relations.invoke({**args, "graph" : state["scene_graph"]})
        else:
            result = f"Unknown tool: {tool_name}"

        tool_message = ToolMessage(
            content=str(result),
            name=tool_name,
            tool_call_id=tool_call["id"]
        )
        tool_outputs.append(tool_message)

    return {"messages": tool_outputs}

graph = StateGraph(AgentState)
graph.add_node("agent", my_agent)
graph.add_node("tools", tool_executor_node)

graph.set_entry_point("agent")
graph.add_edge("agent","tools")

graph.add_conditional_edges(
    "tools",
    should_continue,
    {
        "continue" : "agent",
        "end" : END,
    },
)
app = graph.compile()

def run_model(id_task : str, max_iterations=10):
    task_name, init_graph = generate_graph_and_task(id_task)
    initial_state = AgentState(
        messages=[],
        scene_graph=init_graph,
        task_description=task_name
    )
    state = initial_state
    parsed = None
    for i in range(max_iterations):
        state = app.invoke(state)
        last_message = state['messages'][-1]
        if isinstance(last_message, AIMessage):
            try:
                content = last_message.content.strip()
                content = re.sub(r"<think>.*?</think>", "", content, flags=re.DOTALL).strip()
                parsed = json.loads(content)
                if all(key in parsed for key in [
                    "node_goals", "edge_goals", "action_goals"
                ]) or all(key in parsed for key in [
                    "node goals", "edge goals", "action goals"
                ]):
                    break
            except Exception as e:
                print(f"Iteration {i+1}: JSON parse error: {e}")
                print(f"Content was: {repr(content[:200])}...")
        else:
            print(f"Iteration {i+1}: Last message not AIMessage")
    else:
        print("Max iterations reached. Returning last result.")

    return  parsed, state['scene_graph'], state['task_description']
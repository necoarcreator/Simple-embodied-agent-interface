import json, re, subprocess
from pathlib import Path
from typing import TypedDict, Sequence, Annotated
from dotenv import load_dotenv
from langchain_core.messages import AIMessage, HumanMessage, BaseMessage, ToolMessage, SystemMessage
from langchain_ollama import ChatOllama
from langchain_core.tools import tool
from langgraph.graph.message import add_messages
from langgraph.graph import StateGraph, START, END
from warnings import filterwarnings
from pprint import pprint

from src.action_sequencing.raw_prompt import prompt
from src.task_generation.task_generation import generate_graph_and_task
from src.action_sequencing.prompt_specification import specificate_prompt

filterwarnings('ignore')
load_dotenv()

class AgentState(TypedDict):
    messages: Annotated[Sequence[BaseMessage], add_messages]
    scene_graph: dict
    subgoal_list : list[str]

def validate_pddl_output(pddl_text) -> tuple[bool, str]:
    if "=== domain.pddl ===" not in pddl_text:
        return False, "Missing domain.pddl"
    if "=== problem.pddl ===" not in pddl_text:
        return False, "Missing problem.pddl"
    if pddl_text.count("=== domain.pddl ===") > 1:
        return False, "Duplicate domain.pddl"
    if pddl_text.count("=== problem.pddl ===") > 1:
        return False, "Duplicate problem.pddl"
    
    pddl_paths = (Path.cwd() / ".." / ".." / "ff-planner-docker" / "actual_plans").resolve()
    domain_path, problem_path = pddl_paths / "domain.pddl", pddl_paths / "problem.pddl"

    pattern = r"=== domain\.pddl ===\s*(.*?)\s*=== problem\.pddl ===\s*(.*)"
    match = re.search(pattern, pddl_text, re.DOTALL)
    
    domain_text, problem_text = match.group(1).strip(), match.group(2).strip()
    
    with open(domain_path, "w", encoding='utf-8') as f:
        f.write(domain_text)
    with open(problem_path, "w", encoding='utf-8') as f:
        f.write(problem_text)

    return True, "OK"

def run_planner(domain_name : str, problem_name : str) -> str:
    """
    Runs Fast Downward classic PDDL planner and returns the optimal plan if possible.
    Arguments: 
    domain_path - the name of generated domain file, e.g. "domain.pddl"
    problem_name - the name of generated problem file, e.g. "problem.pddl"
    Note that those names are the same as you generated before.

    """
    base_path = (Path.cwd() / ".." / ".." / "ff-planner-docker" / "actual_plans").resolve()
    
    # Используем только имена файлов для передачи в контейнер
    domain_filename = Path(domain_name).name  # "domain.pddl"
    problem_filename = Path(problem_name).name  # "problem.pddl"

    # Путь к плану
    plan_filename = "plan.pddl"
    plan_file_host = base_path / plan_filename  # Путь на хосте
    plan_file_container = f"/planning/{plan_filename}" # Путь на докер образе 
    
    # Монтируем всю папку base_path в /planning
    cmd = [
        "docker", "run", "--rm",
        "--memory=1g",
        "-v", f"{base_path}:/planning",
        "downward-planner",
        "--plan-file", plan_file_container,
        f"/planning/{domain_filename}",
        f"/planning/{problem_filename}",
        "--search", "astar(lmcut())",
    ]
    # удаляем старый план во избежание багов
    if plan_file_host.exists():
        plan_file_host.unlink() 
        
    result = subprocess.run(cmd, capture_output=True, text=True, encoding='utf-8')
    
    if result.returncode  == 0:
        if plan_file_host.exists():
            with open(plan_file_host, "r", encoding="utf-8") as f:
                plan_content = f.read().strip()
            return plan_content
        
    log = result.stderr if result.stderr else result.stdout
    if 1 <= result.returncode  < 10:
        return "Partly successful termination: at least one plan was \
                        found and another component ran out of memory."
    elif 10 <= result.returncode  < 20:
        return "Unsuccessful, but error-free termination: task is unsolvable."
    elif 20 <= result.returncode  < 30:
        return "Expected failures which prevent the execution of further components: \
                                                                    OOM / Timeout."
    else:
        return f"Unrecoverable failure: {log}"

@tool
def plan_from_pddl(pddl_text: str) -> str:
    """
    Parses the pddl_text string and tries to run it using PDDL planner.
    Output is the plan if possible, otherwise error message is returned.
    
    The input pddl_text should contain a valid PDDL description of the task:
    === domain.pddl ===
    ...
    === problem.pddl ===
    ...
    If the plan is infeasible after many attempts, print __plan_unsolvable__. It will stop iterations.
    """
    is_valid, message = validate_pddl_output(pddl_text)
    if not is_valid:
        return f"PDDL parsing error: {message}"
    
    plan_result = run_planner("domain.pddl", "problem.pddl")
    return plan_result
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

tools = [plan_from_pddl, find_object, get_relations]
llm = ChatOllama(
    model="qwen3:8b",
    temperature=0.0,
    reasoning=False,
).bind_tools(tools)

def my_agent(state: AgentState):
                                
    all_messages = list(state["messages"]) 
    
    response = llm.invoke(all_messages)

    print(f"\n AI: {response.content}")
    if hasattr(response, "tool_calls") and response.tool_calls:
        print(f"USING TOOLS: {[tc['name'] for tc in response.tool_calls]}")

    return {"messages": [response]}

def update_subgoals_from_scene(state: AgentState) -> None:
    """
    Updates state["subgoal_list"] by removing goals that are satisfied in state["scene_graph"].
    Assumes both are lists of strings (e.g., "NEXT_TO(robot.1, toilet.37)").
    """
    raise NotImplementedError("Yet to be implemented: need to pass .pddl plan to VirtualHome executor" \
                                    "and update the graph scene, then check if LTL subgoals are achieved")
    
def should_continue(state : AgentState) -> str:
    """Determine if we should continue or end the reasoning."""
    last_message = state["messages"][-1]
    if isinstance(last_message, ToolMessage) and last_message.tool_calls:
        for tool_call in last_message.tool_calls:
            if tool_call["name"] == "plan_from_pddl":
                # Только после вызова plan_from_pddl обновляем подцели
                update_subgoals_from_scene(state)
                break

    if len(state["subgoal_list"]) == 0: # если все цели выполнены
                return "success"
    
    if isinstance(last_message, AIMessage):
        try:
            content = last_message.content.strip()
            content = re.sub(r"<think>.*?</think>", "", content, flags=re.DOTALL)
            content = content.strip()
            
            parsed = json.loads(content)
            
            unsolvable = True if "__plan_unsolvable__" in parsed else None
            if unsolvable:
                return "fail"
            
        except Exception as e:
            print(f"JSON parse error: {e}")
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
        elif tool_name == "plan_from_pddl":
            args["pddl_text"] = str(args["pddl_text"])
            result = plan_from_pddl.invoke({**args})
        else:
            result = f"Unknown tool: {tool_name}"

        tool_message = ToolMessage(
            content=str(result),
            name=tool_name,
            tool_call_id=tool_call["id"]
        )
        tool_outputs.append(tool_message)

    return {"messages": tool_outputs}

def node_success(state: AgentState):
    state["messages"].append(AIMessage(content='{"status": "success", "message": "All goals achieved"}'))
    return state

def node_fail(state: AgentState):
    state["messages"].append(AIMessage(content='{"status": "fail", "message": "Plann is infeasible"}'))
    return state

graph = StateGraph(AgentState)
graph.add_node("agent", my_agent)
graph.add_node("tools", tool_executor_node)
graph.add_node("success", node_success)
graph.add_node("fail", node_fail)

graph.set_entry_point("agent")
graph.add_edge("agent","tools")
graph.add_conditional_edges(
    "tools",
    should_continue,
    {
        "continue" : "agent",
        "fail" : "fail", 
        "success" : "success",
    },
)
graph.add_edge("success", END)
graph.add_edge("fail", END)

app = graph.compile()

def run_model(num_task, max_iterations=10):
    
    prompt, subgoals = specificate_prompt(num_task, max_iterations)
    _, init_graph = generate_graph_and_task(num_task)
    
    system_prompt = SystemMessage(content=prompt)
    initial_state = AgentState(
        messages=[system_prompt],
        scene_graph=init_graph,
        subgoal_list=subgoals
    )

    state = initial_state
    for i in range(max_iterations):
        state = app.invoke(state)
        last_message = state['messages'][-1]
        if isinstance(last_message, AIMessage) and "status" in last_message.content:
            return last_message.content
        pprint(last_message.content)
    


    

            

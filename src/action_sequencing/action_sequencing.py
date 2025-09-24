import json, re, subprocess
from pathlib import Path
from typing import TypedDict, Sequence, Annotated
from dotenv import load_dotenv
from langchain_core.messages import AIMessage, BaseMessage, ToolMessage, SystemMessage
from langchain_ollama import ChatOllama
from langchain_core.tools import tool
from langgraph.graph.message import add_messages
from langgraph.graph import StateGraph, START, END
from warnings import filterwarnings
from pprint import pprint

from src.action_sequencing.raw_prompt import prompt
from src.task_generation.task_generation import generate_graph_and_task, add_possible_states_to_graph 
from src.action_sequencing.prompt_specification import specificate_prompt

filterwarnings('ignore')
load_dotenv()

# TODO: почему-то не срабатывает остановка генерации при >=3 pddl_attempts создать pddl план. Нужно отладить
class AgentState(TypedDict):
    messages: Annotated[Sequence[BaseMessage], add_messages]
    scene_graph: dict
    subgoal_list : list[str]
    pddl_attempts : int

def validate_pddl_output(pddl_text : str) -> tuple[bool, str]:
    """
    Получает сгенерированный pddl как строку и пытается распарсить её.
    Возвращает флаг, получилось ли распарсить и лог возможных ошибок.
    Проверяет не только наличие === domain.pddl === и === problem.pddl ===,
    но и отсутствие дупликатов, а также базово синтаксис планов (на уровне скобочной последовательности).
    Сохраняет задачу и домен в папку "ff-planner-docker.actual_plans".
    """
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

    domain_start = pddl_text.find("=== domain.pddl ===") + len("=== domain.pddl ===")
    problem_start = pddl_text.find("=== problem.pddl ===")
    
    if domain_start == -1 or problem_start == -1:
        return False, "Could not locate PDDL blocks"

    # Извлекаем domain (от конца заголовка до начала problem)
    domain_text = pddl_text[domain_start:problem_start].strip()

    # TODO: надо парсить не до конца строки, а как-то научиться отделять мусор генерации после конца problem.pddl.
    # Извлекаем problem (от конца заголовка problem до конца строки)
    problem_end_marker = "=== problem.pddl ==="
    problem_start_idx = pddl_text.find(problem_end_marker) + len(problem_end_marker)
    problem_text = pddl_text[problem_start_idx:].strip()

    # Проверим скобочную последовательность по балансу числа скобок.
    if domain_text.count('(') != domain_text.count(')'):
        return False, f"Domain PDDL has unbalanced parentheses. Open: {domain_text.count('(')}, Close: {domain_text.count(')')}"
    if problem_text.count('(') != problem_text.count(')'):
        return False, f"Problem PDDL has unbalanced parentheses. Open: {problem_text.count('(')}, Close: {problem_text.count(')')}"
    
    with open(domain_path, "w", encoding='utf-8') as f:
        f.write(domain_text)
    with open(problem_path, "w", encoding='utf-8') as f:
        f.write(problem_text)

    return True, "OK"

def run_planner(domain_name : str, problem_name : str) -> str:
    """
    Запускает классический планировщик PDDL Fast Downward через docker + subprocess
    и возвращает оптимальный план, если это возможно.

    Аргументы:
    domain_path - имя сгенерированного файла домена, например, "domain.pddl"
    problem_name - имя сгенерированного файла задачи, например, "problem.pddl"
    Важно, что эти имена должны совпадать с теми, которые агент сгенерировал ранее.
    """
    base_path = (Path.cwd() / ".." / ".." / "ff-planner-docker" / "actual_plans").resolve()
    
    # Важно не перепутать имена файлов в докер-контейнере и на хосте.
    domain_filename = Path(domain_name).name
    problem_filename = Path(problem_name).name

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
    # удаляем старый план во избежание багов генерации
    if plan_file_host.exists():
        plan_file_host.unlink() 
        
    result = subprocess.run(cmd, capture_output=True, text=True, encoding='utf-8')
    
    # Если выполнение плана успешно, возвращаем ответ планировщика
    if result.returncode  == 0:
        if plan_file_host.exists():
            with open(plan_file_host, "r", encoding="utf-8") as f:
                plan_content = f.read().strip()
            return f"Success: {plan_content}"
        
    # Отправляем логи агенту. См. https://www.fast-downward.org/latest/documentation/exit-codes/
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

# решил добавить one-shot прямо в докстринг, чтобы агент не забывал синтаксис планов.
@tool
def plan_from_pddl(pddl_text: str) -> str:
    """
    Parses the pddl_text string and tries to run it using PDDL planner.
    Output is the optimal plan if possible, otherwise error message is returned.
    
    The input pddl_text should contain a valid PDDL description of the task:
    === domain.pddl ===
    ...
    === problem.pddl ===
    ...
    Use this function to make best plans.
    Example usage:
    === domain.pddl ===
    (define (domain home-robot)
    (:requirements :strips :typing)
    (:types agent object)
    (:predicates
        ; COPY ALL predicates from "Available Actions" and "Target Subgoal Plan"
        (next_to ?a - agent ?o - object)
        (facing ?a - agent ?o - object)
        (on ?o - object)
        (off ?o - object)
        ; ADD others as needed
    )
    ; DEFINE actions from "Available Actions"
    (:action walk
        :parameters (?a - agent ?o - object)
        :precondition ()
        :effect (next_to ?a ?o)
    )
    (:action turnto
        :parameters (?a - agent ?o - object)
        :precondition (next_to ?a ?o)
        :effect (facing ?a ?o)
    )
    ; ... add other actions
    )
    === problem.pddl ===
    (define (problem robot-task-1)
    (:domain home-robot)
    (:objects
        ; LIST ALL objects from LTL plan and Current State
        robot.1 - agent   ; ← BUT CHECK: is it robot.1 or character.65? Use ID from find_object!
        bathroom.1 - object
        toilet.37 - object
    )
    (:init
        ; COPY ALL from Current State + add properties from find_object
        (inside toilet.37 bathroom.1)
        (clean toilet.37)
        (has_switch computer.417) ; ← only if property exists
    )
    (:goal (and
        ; COPY ALL from Target Subgoal Plan, converted to PDDL
        (next_to robot.1 bathroom.1)
        (facing robot.1 bathroom.1)
        ; ... etc
    ))
    )
    """
    is_valid, message = validate_pddl_output(pddl_text)
    if not is_valid:
        return f"PDDL parsing error: {message}"
    
    plan_result = run_planner("domain.pddl", "problem.pddl")
    return plan_result

@tool
def find_object(object_name: str, graph: dict = None) -> str:
    """Static search for object name matches
    (up to a synonym: synonym lists are stated in the specific file).
    Returns: the object, its properties and states: current and possible.
    An agent should only pass the object_name field, the graph wil be passed automatically.
    """

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
    """Static search for relationships for a target object (by ID match).
    Returns: a string with all relationships involving the object
    (without names, only IDs).
    An agent should only pass the object_id field, the graph wil be passed automatically.
    """

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
    num_predict=512, 
).bind_tools(tools)

def my_agent(state: AgentState):
                                
    all_messages = list(state["messages"]) 
    
    response = llm.invoke(all_messages)

    print(f"\n AI: {response.content}")
    if hasattr(response, "tool_calls") and response.tool_calls:
        print(f"USING TOOLS: {[tc['name'] for tc in response.tool_calls]}")
    else:
        print("NO TOOLS CALLED — just thinking...")

    return {"messages": [response]}

def update_subgoals_from_scene(state: AgentState) -> None:
    """
    Обновляет state["subgoal_list"], удаляя цели, которые выполнены в state["scene_graph"].
    """
    raise NotImplementedError("Yet to be implemented: need to pass .pddl plan to VirtualHome executor" \
                                    "and update the graph scene, then check if LTL subgoals are achieved")
    
def should_continue(state : AgentState) -> str:
    """Определяет, нужно ли продолжать генерацию. 
    Останавливает, если после вызова планировщика:
    а) синтаксис был валидным, можно было составить оптимальный план -> success;
    б) синтаксис был валидным, но план оказался неразрешимым -> fail;
    в) агент сдался сам после нескольких попыток и написал код завершения в ответе __plan_unsolvable__ -> fail.
    """
    last_message = state["messages"][-1]
    if isinstance(last_message, ToolMessage) and last_message.name == "plan_from_pddl":
        content = last_message.content.strip()

        if content.startswith("Success:"):
            return "success"

        if "Partly successful termination" in content or "Unsuccessful, but error-free" in content:
            return "fail"  # задача неразрешима

    elif isinstance(last_message, AIMessage):
        try:
            content = last_message.content
            content = re.sub(r"<think>.*?</think>", "", content, flags=re.DOTALL).strip()
            if "__plan_unsolvable__" in content:
                return "fail"
        except:
            pass
        
    return "continue"

def tool_executor_node(state: AgentState) -> dict:
    """
    Кастомная нода langgraph для вызова tools с замыканием, чтобы модели не приходилось самой передавать
    граф сцены как параметр.
    """

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

            # TODO: здесь не отрабатывает принудительная остановка вызова тулза, если было >= 3 pddl_attempts.
            state["pddl_attempts"] = state.get("pddl_attempts", 0) + 1
            if state["pddl_attempts"] >= 3:
                return {"messages": "You've reached the limit of callings \
                                    - plan is considered to be infeasible"} 
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

def node_success(state: AgentState) -> dict:
    """
    Нода - заглушка, добавляющая в конец сообщение об успешном выполнении целей.
    """
    new_messages = state['messages'] + [AIMessage(content='{"status": "success", "message": "All goals achieved"}')]
    return {'messages' : new_messages}

def node_fail(state: AgentState) -> dict:
    """
    Нода - заглушка, добавляющая в конец сообщение о неудаче при выполнении целей.
    """
    new_messages = state['messages'] + [AIMessage(content='{"status": "fail", "message": "Plan is infeasible"}')]
    return {'messages' : new_messages}

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
# TODO: почему-то не отрабатывает как следует и всё равно = 25. Проверить документацию.
config = {"recursion_limit": 50}

def run_model(num_task, max_iterations=10):
    
    prompt, subgoals = specificate_prompt(num_task, max_iterations)
    _, init_graph = generate_graph_and_task(num_task)
    # добавляем ещё и поле possible_states
    add_possible_states_to_graph(init_graph)

    system_prompt = SystemMessage(content=prompt)
    initial_state = AgentState(
        messages=[system_prompt],
        scene_graph=init_graph,
        subgoal_list=subgoals,
        pddl_attempts=0
    )

    state = initial_state
    for i in range(max_iterations):
        state = app.invoke(state, config)
        last_message = state['messages'][-1]
        pprint(last_message.content)
        
        if isinstance(last_message, ToolMessage) and last_message.name == "plan_from_pddl":
            plan_content = last_message.content.strip()
            if plan_content and "failure" not in plan_content and not plan_content.startswith("PDDL"):
                return {"status": "success", "plan": plan_content}

        # Tcли агент признал провал
        if isinstance(last_message, AIMessage):
            content = last_message.content.strip()
            if "__plan_unsolvable__" in content or '"status": "fail"' in content:
                return {"status": "fail", "message": "Plan is infeasible"}
            
    return {"status": "fail", "message": "Max iterations reached"}
    


    

            

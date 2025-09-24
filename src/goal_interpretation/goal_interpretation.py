from typing import TypedDict, Sequence, Annotated
from dotenv import load_dotenv
from langchain_core.messages import AIMessage, HumanMessage, BaseMessage, ToolMessage, SystemMessage
from langchain_huggingface import HuggingFaceEmbeddings
from langchain_core.documents import Document
from langchain_ollama import ChatOllama
from langchain_core.tools import tool
from langgraph.graph.message import add_messages
from langgraph.graph import StateGraph, START, END
import shutil, json, re
from pathlib import Path
from src.goal_interpretation.raw_prompt import prompt
from src.task_generation.task_generation import generate_graph_and_task, add_possible_states_to_graph 
from src.goal_interpretation.prompt_specification import specificate_prompt
import networkx as nx
from langchain_chroma import Chroma

load_dotenv()

import sys
import math

# Патч для старых версий networkx, которые пытаются импортировать gcd из fractions
if 'fractions' not in sys.modules:
    import fractions
    if not hasattr(fractions, 'gcd'):
        fractions.gcd = math.gcd
else:
    fractions_module = sys.modules['fractions']
    if not hasattr(fractions_module, 'gcd'):
        fractions_module.gcd = math.gcd

class AgentState(TypedDict):
    messages: Annotated[Sequence[BaseMessage], add_messages]
    scene_graph: dict
    task_description: str


def expand_graph_context(graph: dict, seed_node_ids: list[int], depth: int = 1) -> tuple[set, set]:
    """
    Расширяет контекст от seed нод на заданную глубину.
    Возвращает множество всех затронутых node_id и edge_id.
    """
    G = nx.DiGraph()
    
    # Строим граф из scene_graph
    for node in graph['nodes']:
        G.add_node(node['id'], **node)
    
    for edge in graph['edges']:
        G.add_edge(edge['from_id'], edge['to_id'], **edge)

    visited_nodes = set(seed_node_ids)
    visited_edges = set()

    current_level = set(seed_node_ids)
    for _ in range(depth):
        next_level = set()
        for node_id in current_level:
            # Исходящие и входящие рёбра
            for succ in G.successors(node_id):
                edge_data = G.get_edge_data(node_id, succ)
                visited_edges.add((node_id, succ, edge_data['relation_type']))
                next_level.add(succ)
            for pred in G.predecessors(node_id):
                edge_data = G.get_edge_data(pred, node_id)
                visited_edges.add((pred, node_id, edge_data['relation_type']))
                next_level.add(pred)
        visited_nodes.update(next_level)
        current_level = next_level
        if not current_level:
            break

    return visited_nodes, visited_edges

def scene_graph_to_documents(graph: dict) -> list[Document]:
    """
    Превращает объекты и связи графа сцены в документы для RAG 
    с айди для удобного ретрива и расширения контекста.
    Возвращает: список документов.
    """
    documents = []
    node_id_to_name = {}

    # Обрабатываем ноды
    for node in graph['nodes']:
        obj_id = node['id']
        class_name = node['class_name']
        possible_states = node.get('possible_states', [])
        states = node.get('states', [])
        node_id_to_name[obj_id] = class_name

        content = f"Object: {class_name} (ID: {obj_id})"
        if states:
            content += f", States: {', '.join(states)}"
        if possible_states:
            content += f", Possible States: {', '.join(possible_states)}"

        doc = Document(
            page_content=content,
            metadata={
                "type": "node",
                "id": obj_id,
                "class_name": class_name,
                "states": ", ".join(states) if states else "None",
                "possible_states": ", ".join(possible_states) if possible_states else "None"
            }
        )
        documents.append(doc)

    # И связи между ними
    for edge in graph['edges']:
        from_id = edge['from_id']
        to_id = edge['to_id']
        relation = edge['relation_type']
        
        from_name = node_id_to_name.get(from_id, f"Node_{from_id}")
        to_name = node_id_to_name.get(to_id, f"Node_{to_id}")

        content = f"{from_name} ({from_id}) --[{relation}]--> {to_name} ({to_id})"
        
        doc = Document(
            page_content=content,
            metadata={
                "type": "edge",
                "from_id": from_id,
                "to_id": to_id,
                "relation": relation,
                "from_name": from_name,
                "to_name": to_name
            }
        )
        documents.append(doc)

    return documents

################################################################ Бейслайн: статический ретрив с глубиной = 1

def run_baseline_model(id_task : str, max_iterations : int = 10) ->tuple[dict, dict, str]:
    """
    Запускает goal_interpretation модуль с глубиной обхода объектов и связей = 1.
    Модуль представляет собой ReAct агента, который получает задачу на естественном языке и
    должен, пользуясь поиском по графу сцены, составить набор конечных состояний графа, 
    набор связей, которые должны быть изменены, план действий для робота. 
    Возвращает json с полями node_goals, edge_goals, action_goals.
    """
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
        
    tools = [find_object, get_relations]
    llm = ChatOllama(
        model="qwen3:8b",
        temperature=0.0,
        reasoning=False,
    ).bind_tools(tools)

    def my_agent(state: AgentState):
        # TODO: плохой вызов примера задачи. Нужно модифицировать и сделать не 
        # хардкод - версию такого системного промпта.
        system_prompt = SystemMessage(content=specificate_prompt("3_1", 30, 20))
        goal_message = HumanMessage(content=f"Goal: {state['task_description']}")
                                    
        all_messages = [system_prompt, goal_message] + list(state["messages"]) 
        
        response = llm.invoke(all_messages)

        # print(f"\n AI: {response.content}")
        # if hasattr(response, "tool_calls") and response.tool_calls:
            # print(f"USING TOOLS: {[tc['name'] for tc in response.tool_calls]}")

        return {"messages": [response]}

    def should_continue(state : AgentState) -> str:
        """
        Определяет, надо ли продолжать генерацию.
        Есть поля node_goals, edge_goals, action_goals в ответе => заканчиваем.
        """
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

            # ключевая особенность тут: обычный ToolNode не позволяет передавать именованные параметры.
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

    ###################### запуск агента

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


################################ RAG + более удобное использование инструментов + глубина поиска > 1
# use_possible_states : True, если вы хотите добавить их в свойства узлов, иначе False


def run_rag_model(id_task : str, max_iterations : int = 10, use_possible_states : bool = True):
    task_name, init_graph = generate_graph_and_task(id_task)

    # добавляем ещё и поле possible_states
    if use_possible_states:
        add_possible_states_to_graph(init_graph)

    # загружаем граф как список документов
    documents = scene_graph_to_documents(init_graph)
    # и ретривер
    embeddings = HuggingFaceEmbeddings(model_name="all-MiniLM-L6-v2")

    # Создаём фиксированную временную папку внутри проекта
    temp_dir = Path.cwd() / "chroma_cache" / f"session_{id_task}"
    if temp_dir.exists():
        shutil.rmtree(temp_dir, ignore_errors=True)  # пробуем удалить, если осталась от прошлого запуска
    temp_dir.mkdir(parents=True, exist_ok=True)

    try:
        vectorstore = Chroma.from_documents(
            documents=documents,
            embedding=embeddings,
            persist_directory=str(temp_dir),
            collection_name="scene_graph_rag"
        )
        retriever = vectorstore.as_retriever(search_kwargs={"k": 5})
    except Exception as e:
        print(f"Error creating vectorstore: {e}")
        raise
    finally:
        # Опционально: удаляем после использования (если не нужно сохранять)
        # shutil.rmtree(temp_dir, ignore_errors=True)
        pass
    @tool
    def graph_rag_tool(query: str, depth: int = 1) -> str:
        """
        Search for objects or relations in the scene graph using semantic similarity.
        Then expand context to include neighbors up to non-negative 'depth' steps away.
        Returns structured information about found entities and their surroundings.
        Example calls:
        - query = "Find chairs near a table", depth = 1
        - query = "What is connected to the fridge?", depth = 5
        - query = "Objects that can be turned on and are in the kitchen", depth = 4
        """
        # Используем init_graph и retriever из замыкания!
        nonlocal init_graph, retriever

        if not retriever:
            return "Error: Retriever not initialized."

        docs = retriever.invoke(query)
        if not docs:
            return "No relevant objects or relations found in the scene graph."

        # Собираем множество увиденных объектов
        seed_node_ids = set()
        for doc in docs:
            meta = doc.metadata
            if meta["type"] == "node":
                seed_node_ids.add(meta["id"])
            elif meta["type"] == "edge":
                seed_node_ids.add(meta["from_id"])
                seed_node_ids.add(meta["to_id"])

        if not seed_node_ids:
            return "Found only edges, but no connected nodes to expand from."

        # Расширяем контекст
        expanded_nodes, expanded_edges = expand_graph_context(
            init_graph, list(seed_node_ids), depth=depth
        )

        # Формируем ответ
        result_lines = []
        result_lines.append(f"Query: '{query}'")
        result_lines.append(f"Seed nodes: {list(seed_node_ids)}")
        result_lines.append(f"Expanded to depth {depth}: {len(expanded_nodes)} nodes, {len(expanded_edges)} edges\n")

        # Добавляем информацию о нодах
        node_map = {node['id']: node for node in init_graph['nodes']}
        for nid in expanded_nodes:
            node = node_map.get(nid, {})
            name = node.get('class_name', f"Node_{nid}")
            states = node.get('states', [])
            possible_states = node.get('possible_states', [])
            states_str = ", ".join(states) if states else "None"
            possible_states_str = ", ".join(possible_states) if possible_states else "None"
            result_lines.append(f"[NODE] {name} (ID: {nid}) | States: {states_str} | Possible states {possible_states_str}")

        # Добавляем информацию о рёбрах
        for from_id, to_id, relation in expanded_edges:
            from_name = node_map.get(from_id, {}).get('class_name', f"Node_{from_id}")
            to_name = node_map.get(to_id, {}).get('class_name', f"Node_{to_id}")
            result_lines.append(f"[EDGE] {from_name} ({from_id}) --[{relation}]--> {to_name} ({to_id})")

        return "\n".join(result_lines)

    tools = [graph_rag_tool]
    llm = ChatOllama(
        model="qwen3:8b",
        temperature=0.0,
        reasoning=False,
    ).bind_tools(tools)

    def my_agent(state: AgentState):
        # TODO: аналогично, сделать вызов системного промпта менее грубым
        system_prompt = SystemMessage(content=specificate_prompt("3_1", 30, 20))
        goal_message = HumanMessage(content=f"Goal: {state['task_description']}")
                                    
        all_messages = [system_prompt, goal_message] + list(state["messages"]) 
        # TODO: добавить конфиг с recursion_limit > 25
        response = llm.invoke(all_messages)

        """ print(f"\n AI: {response.content}")
        if hasattr(response, "tool_calls") and response.tool_calls:
            print(f"USING TOOLS: {[tc['name'] for tc in response.tool_calls]}")
        """
        return {"messages": [response]}

    def should_continue(state : AgentState) -> str:
        """
        Определяет, надо ли продолжать генерацию.
        Есть поля node_goals, edge_goals, action_goals в ответе => заканчиваем.
        """
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

            if tool_name == "graph_rag_tool":
                query = args.get("query", "")
                depth = args.get("depth", 1)
                result = graph_rag_tool.invoke({"query": query, "depth": depth})
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

    ###################### запуск агента

    initial_state = AgentState(
        messages=[],
        scene_graph=init_graph,
        task_description=task_name
    )
    state = initial_state
    parsed = None
    for i in range(max_iterations):
        # TODO: добавить конфиг с recursion_limit > 25
        state = app.invoke(state)
        last_message = state['messages'][-1]
        # print(last_message.content)
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
                # print(f"Content was: {repr(content[:200])}...")
        else:
            print(f"Iteration {i+1}: Last message not AIMessage")
    else:
        print("Max iterations reached. Returning last result.")

    return  parsed, state['scene_graph'], state['task_description']
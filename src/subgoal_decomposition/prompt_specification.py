from src.subgoal_decomposition.raw_prompt_old import prompt
from src.goal_interpretation.goal_interpretation import run_model
from pathlib import Path
import json, re
from src.task_generation.task_generation import *

def find_init_states(relevant_objects, init_graph):
    base_folder = Path.cwd() / "../../virtualhome/resources/"
    base_folder.resolve()
    synonyms_path = base_folder / "class_name_equivalence.json"
    with open (synonyms_path, "r", encoding = 'utf-8') as f:
        synonyms = json.load(f)

    sufficient_init_graph = ["Objects:", ]
    unique_objects = []
    known_ids = {}
    for obj_name in relevant_objects:
        candidate_names = [obj_name] + synonyms.get(obj_name, [])
        for node in init_graph['nodes']:
            node_name = node['class_name']
            node_id = node['id']
            obj = f"{node['class_name']}.{node_id}"
            if obj not in unique_objects:
                unique_objects.append(obj)
            if node_name in candidate_names:
                known_ids[node_id] = obj
                category = node['category']
                states = ", ".join([s.upper() for s in node.get('states', [])])
                properties = ", ".join([s.upper() for s in node.get('properties', [])])
                new_obj = f"Name : {node_name}; id : {node_id}; category : {category}; states : {states}; properties : {properties}"
                sufficient_init_graph.append(new_obj)
                break
    sufficient_init_graph.append("Relations:")
    for obj_id in known_ids:
        for edge in init_graph['edges']:
            if edge['from_id'] in known_ids and edge['to_id'] in known_ids:
                new_rel = f"{edge['relation_type']}({known_ids[edge['from_id']]}, {known_ids[edge['to_id']]})"
                sufficient_init_graph.append(new_rel)

    return "\n".join(sufficient_init_graph), ", ".join(unique_objects)

def specificate_prompt(id_task : str, num_trials = 10):
    goal_dict, raw_graph, task_description  = run_model(id_task, num_trials)

    node_goals_list = goal_dict.get('node_goals') or goal_dict.get('node goals') or []
    edge_goals_list = goal_dict.get('edge_goals') or goal_dict.get('edge goals') or []
    action_goals_list = goal_dict.get('action_goals') or goal_dict.get('action goals') or []


    obj_names = set()
    for node in node_goals_list:
        if node['name'] not in obj_names:
            obj_names.add(node['name'])
        
    for edge in edge_goals_list:
        if edge['from_name'] not in obj_names:
            obj_names.add(edge['from_name'])
        if edge['to_name'] not in obj_names:
            obj_names.add(edge['to_name'])

    node_goals = ", ".join(str(item) for item in node_goals_list) + "\n"
    edge_goals = ", ".join(str(item) for item in edge_goals_list) + "\n"
    action_goals = ", ".join(str(item) for item in action_goals_list) + "\n"

    relevant = ', '.join([str(item) for item in obj_names])
    init_graph, all_found_objects = find_init_states(obj_names, raw_graph)

    
    necessity = "True" if action_goals else "False"

    relations_types = get_relation_types()
    
    action_space = get_action_space()

    prompt_with_desc = prompt.replace("<task_name>", task_description)
    prompt_with_node_goals = prompt_with_desc.replace("<node_goals>", node_goals)
    prompt_with_edge_goals = prompt_with_node_goals.replace("<edge_goals>", edge_goals)
    prompt_with_action_goals = prompt_with_edge_goals.replace("<action_goals>", action_goals)
    prompt_with_necessity = prompt_with_action_goals.replace("<necessity>", necessity)

    prompt_with_relevants = prompt_with_necessity.replace("<relevant_objects>", relevant)
    prompt_with_initial_states = prompt_with_relevants.replace("<initial_states>", init_graph)
    prompt_with_relations = prompt_with_initial_states.replace("<relation_types>", relations_types)
    prompt_with_action_space = prompt_with_relations.replace("<action_space>", action_space)
    final_prompt = prompt_with_action_space.replace("<objects_seen>", all_found_objects)
    

    return final_prompt, relevant, init_graph
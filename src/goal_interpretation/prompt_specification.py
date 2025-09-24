from src.goal_interpretation.raw_prompt_old import prompt
import json 
from src.task_generation.task_generation import *

def specificate_prompt(task_id : str, num_objects : int = 20, num_relations : int = 20) -> str:
    """
    Переписывает шаблон промпта goal interpretation модуля под задачу с айди task_id.
    Статически в контекст первые num_objects объектов и num_relations отношений между ними.
    Возвращает готовый к использованию промпт.
    """
    goal, init_gr = generate_graph_and_task(task_id)

    object_in_scene, relations_in_scene = formate_init_graph(init_gr, num_objects)

    relations_types = get_relation_types()
    
    action_space = get_action_space()


    prompt_with_objects = prompt.replace("<object_in_scene>", object_in_scene)
    prompt_with_relations = prompt_with_objects.replace("<relations_in_scene>", relations_in_scene)
    prompt_with_relations_types = prompt_with_relations.replace("<relation_types>", relations_types)
    prompt_with_action_space = prompt_with_relations_types.replace("<action_space>", action_space)
    final_prompt = prompt_with_action_space.replace("<goal_str>", goal)

    return final_prompt
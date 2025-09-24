from src.action_sequencing.raw_prompt import prompt
from src.subgoal_decomposition.subgoal_decomposition import run_model
from src.task_generation.task_generation import *

def parse_subgoals(subgoal_dict : dict, filter_actions : bool = False) -> list[str]:
    """
    Делит подцели предыдущего модуля на цели-состояния и остальные. При filter_actions = True
    оставляет только цели-состояния, иначе - передаёт как есть. Возвращает список целей.
    """
    raw_output = subgoal_dict['output']
    
    if filter_actions or not subgoal_dict['necessity_to_use_action']:
        # Удаляем строки, которые выглядят как действия (содержат '(' и не являются известными состояниями)
        state_only = []
        state_predicates = {
            'NEXT_TO', 'FACING', 'ON', 'OFF', 'OPEN', 'CLOSED', 'PLUGGED_IN', 'PLUGGED_OUT',
            'SITTING', 'LYING', 'CLEAN', 'DIRTY', 'ONTOP', 'INSIDE', 'BETWEEN', 'HOLDS_RH', 'HOLDS_LH'
        }
        for item in raw_output:
            pred_name = item.split('(')[0] if '(' in item else item
            if pred_name in state_predicates:
                state_only.append(item)
        output_list = state_only
    else:
        output_list = raw_output

    return output_list

def specificate_prompt(task_id : str, num_trials : int = 10) -> tuple[str, list[str]]:
    """
    Создаёт готовый для использования промпт для модуля action_sequencing. 
    Проброшенные через предыдущий модуль имена, состояния и связи объектов нужны 
    здесь для добавления контекста.
    Очередь подцелей пробрасывается в agent state модуля, а там на каждом шаге 
    моделирования в среде проверяется, какие из подцелей выполнены и удаляются из очереди.
    Когда очередь становится пустой, срабатывает should_continue и останавливает генерацию.
    
    Задача этого модуля - создать валидную .pddl задачу и проверить её выполнимость, получить 
    оптимальный план от классического планировщика.
    """
    subgoal_dict, relevant_objs, seen_graph  = run_model(task_id, num_trials)

    subgoals = parse_subgoals(subgoal_dict)
    subgoals_for_prompt = "\n".join(subgoals)

    relations_types = get_relation_types()
    action_space = get_action_space()

    prompt_with_relevant_objs = prompt.replace("<relevant_objs>", relevant_objs)
    prompt_with_seen_graph = prompt_with_relevant_objs.replace("<current_predicates>", seen_graph)
    prompt_with_relations_types = prompt_with_seen_graph.replace("<relations_types>", relations_types)
    prompt_with_action_space = prompt_with_relations_types.replace("<actions_space>", action_space)
    final_prompt = prompt_with_action_space.replace("<ltl_output>", subgoals_for_prompt)

    return final_prompt, subgoals
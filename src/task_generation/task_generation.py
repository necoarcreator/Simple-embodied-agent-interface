import json
from pathlib import Path

def generate_graph_and_task(num_task):
    base_folder = Path.cwd()

    graph_path = base_folder / "../../virtualhome/dataset/programs_processed_precond_nograb_morepreconds"
    graph_path = graph_path.resolve()

    init_gr_path = graph_path / "init_and_final_graphs" / "TrimmedTestScene1_graph" / "graphs"
    executables_path = graph_path / "executable_programs" / "TrimmedTestScene1_graph" / "executables"

    init_gr_files = [f.name for f in init_gr_path.glob('*.json')]
    executables_files = [f.name for f in executables_path.glob('*.txt')]
    init_gr_files.sort(), executables_files.sort()

    with open (init_gr_path / f"{init_gr_files[num_task]}", "r", encoding='utf-8') as f:
        init_graph = json.load(f)
    with open (executables_path / f"{executables_files[num_task]}", "r", encoding='utf-8') as f:
        executable = f.read()

    real_task_name = executable[:executable.index('\n', executable.index('\n') + 1)]

    return real_task_name, init_graph['init_graph']


def formate_init_graph(graph, context_num_objects = 100, context_num_connections = 100):
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


    objects = []
    known_ids = {}
    for node in graph['nodes'][:context_num_objects]:
        raw_name, obj_id = node['class_name'], node['id']
        states = [s.upper() for s in node.get('states', [])]

        known_ids[obj_id] = raw_name
        possible_states, properties = [], []
        candidate_names = [raw_name] + synonyms.get(raw_name, [])
        for name in candidate_names:
            if name in all_states:
                possible_states = [s.upper() for s in all_states[name]]
                break
        for name in candidate_names:
            if name in all_properties:
                properties = [s.upper() for s in all_properties[name]]
                break  

        object = f"{raw_name}, id: {obj_id}, states: {states}, possible states: {possible_states}, properties: {properties}"
        objects.append(object)

    connections = []
    for edge in graph['edges'][:context_num_connections]:
        if edge['from_id'] in known_ids and edge['to_id'] in known_ids:
            connection = f"{known_ids[edge['from_id']]} ({edge['from_id']}) IS {edge['relation_type']} TO {known_ids[edge['to_id']]} ({edge['to_id']})"
            connections.append(connection)

    
    return "\n".join(objects), "\n".join(connections)
    
def get_relation_types():
    base_folder = Path.cwd() / "../../virtualhome/resources/"
    base_folder.resolve()
    relations_path = base_folder / "relation_types.json"
    with open (relations_path, "r", encoding = 'utf-8') as f:
        relations = json.load(f)

    lines = []
    for relation, description in relations.items():
        line = f"{relation.upper()} : {description}"
        lines.append(line)
    return "\n".join(lines)

def get_action_space():
    base_folder = Path.cwd() / "../../virtualhome/resources/"
    base_folder.resolve()
    actions_path = base_folder / "action_space.json"
    with open (actions_path, "r", encoding = 'utf-8') as f:
        actions = json.load(f)

    lines = []
    for action, description in actions.items():
        line = f"{action.upper()} : {description}"
        lines.append(line)
    return "\n".join(lines)


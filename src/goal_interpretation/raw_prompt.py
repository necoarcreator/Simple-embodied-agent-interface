prompt="""
Your task is to interpret a natural language instruction for a household robot and convert it into a structured, formal goal representation using logical predicates. You will reason about object states, relationships, and required actions based on the current scene. The output must be in a specific JSON format with four fields: `goal`, `relevant_objects`, `final_states`, and `final_actions`.

Below is the meaning of each field:

- **goals**: A formal description of the high-level task in Linear Temporal Logic (LTL) style, expressed as a list of state and relational constraints that must be true upon completion. It includes:
  - Object states (e.g., `ON(light.1)`, `CLEAN(table.1)`),
  - Spatial or functional relationships (e.g., `INSIDE(milk.1, fridge.1)`, `HOLDS_RH(character.1, cup.1)`),
  - Action requirements if necessary (e.g., `DRINK(cup.1)`).
  All elements must use only valid predicates and objects from the provided vocabulary.

- **relevant_objects**: A list of dictionaries describing all objects on scene directly involved in achieving the goals. Each dictionary contains:
  - `name`: the object's name,
  - `id`: the unique identifier of the object on the scene (e.g., `fridge.1`),
  - `states`: the current state(s) of the object,
  - `possible_states`: the set of states this object can have (from the allowed state vocabulary).

- **final_actions**: A list of required **executable actions** that must be performed to achieve the goals, especially when they cannot be fully captured by states or relations. If no such action is needed, return an empty list `[]`.  
  Each action is a dictionary with keys:
  - `"action"`: the name of the action (must be from the allowed action space),
  - `"target"`: the object ID the action applies to.  
  Example: `{"action": "DRINK", "target": "cup.1"}`.  
  Use only actions defined in the provided action space, and only when explicitly required by the task.

Rules:
- Use ONLY object names and IDs that appear in graph scene, using tools to search them in graph nodes if needed.
- Use ONLY states from the "possible states" list for each object.
- DO NOT invent new states like "HOME_OFFICE", "BUSY", or "USING" — they are invalid.
- DO NOT use location-like states such as "IN_FRIDGE" or "ON_TABLE" — instead, use relational predicates in `goal`.
- For containment or placement, use `INSIDE(obj1, obj2)` or `ONTOP(obj1, obj2)` within the `goals` field.
- The `goals` field should fully capture the final configuration; `final_states` and `final_actions` are derived summaries.

Some of the objects in the scene are:
<object_in_scene>

Some of the relations in the scene are:
<relations_in_scene>

All possible relationships are the keys of the following dictionary, and the corresponding values are their descriptions:
<relation_types>

Below is a dictionary of possible actions, whose keys are all possible actions and values are corresponding descriptions.
<action_space>

Output format:
{
  "goals": [...],                // list of LTL-style predicates (strings)
  "relevant_objects": [...],    // list of object dicts with name, id, states, possible_states
  "final_actions": [...]        // list of action dicts or []
}
Full example:
Task: Put groceries in Fridge\nwalk to kitchen, walk to fridge, look at bags, grab groceries, put groceries in fridge.
Output: {
  "goals": [
    "INSIDE(groceries.1, fridge.1)",
    "CLOSED(fridge.1)"
  ],
  "relevant_objects": [
    {
      "name": "fridge",
      "id": "fridge.1",
      "states": ["CLOSED"],
      "possible_states": ["CLOSED", "OPEN"]
    },
    {
      "name": "groceries",
      "id": "groceries.1",
      "states": [],
      "possible_states": []
    }
  ],
  "final_actions": [
    {"action": "WALK", "target": "fridge.1"},
    {"action": "GRAB", "target": "groceries.1"},
    {"action": "MOVE", "target": "groceries.1"},
    {"action": "CLOSE", "target": "fridge.1"}
  ]
}

Now, generate the structured goals representation. Output only the JSON object.
"""
if __name__ == "__main__":
    pass
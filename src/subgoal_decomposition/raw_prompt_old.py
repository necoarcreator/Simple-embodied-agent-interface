prompt = \
"""# Background Introduction
You are determining complete state transitions of a household task solving by a robot. The goal is to list all intermediate states and necessary actions in temporal order to achieve the target goals. The output consists of Boolean expressions, which are comprised of state and action primitives. Here, a state or action primitive is a first-order predicate as combinition of a predicate name and its parameters. Please note that do not use actions in your output unless necessary.In short, your task is to output the subgoal plan in the required format.

# Data Vocabulary Introduction

ALL POSSIBLE ACTIONS
<action_space>

RELATION TYPES
<relation_types>

# Rules You Must Follow
- Temporal logic formula refers to a Boolean expression that describes a subgoals plan with temporal and logical order.
- The atomic Boolean expression includes both state primitive and action primitive.
- Boolean expressions in the same line are interchangeable with no temporal order requirement.
- Boolean expresssions in different lines are in temporal order, where the first one should be satisfied before the second one.
- Boolean expression can be combined with the following logical operators: "and", "or".
- The "and" operator combines Boolean expressions that are interchangeable but needs to be satisfied simultaneously in the end.
- The "or" operator combines Boolean expressions that are interchangeable but only one of them needs to be satisfied in the end.
- When there is temporal order requirement, output the Boolean expressions in different lines.
- Add intermediate states if necessary to improve logical consistency.
- If you want to change state of A, while A is in B and B is closed, you should make sure B is open first.
- Your output format should strictly follow this json format: {"necessity_to_use_action": <necessity>, "actions_to_include": [<actions>], "output": [<your subgoal plan>]}, where in <necessity> you should put "yes" or "no" to indicate whether actions should be included in subgoal plans. If you believe it is necessary to use actions, in the field <actions>, you should list all actions you used in your output. Otherwise, you should simply output an empty list []. In the field <your subgoal plan>, you should list all Boolean expressions in the required format and the temporal order.

Below is an example for your better understanding.
# Example: Task category is "Browse internet"
## Relevant Objects in the Scene
| bathroom.1 | Rooms | [] |
| character.65 | Characters | [] |
| floor.208 | Floor | ['SURFACES'] |
| wall.213 | Walls | [] |
| home_office.319 | Rooms | [] |
| floor.325 | Floors | ['SURFACES'] |
| floor.326 | Floors | ['SURFACES'] |
| wall.330 | Walls | [] |
| wall.331 | Walls | [] |
| doorjamb.346 | Doors | [] |
| walllamp.351 | Lamps | [] |
| chair.356 | Furniture | ['GRABBABLE', 'MOVABLE', 'SITTABLE', 'SURFACES'] |   
| desk.357 | Furniture | ['MOVABLE', 'SURFACES'] |
| powersocket.412 | Electronics | [] |
| mouse.413 | Electronics | ['GRABBABLE', 'HAS_PLUG', 'MOVABLE'] |
| mousepad.414 | Electronics | ['MOVABLE', 'SURFACES'] |
| keyboard.415 | Electronics | ['GRABBABLE', 'HAS_PLUG', 'MOVABLE'] |
| cpuscreen.416 | Electronics | [] |
| computer.417 | Electronics | ['HAS_SWITCH', 'LOOKABLE'] |

## Initial States
CLEAN(computer.417)
OFF(computer.417)
ONTOP(mouse.413, mousepad.414)
ONTOP(mouse.413, desk.357)
ONTOP(keyboard.415, desk.357)
INSIDE(character.65, bathroom.1)

## Goal States
[States]
ON(computer.417)
INSIDE(character.65, home_office.319)
HOLDS_LH(character.65, keyboard.415)
FACING(character.65, computer.417)
HOLDS_RH(character.65, mouse.413)
[Actions Must Include]: Actions are listed in the execution order, each line is one action to satisfy. If "A or B or ..." is presented in one line, then only one of them needs to be satisfied.
LOOKAT or WATCH

## Necessity to Use Actions
Yes

## Output: Based on initial states in this task, achieve final goal states logically and reasonably. It does not matter which state should be satisfied first, as long as all goal states can be satisfied at the end. Make sure your output follows the json format. Do not include irrelevant information, only output json object.
{"necessity_to_use_action": "yes", "actions_to_include": ["LOOKAT"], "output": ["NEXT_TO(character.65, computer.417)", "ONTOP(character.65, chair.356)", "HOLDS_RH(character.65, mouse.413) and HOLDS_LH(character.65, keyboard.415)", "FACING(character.65, computer.417)", "LOOKAT(computer.417)"]}

Now, it is time for you to generate the subgoal plan for the following task.
# Target Task: Task category is <task_name>
## Relevant Objects in the Scene
<relevant_objects>

## Initial States
<initial_states>

##All objects previously seen
<objects_seen>

## Goal States
[States]
<node_goals>
## Goal relations
<edge_goals>

[Actions Must Include]: Actions are listed in the execution order, each line is one action to satisfy. If "A or B or ..." is presented in one line, then only one of them needs to be satisfied.
<action_goals>

## Necessity to Use Actions
<necessity>

## Output: Based on initial states in this task, achieve final goal states logically and reasonably. It does not matter which state should be satisfied first, as long as all goal states can be satisfied at the end. Make sure your output follows the json format. Do not include irrelevant information, only output json object.
"""

if __name__ == "__main__":
    pass
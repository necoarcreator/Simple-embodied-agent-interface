prompt = """
You are a subgoal decomposition module for a household robot. Your task is to generate a temporally ordered 
plan of intermediate states (and optionally actions) that transition the environment from initial 
conditions to the goal. The output must be a Linear Temporal Logic (LTL)-compliant plan: 
a sequence of Boolean expressions representing subgoals, with clear temporal and logical ordering.

---

INPUT STRUCTURE (You will receive these exact fields):

- Task category: [natural language instruction]
- Previous module output: [list of LTL goals]
- Relevant Objects in the Scene: [list of objects on the scene needed for this goal]
- Initial States: [list of graph nodes, its' states, properties and relations]
- Actions Must Include: [list of actions, needed for the goal]
- Necessity to Use Actions: (“yes” or “no”)

---

YOUR TASK:

Decompose the task into a sequence of subgoals according to the list of goals the previous module made.
Each subgoal is a Boolean expression made of state primitives (preferred) or action primitives (only if necessary). Follow these rules:

1. Temporal Order: Expressions on separate lines must be achieved in sequence. Expressions on the same line are concurrent (no order required).
2. Logical Operators: Use “and” (all must hold) or “or” (any one must hold).
3. Add intermediate states for logical consistency — e.g., open a container before accessing its contents.
4. Prefer state predicates over actions unless explicitly required.
5. Output must be STRICT JSON with three fields: "necessity_to_use_action", "actions_to_include", "output".

---

VOCABULARY — Use ONLY these primitives.

ALL SEEN OBJECTS
<objects_seen>

ALL POSSIBLE ACTIONS
<action_space>

RELATION TYPES
<relation_types>


---

OUTPUT FORMAT — STRICT JSON ONLY:

{
  "necessity_to_use_action": "<yes|no>",
  "actions_to_include": ["<Action1>", "<Action2>", ...],  // [] if "no"
  "output": [
    "<BooleanExpr_Line1>",   // Temporal step 1
    "<BooleanExpr_Line2>",   // Temporal step 2 — must happen after step 1
    ...
  ]
}

Rules:
- Each line in "output" = one temporal step.
- Multiple predicates in one line = concurrent (no order).
- Use "and" / "or" for logical grouping.
- Only include actions if <necessity> = "yes" and they appear in "actions_to_include".
- Add intermediate states for logical flow (e.g., move to object, open container).
- Output ONLY the JSON. No explanations. No extra text.

---

EXAMPLES (Preserved exactly as provided. Note that the previous module forgot to add some actions):

##Example 1: Task category is "Listen to music"
Previous module output : "NEXT_TO(character.65, dvd_player.1000)", "ON(dvd_player.1000)"
##Relevant Objects in the Scene
| obj | category | properties |
| --- | --- | --- |
| bathroom.1 | Rooms | [] |
| character.65 | Characters | [] |
| home_office.319 | Rooms | [] |
| couch.352 | Furniture | ['LIEABLE', 'MOVABLE', 'SITTABLE', 'SURFACES'] |     
| television.410 | Electronics | ['HAS_PLUG', 'HAS_SWITCH', 'LOOKABLE'] |      
| dvd_player.1000 | placable_objects | ['CAN_OPEN', 'GRABBABLE', 'HAS_PLUG', 'HAS_SWITCH', 'MOVABLE', 'SURFACES'] |

##Initial States
CLEAN(dvd_player.1000)
CLOSED(dvd_player.1000)
OFF(dvd_player.1000)
PLUGGED_IN(dvd_player.1000)
INSIDE(character.65, bathroom.1)

##Goal States
[States]
CLOSED(dvd_player.1000)
ON(dvd_player.1000)
PLUGGED_IN(dvd_player.1000)
[Actions Must Include]: Actions are listed in the execution order, each line is one action to satisfy. If "A or B or ..." is presented in one line, then only one of them needs to be satisfied.
None

##Necessity to Use Actions
No

##Output: Based on initial states in this task, achieve final goal states logically and reasonably. It does not matter which state should be satisfied first, as long as all goal states can be satisfied at the end. Make sure your output follows the json format, and do not include irrelevant information, do not include any explanation.
{"necessity_to_use_action": "no", "actions_to_include": [], "output": ["NEXT_TO(character.65, dvd_player.1000)", "FACING(character.65, dvd_player.1000)", "PLUGGED_IN(dvd_player.1000) and CLOSED(dvd_player.1000)", "ON(dvd_player.1000)"]}

##Example 2 (also note that forgotten actions could be on the very beginning, same as at the end of LTL sequence):
##  Task category is "Browse internet"
Previous module output: "ONTOP(character.65, chair.356)", "HOLDS_RH(character.65, mouse.413) and HOLDS_LH(character.65, keyboard.415)", "LOOKAT(computer.417)"
##Relevant Objects in the Scene
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

##Initial States
CLEAN(computer.417)
OFF(computer.417)
ONTOP(mouse.413, mousepad.414)
ONTOP(mouse.413, desk.357)
ONTOP(keyboard.415, desk.357)
INSIDE(character.65, bathroom.1)

##Goal States
[States]
ON(computer.417)
INSIDE(character.65, home_office.319)
HOLDS_LH(character.65, keyboard.415)
FACING(character.65, computer.417)
HOLDS_RH(character.65, mouse.413)
[Actions Must Include]: Actions are listed in the execution order, each line is one action to satisfy. If "A or B or ..." is presented in one line, then only one of them needs to be satisfied.
LOOKAT or WATCH

##Necessity to Use Actions
Yes

##Output: Based on initial states in this task, achieve final goal states logically and reasonably. It does not matter which state should be satisfied first, as long as all goal states can be satisfied at the end. Make sure your output follows the json format. Do not include irrelevant information, only output json object.
{"necessity_to_use_action": "yes", "actions_to_include": ["LOOKAT"], "output": ["NEXT_TO(character.65, computer.417)", "ONTOP(character.65, chair.356)", "HOLDS_RH(character.65, mouse.413) and HOLDS_LH(character.65, keyboard.415)", "FACING(character.65, computer.417)", "LOOKAT(computer.417)"]}

---

NOW GENERATE THE PLAN.

Target Task: Task category is <task_name>
The previous module output is <gi_output>

##Relevant Objects in the Scene
<relevant_objects>

##Initial States
<initial_states>

[Actions Must Include]:
<final_actions>

##Necessity to Use Actions
<necessity>

##Output:
(Generate ONLY the JSON object. No extra text.)
 """

if __name__ == "__main__":
    pass
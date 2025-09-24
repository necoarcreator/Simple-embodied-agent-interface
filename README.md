# Simple-embodied-agent-interface

Implementation of goal interpretation, subgoal decomposition, and action sequencing modules for an embodied agent in the VirtualHome simulator.    
This project is built as a modular pipeline to interface with the [Embodied Agent Interface (EAI)](https://github.com/embodied-agent-interface/embodied-agent-interface) evaluation framework, [Fast-Downward classical planner](https://github.com/aibasel/downward) and [VirtualHome simulator](https://github.com/xavierpuigf/virtualhome) resourses.  

---

## 📌 Overview  

This repository implements three core modules for an embodied agent:  
- **Goal Interpretation**: Parses natural language goals into structured symbolic representations.  
- **Subgoal Decomposition**: Breaks down high-level symbolic goals into LTL-logical queue of subgoals.  
- **Action Sequencing**: Generates .pddl plans from LTL-logical queue of subgoals using ReAct + LLM+P agent. The output is a valid PDDL plan if possible (and performing a step in the simulator environment in future versions).  

The pipeline uses prompts, few-shot examples, ReAct agents, LLP+P agents, structured output validation. Experiments and metrics are tracked via `sandbox.ipynb`, which serves as the main entry point.  

> ⚠️ **Important**: To validate your outputs against EAI’s official metrics, you must install the [Embodied Agent Interface](https://github.com/embodied-agent-interface/embodied-agent-interface).  


## 🗂️ Project Structure  
simple-embodied-agent-interface/  
├── src/  
│ ├── task_generation/ # Utilities for task selection, scene graph, synonyms, state/relation dicts, EAI ID mapping  
│ │ └── sandbox.ipynb # 🎯 Main entry point: experiments, metric calculation, module orchestration  
│ ├── goal_interpretation/ # System prompt, task-specific prompt generation, ReAct agent / ReAct + graph RAG agent, structured output validation  
│ ├── subgoal_decomposition/ # System prompt, few-shot decomposition, structured output validation  
│ └── action_sequencing/ # System prompt, ReAct + LLM+P agent, step simulation stub, subgoal removal logic  
│    
├── virtualhome/ # Critical: contains dataset files & semantic dictionaries (synonyms, relations, states, etc.)  
│ ├── dataset/ # EAI-provided VirtualHome dataset (required for pipeline)  
│ └── ... # Other utility files for environment semantics  
│  
├── ff-planner-docker/ # Fast Downward planner setup (for PDDL generation and planning experiments)  
│ ├── pddl_tasks/ # Generated PDDL tasks by your agents  
│ └── Dockerfile # For building Fast Downward container  
│  
├── my_llm_outputs/ # 📁 Your generated outputs (e.g., goal interpretation results for EAI dataset)  
├── my_eai_results/ # 📊 Evaluation metrics computed by your pipeline  
├── output/virtualhome/ # EAI's author-provided baseline metrics to compare (from SOTA proprietary models)
├── logs/ # Logs from runs  
├── requirements.txt # Python dependencies  
├── .gitignore  
├── LICENSE  
└── README.md      

## 📦 Requirements  

### Core Dependencies  

Install the official **Embodied Agent Interface** for output validation:  
  
```bash  
git clone https://github.com/embodied-agent-interface/embodied-agent-interface.git  
cd embodied-agent-interface  
pip install -e .  ```

### Python Environment  
You’ll need Python 3.9+ and packages listed in requirements.txt.  

## 🚀 Installation & Usage  
For now, here’s what you likely did:  

1. Clone this repo:
```bash
git clone https://github.com/your-username/simple-embodied-agent-interface.git
cd simple-embodied-agent-interface ```
2. (optionally) Install EAI interface (see below).  
3. Set up virtual environment:
```bash
python3 -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate
pip install --upgrade pip
pip install -r requirements.txt
```
4. (optionally) Build the Fast Downward planner Docker image (required only for PDDL-based action_sequencing module):
```bash
cd ff-planner-docker
docker build -t downward-planner .
cd ..
```
5. Run src/task_generation/sandbox.ipynb to start experimenting. Outputs are stored in my_llm_outputs/ by default.
6. (optionally) Evaluate using EAI pipeline → results saved to my_eai_results/ by default.

## 📁 Data & Results  
Your Outputs  
All generated outputs (e.g., goal interpretations) are stored in:  
my_llm_outputs/virtualhome/goal_interpretation/

Metrics and evaluation results are saved in:  
my_eai_results/virtualhome/evaluate_results/

Baseline Metrics  
For comparison, author-provided baseline metrics (from SOTA proprietary models) are available in:  
output/virtualhome/

<img width="989" height="614" alt="image" src="https://github.com/user-attachments/assets/05bc4ca0-4125-42cd-bf33-8434f4f0db6b" />
<img width="1114" height="532" alt="image" src="https://github.com/user-attachments/assets/976684fd-a634-4950-b271-5eb727b2238c" />

## ⚙️ Notes on VirtualHome  
❗ The virtualhome/ folder is critical for your pipeline — it contains:   

Dataset files (taken from EAI authors)  
Semantic dictionaries:  
Object synonyms  
Action types  
Object states  
Relations between objects
etc.  
🛑 Note: The actual VirtualHome simulator code is not required for running those current modules — it would only be needed while implementing environment simulation steps or transition modeling module used as a tool for comparement with ground truth during goal generation.

## 🧩 Fast Downward Planner  
The ff-planner-docker/ directory contains:  

Generated .pddl task files (produced by the agents)  
A Dockerfile to build the Fast Downward planner container  
Useful for:  

Validating plan feasibility  
Comparing LLM-generated plans vs classical planners
  
## 📜 License    
This project is licensed under the MIT License — see the LICENSE file for details.   

## Special thanks  

Special thanks to the authors of the EAI pipeline (https://github.com/embodied-agent-interface/embodied-agent-interface)   
for making it open source.  
This project would not have been possible without the authors of the fast-downward planner (https://github.com/aibasel/downward),   
and thanks to them for their contributions to open source.  
I would also like to thank the authors of the VirtualHome simulator for creating this product (https://github.com/xavierpuigf/virtualhome).

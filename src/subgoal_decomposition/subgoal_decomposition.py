
from langchain_core.messages import AIMessage
from langchain_ollama import ChatOllama
from src.subgoal_decomposition.prompt_specification import specificate_prompt
from pathlib import Path
from dotenv import load_dotenv
import re, json

load_dotenv()
llm = ChatOllama( 
    model="qwen3:8b",
    temperature=0.0,
    reasoning=False,
)

def run_model(id_task : str, max_iterations : int = 10) -> tuple[dict, str, str]:
    """
    Запуск subgoal_decomposition модуля. Сделан на основе few-shot и информации, полученной 
    предыдущим ReAct модулем + валидации состояний и связей релевантных объектов. 
    Пробрасывает имена и состояния релевантных объектов дальше, в action_sequencing модуль.
    Ответ формируется в LTL формате, как список упорядоченных целей-состояний и целей-связей.
    В случае, когда таких целей сделать нельзя, делает цели-действия."""
    task, relevant_objs, seen_graph = specificate_prompt(id_task = id_task, num_trials = 10)
    parsed = None
    for i in range(max_iterations):
        last_message = llm.invoke(task)
        if isinstance(last_message, AIMessage):
            try:
                content = last_message.content.strip()
                content = re.sub(r"<think>.*?</think>", "", content, flags=re.DOTALL).strip()
                parsed = json.loads(content)
                if all(key in parsed for key in [
                    "necessity_to_use_action", "actions_to_include", "output"
                ]) or all(key in parsed for key in [
                    "necessity to use action", "actions to include", "output"
                ]):
                    print(f"Subgoal decomposition completed at iteration {i+1}")
                    break
            except Exception as e:
                print(f"Iteration {i+1}: JSON parse error: {e}")
                print(f"Content was: {repr(content[:200])}...")
        else:
            print(f"Iteration {i+1}: Last message not AIMessage")
    else:
        print("Max iterations reached. Returning last result.")

    return parsed, relevant_objs, seen_graph

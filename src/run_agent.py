from typing import Any, Dict, List, Optional

from provider.message import Message, StepFinishPart, StepStartPart, text_message, to_langchain_messages
from processor import process_stream
from provider.prompt import build_prompt
from provider.llm import create_llm

from model_tools import get_tool_definitions

def should_terminate(history: List[Message]) -> bool:
    """判断是否应该终止agent loop."""
    last_user = next((m for m in reversed(history) if m.role == "user"), None)
    last_assistant = next((m for m in reversed(history) if m.role == "assistant"), None)
    if not last_assistant or not last_assistant.finish or last_assistant.finish == "tool-calls":
        return False
    if any(getattr(p, "type", "") == "tool" and p.state.status not in ("completed", "error") for p in last_assistant.parts):
        return False
    return not (last_user and last_user.id > last_assistant.id)


def run_loop(
    user_message: str,
    history: List[Message],
    tools: List[Dict[str, Any]],
    llm,
    max_steps: int = 20,
    system_prompt: Optional[str] = None,
) -> List[Message]:
    """Run the agent loop and return full message history."""
    history.append(text_message("user", user_message))
    step = 0
    force_stop_added = False #到达max_step了，强制终止，然后summary；

    while True:
        #是否应当终止
        if should_terminate(history):
            #判断agent loop 是否应该结束
            break
        if step >= max_steps and not force_stop_added:
            history.append(text_message("user", "[MAX STEPS REACHED, please summarize as text only, no tools]"))
            force_stop_added = True

        step += 1
        print(f"\n[step {step}]")
        assistant = Message(role="assistant", parts=[StepStartPart()])
        history.append(assistant)

        lc_messages = to_langchain_messages(history[:-1])
        active_tools = [] if force_stop_added else tools
        result = process_stream(llm, system_prompt or "", lc_messages, active_tools, assistant, history)
        assistant.parts.append(StepFinishPart(reason=result))

        if result == "stop":
            break
    return history

if __name__ =="__main__":
    llm = create_llm()
    system_prompt = build_prompt()
    tools = get_tool_definitions()
    print("react agent from longchain")
    history =[]
    while True:
        user_input = input("user:**").strip()
        if user_input == "exit":
            break
        conversation=run_loop(
            user_message=user_input,
            history=history,
            tools=tools,
            llm=llm,
            max_steps=20,
            system_prompt=system_prompt
            )
        
    
    


    

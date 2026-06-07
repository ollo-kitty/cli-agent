from typing import Any, Callable, Dict, List, Optional

from provider.message import Message, StepFinishPart, StepStartPart, text_message, to_langchain_messages
from processor import process_stream

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
    on_text_delta: Optional[Callable[[str], None]] = None,
    on_tool_start: Optional[Callable[[str, Dict[str, Any]], None]] = None,
    on_tool_result: Optional[Callable[[str, str], None]] = None,
    on_step_start: Optional[Callable[[int], None]] = None,
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
        if on_step_start:
            on_step_start(step)
        assistant = Message(role="assistant", parts=[StepStartPart()])
        history.append(assistant)

        lc_messages = to_langchain_messages(history[:-1])
        active_tools = [] if force_stop_added else tools
        text_delta_handler = on_text_delta or (lambda delta: None)
        tool_start_handler = on_tool_start or (lambda name, args: None)
        tool_result_handler = on_tool_result or (lambda name, output: None)
        result = process_stream(
            llm,
            system_prompt or "",
            lc_messages,
            active_tools,
            assistant,
            history,
            on_text_delta=text_delta_handler,
            on_tool_start=tool_start_handler,
            on_tool_result=tool_result_handler,
        )
        assistant.parts.append(StepFinishPart(reason=result))

        if result == "stop":
            break
    return history

# OpenCode loop: LLM stream processing and tool execution.

import time
from typing import Any, Callable, Dict, List, Literal, Optional

from langchain_core.messages import BaseMessage, SystemMessage

from model_tools import handle_function_call
from provider.message import Message, TextPart, ToolPart, ToolState, new_id, now, text_message


def _stream_with_retry(llm, messages):
    #最多重试三次
    for attempt in range(3):
        try:
            yield from llm.stream(messages)
            return
        except Exception:
            if attempt == 2:
                raise
            time.sleep(2**attempt)


def _run_tool(tool_name: str, args: dict) -> str:
    """调用工具"""
    return str(handle_function_call(tool_name, args))


def process_stream(
    llm,
    system: str,
    messages: List[BaseMessage],
    tools: List[Dict[str, Any]],
    assistant_msg: Message,
    history: List[Message],
    on_text_delta: Optional[Callable[[str], None]] = None,
    on_tool_start: Optional[Callable[[str, Dict[str, Any]], None]] = None,
    on_tool_result: Optional[Callable[[str, str], None]] = None,
) -> Literal["continue", "stop"]:
    """llm的一次stream流式调用，执行完整的工具调用（多次调用），
    将结果附加到历史消息中"""
    
    llm_with_tools = llm.bind_tools(tools)
    full_chunk = None
    text_part = None

    #调用LLM的stream
    for chunk in _stream_with_retry(llm_with_tools, [SystemMessage(content=system), *messages]):
        full_chunk = chunk if full_chunk is None else full_chunk + chunk
        if chunk.content:
            delta = str(chunk.content)
            if text_part is None:
                text_part = TextPart()
                assistant_msg.parts.append(text_part)
            text_part.text += delta
            if on_text_delta:
                on_text_delta(delta)
            else:
                print(delta, end="", flush=True)

    if text_part:
        text_part.time_end = now()
        if not on_text_delta:
            print()

    #判断是否有工具调用
    tool_calls = getattr(full_chunk, "tool_calls", []) if full_chunk is not None else []

    #有工具调用便利工具调用
    for call in tool_calls:
        tool_name = call["name"]
        args = call.get("args") or {}
        call_id = call.get("id") or new_id()
        started = now()
        part = ToolPart(
            tool_call_id=call_id,
            tool_name=tool_name,
            state=ToolState("running", args, time_start=started),
        )
        assistant_msg.parts.append(part)
        if on_tool_start:
            on_tool_start(tool_name, args)
        else:
            print(f"🔧 calling tool: {tool_name}({args})")

        try:
            output = _run_tool(tool_name, args)
            part.state = ToolState("completed", args, output=output, time_start=started, time_end=now())
        except Exception as exc:
            output = str(exc)
            part.state = ToolState("error", args, error=output, time_start=started, time_end=now())

        if on_tool_result:
            on_tool_result(tool_name, output)
        else:
            print(f"✓ tool result: {output[:100]}...")
        history.append(Message(role="tool", parts=[part]))

    assistant_msg.finish = "tool-calls" if tool_calls else "stop"
    assistant_msg.time_completed = now()
    #如果有tool-calls就要继续执行，否则就应该结束回话
    return "continue" if tool_calls else "stop"

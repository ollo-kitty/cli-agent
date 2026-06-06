import itertools
import time
from dataclasses import dataclass, field
from typing import Any, Dict, List, Literal, Optional, Union

from langchain_core.messages import AIMessage, BaseMessage, HumanMessage, ToolMessage


#迭代计数器，每次都会生成一个id；
_counter = itertools.count(1)


def now() -> float:
    return time.time()


def new_id() -> str:
    return f"{int(time.time() * 1000)}_{next(_counter):06d}"

#Text类型
@dataclass
class TextPart:
    type: Literal["text"] = "text"
    id: str = field(default_factory=new_id)
    text: str = ""
    time_start: float = field(default_factory=now)
    time_end: Optional[float] = None

#思考Part
@dataclass
class ReasoningPart:
    type: Literal["reasoning"] = "reasoning"
    id: str = field(default_factory=new_id)
    text: str = ""
    time_start: float = field(default_factory=now)
    time_end: Optional[float] = None

#工具执行的状态：记录工具调用的生命周期的;
#如果工具是异步执行的，要使用状态管理；
@dataclass
class ToolState:
    status: Literal["pending", "running", "completed", "error"]
    input: Dict[str, Any]
    output: Optional[str] = None
    error: Optional[str] = None
    time_start: Optional[float] = None
    time_end: Optional[float] = None

#tool part
@dataclass
class ToolPart:
    type: Literal["tool"] = "tool"
    id: str = field(default_factory=new_id)
    tool_call_id: str = ""
    tool_name: str = ""
    state: ToolState = field(default_factory=lambda: ToolState("pending", {}))


#agent步骤开始
@dataclass
class StepStartPart:
    type: Literal["step_start"] = "step_start"
    id: str = field(default_factory=new_id)

#agent步骤结束
@dataclass
class StepFinishPart:
    type: Literal["step_finish"] = "step_finish"
    id: str = field(default_factory=new_id)
    reason: str = ""
    tokens: Optional[Dict[str, Any]] = None


Part = Union[TextPart, ReasoningPart, ToolPart, StepStartPart, StepFinishPart]


@dataclass
class Message:
    role: Literal["user", "assistant", "tool"]
    parts: List[Part] 
    id: str = field(default_factory=new_id)
    finish: Optional[str] = None
    time_created: float = field(default_factory=now)
    time_completed: Optional[float] = None
    error: Optional[str] = None
    tokens: Optional[Dict[str, Any]] = None


def text_message(role: Literal["user", "assistant"], text: str) -> Message:
    part = TextPart(text=text, time_end=now())
    return Message(role=role, parts=[part])


def to_langchain_messages(history: List[Message]) -> List[BaseMessage]:
    """将agent 的 LLM event 事件流转换为 longchain兼容的message"""
    result: List[BaseMessage] = []
    for msg in history:
        if msg.role == "user":
            text = "\n".join(p.text for p in msg.parts if isinstance(p, TextPart))
            result.append(HumanMessage(content=text))
        elif msg.role == "assistant":
            text = "\n".join(p.text for p in msg.parts if isinstance(p, TextPart))
            tool_calls = [
                {"id": p.tool_call_id, "name": p.tool_name, "args": p.state.input}
                for p in msg.parts
                if isinstance(p, ToolPart)
            ]
            result.append(AIMessage(content=text, tool_calls=tool_calls))
        elif msg.role == "tool":
            for p in msg.parts:
                if isinstance(p, ToolPart):
                    content = p.state.output if p.state.status == "completed" else p.state.error
                    result.append(ToolMessage(content=content or "", tool_call_id=p.tool_call_id))
    return result

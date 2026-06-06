"""
每个方法执行registry.register()告诉系统功能、参数、属于哪个工具组、是否可用；
引用链：:
    tools/registry.py  (no imports from model_tools or tool files)
           ^
    tools/*.py  (import from tools.registry at module level)
           ^
    model_tools.py  (imports tools.registry + all tool modules)
           ^
    run_agent.py, cli.py, batch_runner.py, etc.
"""

import json
import logging
from typing import Callable, Dict, List, Optional, Set, Union

logger = logging.getLogger(__name__)

class ToolEntry:
    """一个注册工具集合的元数据"""
    def __init__(self, name, toolset, schema, handler,
                  is_async, description, emoji):
        self.name = name
        self.toolset = toolset
        self.schema = schema
        self.handler = handler
        self.is_async = is_async
        self.description = description
        self.emoji = emoji


class ToolRegistry:
    
    def __init__(self):
        self._tools: Dict[str, ToolEntry] = {} #{工具名：工具实体对象}

    def register(
        self,
        name: str,
        toolset: str,
        schema: dict,
        handler: Callable, #可调用的对象，方法实体
        is_async: bool = False,
        description: str = "",
        emoji: str = "",
    ):
        """注册一个工具：每个文件被import的时候就会执行此操作."""
        #判断是否已经注册
        existing = self._tools.get(name)
        if existing and existing.toolset != toolset:
            # 注册方法发生冲突：同名但不属于同一个工具组；
            logger.warning(
                "Tool name collision: '%s' (toolset '%s') is being "
                "overwritten by toolset '%s'",
                name, existing.toolset, toolset,
            )
        self._tools[name] = ToolEntry(
            name=name,
            toolset=toolset,
            schema=schema,
            handler=handler,
            is_async=is_async,
            description=description or schema.get("description", ""),
            emoji=emoji,
        )

    def deregister(self, name: str) -> None:
        """删除一个工具，传入工具name"""
        entry = self._tools.pop(name, None)
        if entry is None:
            return
        logger.debug("Deregistered tool: %s", name)

    def get_definitions(self, tool_names: Set[str]) -> List[dict]:
        """
        返回可用的工具schema，保证符合OpenAI tools的规范
        传入工具名字的集合；
        """
        result = []
        for name in sorted(tool_names):
            entry = self._tools.get(name)
            if not entry:
                continue
            # Ensure schema always has a "name" field — use entry.name as fallback
            schema_with_name = {**entry.schema, "name": entry.name}
            result.append({"type": "function", "function": schema_with_name})
        return result

    
    def dispatch(self, name: str, args: dict, **kwargs) -> str:
        """传入工具的名称来执行工具：同步调用或者异步调用（_run_async协程）"""
        entry = self._tools.get(name)
        if not entry:
            return json.dumps({"error": f"Unknown tool: {name}"})
        try:
            if entry.is_async:
                pass
                # 如果是异步工具，这里先不实现；
                # from model_tools import _run_async
                # return _run_async(entry.handler(args, **kwargs))
            return entry.handler(args, **kwargs)
        except Exception as e:
            logger.exception("Tool %s dispatch error: %s", name, e)
            return json.dumps({"error": f"Tool execution failed: {type(e).__name__}: {e}"})


    def get_all_tool_names(self) -> List[str]:
        """返回所有已注册的工具名."""
        return sorted(self._tools.keys())

    def get_schema(self, name: str) -> Optional[dict]:
        """
        拿到所有工具的原始schema。
        """
        entry = self._tools.get(name)
        return entry.schema if entry else None

    def get_toolset_for_tool(self, name: str) -> Optional[str]:
        """根据工具名拿到所属工具组"""
        entry = self._tools.get(name)
        return entry.toolset if entry else None

    def get_emoji(self, name: str, default: str = "⚡") -> str:
        """获取工具显示用的 emoji，没有就用默认。"""
        entry = self._tools.get(name)
        return (entry.emoji if entry and entry.emoji else default)

    def get_tool_to_toolset_map(self) -> Dict[str, str]:
        """生成 {tool_name: toolset} 映射表。"""
        return {name: e.toolset for name, e in self._tools.items()}

# 在引用时会执行一次
registry = ToolRegistry()

# 注册中心提供的方法调用结果返回标准：Usage:
#   from tools.registry import registry, tool_error, tool_result
#
#   return tool_error("something went wrong")
#   return tool_error("not found", code=404)
#   return tool_result(success=True, data=payload)
#   return tool_result(items)         

def tool_error(message, **extra) -> str:
    result = {"error": str(message)}
    if extra:
        result.update(extra)
    return json.dumps(result, ensure_ascii=False)


def tool_result(data=None, **kwargs) -> str:
    if data is not None:
        return json.dumps(data, ensure_ascii=False)
    return json.dumps(kwargs, ensure_ascii=False)

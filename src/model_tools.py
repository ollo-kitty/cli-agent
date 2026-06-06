#!/usr/bin/env python3
"""
agent的工具编排：
    1.从本地 tools 包中导入真实的工具模块；
    2.向模型暴露已注册工具的 schema；
    3.将模型发起的工具调用分发给已注册的处理函数。
"""

import importlib
import json
import logging
import pkgutil
from typing import Any, Dict, List, Optional

from tools.registry import registry

logger = logging.getLogger(__name__)

_SKIP_TOOL_MODULES = {"__init__", "registry"}

def _discover_tools() -> None:
    """遍历tools包下的所有模块，跳过子包和_SKIP_TOOL_MODULES中的文件
    包下的工具都会执行注册；
    """
    import tools

    for module_info in pkgutil.iter_modules(tools.__path__):
        if module_info.ispkg or module_info.name in _SKIP_TOOL_MODULES:
            continue
        module_name = f"tools.{module_info.name}"
        try:
            importlib.import_module(module_name)
            #引入这个包时会自动run注册文件；
        except Exception as exc:
            logger.warning("Could not import tool module %s: %s", module_name, exc)

#模块被加载时就会执行
_discover_tools()

def _tools_for_toolset(toolset: str) -> List[str]:
    """按照工具组名筛选工具"""
    return [
        name
        for name, entry_toolset in registry.get_tool_to_toolset_map().items()
        if entry_toolset == toolset
    ]

def _resolve_requested_tools(toolsets: Optional[List[str]]) -> set[str]:
    """将工具组名或工具名列表解析为工具名集合:支持两种传入方式"""
    available_names = set(registry.get_all_tool_names())
    if toolsets is None:
        return available_names

    result: set[str] = set()
    for item in toolsets:
        names = [item] if item in available_names else _tools_for_toolset(item)
        result.update(names)
    return result


def get_tool_definitions(
    enabled_toolsets: List[str] = None,
    disabled_toolsets: List[str] = None,
) -> List[Dict[str, Any]]:
    """
    Return OpenAI-compatible tool definitions from the registry.
    enabled_toolsets：启用的工具集合
    disabled_toolsets：禁止的工具集合
    """
    #传入启用的工具集合的名字
    tools_to_include = _resolve_requested_tools(enabled_toolsets)
    if disabled_toolsets:
        #消除掉禁用的工具集合的名字
        tools_to_include.difference_update(_resolve_requested_tools(disabled_toolsets))
    #拿到工具集合的描述：open-ai格式
    filtered_tools = registry.get_definitions(tools_to_include)

    return filtered_tools


# 参数的矫正 ： 模型在调用工具时，会将参数的数字或布尔值传位str
def coerce_tool_args(tool_name: str, args: Dict[str, Any]) -> Dict[str, Any]:
    """Coerce string arguments to the primitive types declared in tool schemas."""
    if not args or not isinstance(args, dict):
        return args

    schema = registry.get_schema(tool_name)
    if not schema:
        return args

    properties = (schema.get("parameters") or {}).get("properties")
    if not properties:
        return args

    for key, value in args.items():
        if not isinstance(value, str):
            continue
        prop_schema = properties.get(key)
        if not prop_schema:
            continue
        expected = prop_schema.get("type")
        if not expected:
            continue
        coerced = _coerce_value(value, expected)
        if coerced is not value:
            args[key] = coerced

    return args


def _coerce_value(value: str, expected_type):
    if isinstance(expected_type, list):
        for type_name in expected_type:
            result = _coerce_value(value, type_name)
            if result is not value:
                return result
        return value

    if expected_type in ("integer", "number"):
        return _coerce_number(value, integer_only=(expected_type == "integer"))
    if expected_type == "boolean":
        return _coerce_boolean(value)
    return value


def _coerce_number(value: str, integer_only: bool = False):
    try:
        number = float(value)
    except (ValueError, OverflowError):
        return value
    if number != number or number == float("inf") or number == float("-inf"):
        return value
    if number == int(number):
        return int(number)
    if integer_only:
        return value
    return number


def _coerce_boolean(value: str):
    normalized = value.strip().lower()
    if normalized == "true":
        return True
    if normalized == "false":
        return False
    return value


def handle_function_call(
    function_name: str,
    function_args: Dict[str, Any],
    tool_call_id: Optional[str] = None,
    session_id: Optional[str] = None,
    user_task: Optional[str] = None,
    store: Any = None,
) -> str:
    """调用注册的方法"""
    del tool_call_id, session_id
    #矫正参数
    function_args = coerce_tool_args(function_name, function_args or {})
    dispatch_kwargs = {
        "user_task": user_task,
        "store": store,
    }
    try:
        return registry.dispatch(function_name, function_args, **dispatch_kwargs)
    except Exception as exc:
        logger.exception("Error executing %s: %s", function_name, exc)
        return json.dumps({"error": f"Error executing {function_name}: {exc}"}, ensure_ascii=False)
    
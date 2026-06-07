# cli-agent

一个基于 LangChain 的终端 Agent Demo，带有 Claude Code 风格的 Rich UI。

当前项目把职责拆成两层：

- `src/run_agent.py`：只保留 Agent 主循环，不负责终端输入输出。
- `src/main.py`：负责终端 UI、用户输入、流式输出渲染和命令处理。

## Requirements

- Python 3.12 推荐
- 使用 `uv` 管理依赖

安装依赖：

```bash
uv sync
```

如果当前环境的 uv 缓存目录没有写权限，可以临时指定缓存目录：

```bash
UV_CACHE_DIR=/private/tmp/uv-cache uv sync
```

## Environment

在项目根目录创建 `.env`：

```env
OPENAI_API_KEY=your-api-key
OPENAI_BASE_URL=https://your-model-endpoint/v1
OPENAI_MODEL=your-model-name
```

`src/provider/llm.py` 会读取这些变量创建 `ChatOpenAI`。

## Start UI

从项目根目录启动聊天 UI：

```bash
uv run python src/main.py
```

进入界面后，在 `You` 输入提示后直接输入消息。

## UI Commands

```text
/help   显示命令帮助
/clear  清空当前终端视图和本地对话历史
exit    退出聊天
quit    退出聊天
q       退出聊天
```

退出时会显示一个 Claude 风格的结束面板。

## Tools

工具定义在 `src/tools/` 中，通过 `registry.register()` 注册。

当前示例工具：

- `add`：计算两个整数之和
- `skills_list`：列出可用 skills
- `skill_view`：查看指定 skill 的完整内容

工具调用流程：

1. `src/model_tools.py` 自动发现并导入 `src/tools/` 下的工具模块。
2. `get_tool_definitions()` 返回 OpenAI tool schema。
3. LLM 通过 `bind_tools()` 获得工具定义。
4. 模型发起 tool call 后，`processor.py` 调用 `handle_function_call()`。
5. `handle_function_call()` 通过 registry 分发到真实工具函数。

## Skills

skills 存放在：

```text
src/skills/
```

每个 skill 推荐使用：

```text
src/skills/<skill-name>/SKILL.md
```

启动时，`build_prompt()` 会把 `skills_list()` 的结果转成 XML 注入 system prompt：

```xml
<avaliable_skills>
  <skill>
    <name>...</name>
    <description>...</description>
  </skill>
</avaliable_skills>
```

当任务匹配某个 skill 时，模型可以调用 `skill_view(name)` 加载完整指引。

## Project Structure

```text
src/main.py                 # Rich + Typer 终端 UI 入口
src/run_agent.py            # Agent 主循环
src/processor.py            # LLM 流式处理和工具执行
src/model_tools.py          # 工具发现、schema 暴露、工具分发
src/provider/llm.py         # LLM 创建
src/provider/message.py     # Message / Part 数据结构
src/provider/prompt.py      # system prompt 构建
src/tools/                  # 工具实现和注册
src/skills/                 # skill 指引文件
```

## Development

语法检查：

```bash
UV_CACHE_DIR=/private/tmp/uv-cache uv run python -m py_compile src/main.py src/run_agent.py src/processor.py
```

启动 UI 做手动验证：

```bash
UV_CACHE_DIR=/private/tmp/uv-cache uv run python src/main.py
```

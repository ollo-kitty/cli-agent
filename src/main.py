from __future__ import annotations

from pathlib import Path
import sys

import typer
from rich.align import Align
from rich.console import Console, Group
from rich.live import Live
from rich.markdown import Markdown
from rich.panel import Panel
from rich.prompt import Prompt
from rich.rule import Rule
from rich.table import Table
from rich.text import Text



from model_tools import get_tool_definitions
from provider.llm import create_llm
from provider.message import Message
from provider.prompt import build_prompt
from run_agent import run_loop


app = typer.Typer(
    name="claude-chat",
    help="极简终端 AI 对话工具",
    add_completion=False,
)
console = Console()


THEME = {
    "accent": "bright_cyan",
    "muted": "grey62",
    "border": "grey35",
    "assistant": "bright_green",
    "user": "bright_blue",
    "warn": "yellow",
}


def render_header() -> None:
    cwd = Path.cwd().name
    title = Text()
    title.append("Claude Code", style=f"bold {THEME['accent']}")
    title.append("  terminal agent", style=THEME["muted"])

    meta = Table.grid(expand=True)
    meta.add_column(justify="left")
    meta.add_column(justify="right")
    meta.add_row(title, Text(f"cwd: {cwd}", style=THEME["muted"]))

    help_text = Text()
    help_text.append("/help", style=THEME["accent"])
    help_text.append(" commands   ", style=THEME["muted"])
    help_text.append("/clear", style=THEME["accent"])
    help_text.append(" reset screen   ", style=THEME["muted"])
    help_text.append("exit", style=THEME["accent"])
    help_text.append(" quit", style=THEME["muted"])

    console.print(
        Panel(
            Group(meta, Rule(style=THEME["border"]), Align.left(help_text)),
            border_style=THEME["border"],
            padding=(1, 2),
        )
    )


def render_help() -> None:
    commands = Table.grid(padding=(0, 2))
    commands.add_column(style=THEME["accent"], no_wrap=True)
    commands.add_column(style=THEME["muted"])
    commands.add_row("/help", "显示可用命令")
    commands.add_row("/clear", "清空屏幕和本地对话记录")
    commands.add_row("exit / quit / q", "退出对话")

    console.print(
        Panel(
            commands,
            title="[bold]Commands[/bold]",
            title_align="left",
            border_style=THEME["border"],
            padding=(1, 2),
        )
    )


def render_empty_warning() -> None:
    console.print(Text("请输入有效内容。", style=THEME["warn"]))


def render_goodbye() -> None:
    message = Text()
    message.append("Session closed", style=f"bold {THEME['accent']}")
    message.append("\nContext cleared from this terminal view.", style=THEME["muted"])

    console.print()
    console.print(
        Panel(
            Align.left(message),
            title=f"[bold {THEME['assistant']}]✻ Claude[/bold {THEME['assistant']}]",
            title_align="left",
            border_style=THEME["border"],
            padding=(1, 2),
        )
    )


def ask_user() -> str:
    console.print()
    console.print(Text("╭─ You", style=f"bold {THEME['user']}"))
    value = Prompt.ask(Text("╰─", style=f"bold {THEME['user']}"))
    return value.strip()


def clear_screen(history: list[Message]) -> None:
    history.clear()
    console.clear()
    render_header()


def render_stream_panel(content: str, tool_lines: list[str]) -> Panel:
    body = []
    if tool_lines:
        body.append(Text("\n".join(tool_lines), style=THEME["muted"]))
        body.append(Rule(style=THEME["border"]))
    body.append(Markdown(content) if content else Text("Thinking...", style=THEME["muted"]))
    return Panel(
        Group(*body),
        title=f"[bold {THEME['assistant']}]✻ Claude[/bold {THEME['assistant']}]",
        title_align="left",
        border_style=THEME["border"],
        padding=(1, 2),
    )


def render_agent_turn(user_message: str, history: list[Message], llm, system_prompt: str, tools: list[dict]) -> None:
    content_parts: list[str] = []
    tool_lines: list[str] = []

    with Live(
        render_stream_panel("", tool_lines),
        console=console,
        refresh_per_second=12,
        transient=False,
    ) as live:
        def refresh() -> None:
            live.update(render_stream_panel("".join(content_parts), tool_lines))

        def on_step_start(step: int) -> None:
            if step > 1:
                tool_lines.append("↳ continuing with tool result")
                refresh()

        def on_text_delta(delta: str) -> None:
            content_parts.append(delta)
            refresh()

        def on_tool_start(name: str, args: dict) -> None:
            tool_lines.append(f"↳ calling {name}({args})")
            refresh()

        def on_tool_result(name: str, output: str) -> None:
            tool_lines.append(f"✓ {name}: {output[:160]}")
            refresh()

        run_loop(
            user_message=user_message,
            history=history,
            tools=tools,
            llm=llm,
            max_steps=20,
            system_prompt=system_prompt,
            on_text_delta=on_text_delta,
            on_tool_start=on_tool_start,
            on_tool_result=on_tool_result,
            on_step_start=on_step_start,
        )
        refresh()


@app.command()
def chat() -> None:
    """启动终端 AI 对话。"""
    history: list[Message] = []
    llm = create_llm()
    system_prompt = build_prompt()
    tools = get_tool_definitions()

    render_header()

    while True:
        user_msg = ask_user()
        command = user_msg.lower()

        if command in {"exit", "quit", "q"}:
            render_goodbye()
            break

        if command == "/help":
            render_help()
            continue

        if command == "/clear":
            clear_screen(history)
            continue

        if not user_msg:
            render_empty_warning()
            continue

        render_agent_turn(user_msg, history, llm, system_prompt, tools)


if __name__ == "__main__":
    app()

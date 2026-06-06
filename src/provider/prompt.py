import json
from html import escape

from tools.skill_tool import skills_list


DEFAULT_SYSTEM_PROMPT ="""你是一个智能助手，可以调用工具查看技能skill的指引，
回答前先判断是否具有匹配的skill，如果需要使用某个具体的skill，先调用`skill_view(name)`
加载完整指引，再按照指引执行，回答要简洁、准确。"""

DEFAULT_SKILL_PROMPT = """Skill provide specialized instructions and workflows
for specific tasks. \n Use the skill_view(name) to load a skill when a task matches its description.
"""

def _parse_skill(skill_result: str) -> str:
    payload = json.loads(skill_result)
    lines = ["<avaliable_skills>"]

    for skill in payload.get("skills", []):
        name = escape(str(skill.get("name", "")))
        description = escape(str(skill.get("description", "")))
        lines.extend(
            [
                "  <skill>",
                f"    <name>{name}</name>",
                f"    <description>{description}</description>",
                "  </skill>",
            ]
        )

    lines.append("</avaliable_skills>")
    return "\n".join(lines)

def build_prompt(
        base_prompt: str| None = None,
        )->str:
    model_prompt = (base_prompt or DEFAULT_SYSTEM_PROMPT).strip()
    skills= skills_list()
    skill_xml = _parse_skill(skills)
    skill_prompt = DEFAULT_SKILL_PROMPT + "\n" + skill_xml
    return model_prompt + "\n\n" + skill_prompt

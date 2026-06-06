import json
import logging


import yaml

from pathlib import Path
from typing import Dict, Any, List, Tuple

from tools.registry import registry, tool_error

logger = logging.getLogger(__name__)


#默认为全局配置

SKILLS_DIR = Path("./skills")

# skill name 和 descriptiono的长度限制
MAX_NAME_LENGTH = 64
MAX_DESCRIPTION_LENGTH = 1024

#设置递归查找skill时应当排除的目录
_EXCLUDED_SKILL_DIRS = frozenset((".git", ".github", ".hub"))

def _parse_frontmatter(content: str) -> Tuple[Dict[str, Any], str]:
    """Parse YAML frontmatter from markdown content."""
    if not content.startswith("---"):
        return {}, content

    parts = content.split("---", 2)
    if len(parts) < 3:
        return {}, content

    frontmatter = yaml.safe_load(parts[1]) or {}
    if not isinstance(frontmatter, dict):
        frontmatter = {}
    return frontmatter, parts[2].lstrip()



def _find_all_skills() -> List[Dict[str, Any]]:
    """找到skill目录下的所有skill.md
    Returns:
        List of skill metadata dicts (name, description, category).
    """
    skills = []
    seen_names: set = set()

    if SKILLS_DIR.exists():
        for skill_md in SKILLS_DIR.rglob("SKILL.md"):
            #递归查找所有的SKILL.md
            if any(part in _EXCLUDED_SKILL_DIRS for part in skill_md.parts):
                continue

            #当前skill所在的目录
            skill_dir = skill_md.parent

            try:
                content = skill_md.read_text(encoding="utf-8")[:4000]
                frontmatter, body = _parse_frontmatter(content)

                name = frontmatter.get("name", skill_dir.name)[:MAX_NAME_LENGTH]
                if name in seen_names:
                    continue

                description = frontmatter.get("description", "")
                if not description:
                    for line in body.strip().split("\n"):
                        line = line.strip()
                        if line and not line.startswith("#"):
                            description = line
                            break

                if len(description) > MAX_DESCRIPTION_LENGTH:
                    description = description[:MAX_DESCRIPTION_LENGTH - 3] + "..."

                seen_names.add(name)
                skills.append({
                    "name": name,
                    "description": description,
                })

            except (UnicodeDecodeError, PermissionError) as e:
                logger.debug("Failed to read skill file %s: %s", skill_md, e)
                continue
            except Exception as e:
                logger.debug(
                    "Skipping skill at %s: failed to parse: %s", skill_md, e, exc_info=True
                )
                continue

    return skills


def skills_list() -> str:
    """
    列举所有可用的skill，只返回name和description：渐进式披露
    Args:
        简单实现无任何过滤，不需要任何参数
    Returns:
        JSON string with minimal skill info: name, description
    """
    try:
        if not SKILLS_DIR.exists():
            SKILLS_DIR.mkdir(parents=True, exist_ok=True)
            return json.dumps(
                {
                    "success": True,
                    "skills": [],
                    "categories": [],
                    "message": "No skills found.",
                },
                ensure_ascii=False,
            )

        # 获取所有的skill
        all_skills = _find_all_skills()

        if not all_skills:
            return json.dumps(
                {
                    "success": True,
                    "skills": [],
                    "categories": [],
                    "message": "No skills found in skills/ directory.",
                },
                ensure_ascii=False,
            )
        
        return json.dumps(
            {
                "success": True,
                "skills": all_skills,
                "count": len(all_skills),
                "hint": "Use skill_view(name) to see full content",
            },
            ensure_ascii=False,
        )

    except Exception as e:
        return tool_error(str(e), success=False)


def skill_view(name: str, file_path: str = None) -> str:
    """
    查看skill的content;
    """
    try:
        if not SKILLS_DIR.exists():
            return json.dumps(
                {
                    "success": False,
                    "error": "Skills directory does not exist yet. It will be created on first install.",
                },
                ensure_ascii=False,
            )

        skill_dir = None
        skill_md = None

        direct_path = SKILLS_DIR / name
        if direct_path.is_dir() and (direct_path / "SKILL.md").exists():
            skill_dir = direct_path
            skill_md = direct_path / "SKILL.md"
        elif direct_path.with_suffix(".md").exists():
            skill_md = direct_path.with_suffix(".md")
            skill_dir = skill_md.parent

        if not skill_md:
            for found_skill_md in SKILLS_DIR.rglob("SKILL.md"):
                if found_skill_md.parent.name == name:
                    skill_dir = found_skill_md.parent
                    skill_md = found_skill_md
                    break

        if not skill_md:
            for found_md in SKILLS_DIR.rglob(f"{name}.md"):
                if found_md.name != "SKILL.md":
                    skill_md = found_md
                    skill_dir = found_md.parent
                    break

        if not skill_md or not skill_md.exists():
            available = [s["name"] for s in _find_all_skills()[:20]]
            return json.dumps(
                {
                    "success": False,
                    "error": f"Skill '{name}' not found.",
                    "available_skills": available,
                    "hint": "Use skills_list to see all available skills",
                },
                ensure_ascii=False,
            )

        if file_path:
            target_file = skill_dir / file_path
            if not target_file.exists():
                return json.dumps(
                    {
                        "success": False,
                        "error": f"File '{file_path}' not found in skill '{name}'.",
                    },
                    ensure_ascii=False,
                )
        else:
            target_file = skill_md

        content = target_file.read_text(encoding="utf-8")

        try:
            rel_path = str(target_file.relative_to(skill_dir))
        except ValueError:
            rel_path = str(target_file)

        return json.dumps(
            {
                "success": True,
                "name": name,
                "file": file_path or "SKILL.md",
                "path": rel_path,
                "content": content,
            },
            ensure_ascii=False,
        )

    except Exception as e:
        return tool_error(str(e), success=False)


# ---------------------------------------------------------------------------
# Registry
# ---------------------------------------------------------------------------

SKILLS_LIST_SCHEMA = {
    "name": "skills_list",
    "description": "List available skills (name + description). Use skill_view(name) to load full content.",
    "parameters": {
        "type": "object",
        "properties": {},
        "required": [],
    },
}

SKILL_VIEW_SCHEMA = {
    "name": "skill_view",
    "description": "Load a skill's SKILL.md content by name, or load a specific file inside the skill with file_path.",
    "parameters": {
        "type": "object",
        "properties": {
            "name": {
                "type": "string",
                "description": "The skill name (use skills_list to see available skills)",
            },
            "file_path": {
                "type": "string",
                "description": "OPTIONAL: Path to a file within the skill. Omit to get the main SKILL.md content.",
            },
        },
        "required": ["name"],
    },
}

registry.register(
    name="skills_list",
    toolset="skills",
    schema=SKILLS_LIST_SCHEMA,
    handler=lambda args, **kw: skills_list(),
    emoji="📚",
)
registry.register(
    name="skill_view",
    toolset="skills",
    schema=SKILL_VIEW_SCHEMA,
    handler=lambda args, **kw: skill_view(
        args.get("name"), file_path=args.get("file_path")
    ),
    emoji="📚",
)

"""Skill loader for the debate project — loads SKILL.md files with YAML frontmatter.

Two skill types live side-by-side:

* `llm_prompt` — SKILL.md whose body is a prompt template; exposes `.render(**kwargs) -> str`.
* `deterministic` — SKILL.md describing rules + a sibling `script.py` whose `run(...)`
  function is bound to the loaded skill and exposed via `.run(*args, **kwargs)`.

`SkillLoader.load(name)` returns a uniform `Skill` object regardless of type; calling
the wrong method (`.render` on a deterministic skill, `.run` on an LLM-prompt skill)
raises `SkillTypeMismatchError`.
"""

from __future__ import annotations

import importlib.util
from collections.abc import Callable
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import yaml


class SkillTypeMismatchError(TypeError):
    """Raised when render() / run() is called on a skill of the wrong type."""


@dataclass(frozen=True)
class Skill:
    """Base class — never instantiated directly; the loader returns a subclass."""

    name: str
    type: str
    description: str
    when_to_use: str
    body: str
    source_path: Path

    def render(self, **kwargs: Any) -> str:  # noqa: ARG002
        raise SkillTypeMismatchError(
            f"render() is only valid on llm_prompt skills; '{self.name}' is type '{self.type}'."
        )

    def run(self, *args: Any, **kwargs: Any) -> Any:  # noqa: ARG002
        raise SkillTypeMismatchError(
            f"run() is only valid on deterministic skills; '{self.name}' is type '{self.type}'."
        )


@dataclass(frozen=True)
class LLMSkill(Skill):
    """LLM-prompt skill — the body is a template with {{ var }} placeholders."""

    def render(self, **kwargs: Any) -> str:
        result = self.body
        for key, value in kwargs.items():
            result = result.replace(f"{{{{ {key} }}}}", str(value))
        return result


@dataclass(frozen=True)
class DeterministicSkill(Skill):
    """Deterministic skill — bound to the `run` callable from the sibling script.py."""

    _run: Callable[..., Any] = field(default=None, repr=False)  # type: ignore[assignment]

    def run(self, *args: Any, **kwargs: Any) -> Any:
        return self._run(*args, **kwargs)


class SkillLoader:
    """Discovers and loads SKILL.md files under a project-local skills root."""

    def __init__(self, skills_root: Path) -> None:
        self._root = Path(skills_root)
        if not self._root.is_dir():
            raise FileNotFoundError(f"Skills root does not exist: {self._root}")
        self._cache: dict[str, Skill] = {}

    def load(self, skill_name: str) -> Skill:
        if skill_name in self._cache:
            return self._cache[skill_name]
        skill_dir = self._find_dir(skill_name)
        skill = self._build(skill_dir, skill_name)
        self._cache[skill_name] = skill
        return skill

    def _find_dir(self, name: str) -> Path:
        for skill_md in self._root.rglob("SKILL.md"):
            if skill_md.parent.name == name:
                return skill_md.parent
        raise FileNotFoundError(f"Skill not found: {name}")

    def _build(self, skill_dir: Path, skill_name: str) -> Skill:
        frontmatter, body = self._parse(skill_dir / "SKILL.md")
        declared_name = frontmatter.get("name", skill_name)
        skill_type = frontmatter.get("type")
        description = frontmatter.get("description", "")
        when_to_use = frontmatter.get("when_to_use", "")

        common = {
            "name": declared_name,
            "type": skill_type,
            "description": description,
            "when_to_use": when_to_use,
            "body": body,
            "source_path": skill_dir / "SKILL.md",
        }

        if skill_type == "llm_prompt":
            return LLMSkill(**common)
        if skill_type == "deterministic":
            script_path = skill_dir / "script.py"
            if not script_path.is_file():
                raise FileNotFoundError(
                    f"Deterministic skill '{declared_name}' is missing its script.py at {script_path}"
                )
            run_fn = self._load_run_fn(script_path, declared_name)
            return DeterministicSkill(**common, _run=run_fn)
        raise ValueError(
            f"Unknown skill type {skill_type!r} in {skill_dir / 'SKILL.md'}; "
            "expected 'llm_prompt' or 'deterministic'."
        )

    @staticmethod
    def _parse(path: Path) -> tuple[dict, str]:
        content = path.read_text(encoding="utf-8")
        if not content.startswith("---"):
            raise ValueError(f"Missing YAML frontmatter: {path}")
        end = content.find("\n---", 3)
        if end == -1:
            raise ValueError(f"Malformed frontmatter (no closing ---): {path}")
        frontmatter = yaml.safe_load(content[3:end].strip()) or {}
        body = content[end + 4:].strip()
        return frontmatter, body

    @staticmethod
    def _load_run_fn(script_path: Path, skill_name: str) -> Callable[..., Any]:
        module_name = f"debate_skill_{skill_name}"
        spec = importlib.util.spec_from_file_location(module_name, script_path)
        if spec is None or spec.loader is None:
            raise ImportError(f"Could not build import spec for {script_path}")
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        run_fn = getattr(module, "run", None)
        if run_fn is None or not callable(run_fn):
            raise AttributeError(
                f"Deterministic skill '{skill_name}' script.py must define a callable run(...)."
            )
        return run_fn

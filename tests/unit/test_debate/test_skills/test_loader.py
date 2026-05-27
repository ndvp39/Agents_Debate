"""Tests for the SKILL.md loader."""

from pathlib import Path

import pytest

from debate.skills.loader import (
    DeterministicSkill,
    LLMSkill,
    SkillLoader,
    SkillTypeMismatchError,
)

SKILLS_ROOT = Path(__file__).resolve().parents[4] / "src" / "debate" / "skills"


@pytest.fixture
def loader() -> SkillLoader:
    return SkillLoader(SKILLS_ROOT)


# ---------------------------------------------------------------------------
# 1. successful load of an LLM-prompt skill
# ---------------------------------------------------------------------------

def test_loads_llm_prompt_skill(loader: SkillLoader) -> None:
    skill = loader.load("craft_opening")
    assert isinstance(skill, LLMSkill)
    assert skill.name == "craft_opening"
    assert skill.type == "llm_prompt"
    assert "Topic: {{ topic }}" in skill.body


# ---------------------------------------------------------------------------
# 2. successful load of a deterministic skill
# ---------------------------------------------------------------------------

def test_loads_deterministic_skill(loader: SkillLoader) -> None:
    skill = loader.load("synthesize_evidence")
    assert isinstance(skill, DeterministicSkill)
    assert skill.name == "synthesize_evidence"
    assert skill.type == "deterministic"
    assert "Rules" in skill.body


# ---------------------------------------------------------------------------
# 3. render() substitutes placeholders + leaves unmatched as-is
# ---------------------------------------------------------------------------

def test_render_substitutes_placeholders_and_preserves_unmatched(loader: SkillLoader) -> None:
    skill = loader.load("craft_opening")
    rendered = skill.render(topic="AI safety", stance="PRO")
    assert "Topic: AI safety" in rendered
    assert "Stance: PRO" in rendered

    # Re-render with only a bogus kwarg: real placeholders survive untouched.
    rendered2 = skill.render(bogus="x")
    assert "{{ topic }}" in rendered2
    assert "{{ stance }}" in rendered2


# ---------------------------------------------------------------------------
# 4. render() on a deterministic skill raises
# ---------------------------------------------------------------------------

def test_render_on_deterministic_skill_raises(loader: SkillLoader) -> None:
    skill = loader.load("synthesize_evidence")
    with pytest.raises(SkillTypeMismatchError, match="render"):
        skill.render(anything="x")


# ---------------------------------------------------------------------------
# 5. run() on a deterministic skill invokes script.py and returns its value
# ---------------------------------------------------------------------------

def test_run_on_deterministic_skill_invokes_script(loader: SkillLoader) -> None:
    skill = loader.load("synthesize_evidence")
    result = skill.run("draft text", ["src A", "src B"])
    assert result["citations"] == ["src A", "src B"]
    assert result["enriched_argument"] == "draft text\n\nSources: src A; src B"

    empty = skill.run("just the draft", [])
    assert empty == {"citations": [], "enriched_argument": "just the draft"}


# ---------------------------------------------------------------------------
# 6. run() on an LLM-prompt skill raises
# ---------------------------------------------------------------------------

def test_run_on_llm_skill_raises(loader: SkillLoader) -> None:
    skill = loader.load("craft_opening")
    with pytest.raises(SkillTypeMismatchError, match="run"):
        skill.run("anything")


# ---------------------------------------------------------------------------
# 7. Missing skill name raises FileNotFoundError
# ---------------------------------------------------------------------------

def test_missing_skill_raises(loader: SkillLoader) -> None:
    with pytest.raises(FileNotFoundError, match="does_not_exist"):
        loader.load("does_not_exist")


# ---------------------------------------------------------------------------
# 8. Deterministic skill missing its script.py raises a clear error
# ---------------------------------------------------------------------------

def test_deterministic_missing_script_raises(tmp_path: Path) -> None:
    skill_dir = tmp_path / "broken_det"
    skill_dir.mkdir()
    (skill_dir / "SKILL.md").write_text(
        "---\n"
        "name: broken_det\n"
        "type: deterministic\n"
        "description: missing script\n"
        "---\n\n"
        "# Broken\n## Rules\nnone.\n",
        encoding="utf-8",
    )
    loader = SkillLoader(tmp_path)
    with pytest.raises(FileNotFoundError, match="script.py"):
        loader.load("broken_det")


# ---------------------------------------------------------------------------
# 9. Malformed frontmatter (no closing ---) raises ValueError
# ---------------------------------------------------------------------------

def test_malformed_frontmatter_raises(tmp_path: Path) -> None:
    skill_dir = tmp_path / "broken_fm"
    skill_dir.mkdir()
    (skill_dir / "SKILL.md").write_text(
        "---\n"
        "name: broken_fm\n"
        "type: llm_prompt\n"
        "description: no closing fence\n"
        "\n"
        "# Body without closing fence\n",
        encoding="utf-8",
    )
    loader = SkillLoader(tmp_path)
    with pytest.raises(ValueError, match="closing"):
        loader.load("broken_fm")


def test_missing_frontmatter_raises(tmp_path: Path) -> None:
    skill_dir = tmp_path / "no_fm"
    skill_dir.mkdir()
    (skill_dir / "SKILL.md").write_text("# Just a heading\nnothing else.\n", encoding="utf-8")
    loader = SkillLoader(tmp_path)
    with pytest.raises(ValueError, match="frontmatter"):
        loader.load("no_fm")


# ---------------------------------------------------------------------------
# 10. Caching: same name returns the same instance
# ---------------------------------------------------------------------------

def test_caching_returns_same_instance(loader: SkillLoader) -> None:
    first = loader.load("craft_opening")
    second = loader.load("craft_opening")
    assert first is second


# ---------------------------------------------------------------------------
# Extra sanity: missing skills_root raises at construction
# ---------------------------------------------------------------------------

def test_missing_root_raises(tmp_path: Path) -> None:
    with pytest.raises(FileNotFoundError, match="does not exist"):
        SkillLoader(tmp_path / "nope")

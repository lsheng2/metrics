from __future__ import annotations

from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
SOURCE_SKILLS = ROOT / ".agents" / "skills"
CLAUDE_SKILLS = ROOT / ".claude" / "skills"


def _files(root: Path) -> dict[str, bytes]:
    return {
        path.relative_to(root).as_posix(): path.read_bytes()
        for path in root.rglob("*")
        if path.is_file() and "__pycache__" not in path.parts
    }


def test_claude_skill_copies_are_byte_identical_to_agents_source():
    copies = sorted(path for path in CLAUDE_SKILLS.iterdir() if path.is_dir())
    assert copies
    for copy in copies:
        source = _files(SOURCE_SKILLS / copy.name)
        mirrored = _files(copy)
        assert sorted(mirrored) == sorted(source), copy.name
        assert [name for name in source if mirrored[name] != source[name]] == [], copy.name

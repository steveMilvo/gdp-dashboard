"""Versioned prompt files.

Agent prompts live in `prompts/<name>.v<N>.md` with a small YAML-ish header.
They are files rather than inline strings so a prompt change shows up in
`git diff` and can be reverted like any other code change. `AgentInvocation`
records the exact name and version used, so a regression is traceable to a
specific prompt revision.
"""

from __future__ import annotations

import functools
import re
from dataclasses import dataclass
from pathlib import Path
from string import Template

from ..config import settings

_FILENAME = re.compile(r"^(?P<name>[a-z0-9_]+)\.v(?P<version>\d+)\.md$")
_FRONTMATTER = re.compile(r"\A---\n(?P<meta>.*?)\n---\n(?P<body>.*)\Z", re.S)


class PromptNotFound(FileNotFoundError):
    pass


@dataclass(frozen=True)
class Prompt:
    name: str
    version: str
    meta: dict[str, str]
    system: str
    template: str
    path: Path

    def render(self, **values: object) -> str:
        """Substitution is `$name` / `${name}`. A missing key is an error, not
        an empty string — a silently-blank prompt section is the kind of bug
        that produces confidently wrong output."""
        return Template(self.template).substitute(
            {k: _stringify(v) for k, v in values.items()}
        )


def _stringify(value: object) -> str:
    if isinstance(value, str):
        return value
    if isinstance(value, (list, tuple)):
        return "\n".join(f"- {item}" for item in value)
    return str(value)


def _parse(path: Path) -> Prompt:
    match = _FILENAME.match(path.name)
    if not match:
        raise PromptNotFound(f"{path.name} is not a versioned prompt file")
    raw = path.read_text(encoding="utf-8")
    meta: dict[str, str] = {}
    body = raw
    fm = _FRONTMATTER.match(raw)
    if fm:
        body = fm.group("body")
        for line in fm.group("meta").splitlines():
            if ":" in line:
                key, _, value = line.partition(":")
                meta[key.strip()] = value.strip()

    system, _, template = body.partition("\n## USER\n")
    system = system.replace("## SYSTEM\n", "", 1).strip()
    if not template.strip():
        # A prompt with no explicit split is all-user, no system.
        system, template = "", body
    return Prompt(
        name=match.group("name"),
        version=match.group("version"),
        meta=meta,
        system=system.strip(),
        template=template.strip(),
        path=path,
    )


@functools.lru_cache(maxsize=128)
def load(name: str, version: str | None = None) -> Prompt:
    directory = settings().prompts_dir
    candidates = sorted(
        (p for p in directory.glob(f"{name}.v*.md") if _FILENAME.match(p.name)),
        key=lambda p: int(_FILENAME.match(p.name).group("version")),  # type: ignore[union-attr]
    )
    if not candidates:
        raise PromptNotFound(f"no prompt named {name!r} in {directory}")
    if version is None:
        return _parse(candidates[-1])
    for path in candidates:
        if _FILENAME.match(path.name).group("version") == str(version):  # type: ignore[union-attr]
            return _parse(path)
    raise PromptNotFound(f"prompt {name!r} has no version {version!r}")


def clear_cache() -> None:
    load.cache_clear()

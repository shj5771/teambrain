"""Team wiki: an LLM curates raw team-knowledge entries into topic pages.

The shared store (store.jsonl) is an append-only log of public-channel turns.
This module periodically reads the entries it has not processed yet, asks an
LLM to fold them into a small set of Markdown topic pages (decisions, project
facts, how-tos), and writes those pages to ``<store dir>/wiki/<slug>.md``.

- Input is only what is already in the shared store, so the visibility rule
  (public channels only) carries over automatically: DMs/private channels can
  never reach the wiki because they never reach the store.
- When a decision changes, the page keeps the current decision on top and the
  old one under a "변경 이력" (change history) section.
- The LLM call is injected (``llm`` argument). Inside Hermes the default uses
  Hermes' own configured model via ``agent.auxiliary_client.call_llm``, so no
  extra API key is needed. Tests pass a fake.
- Standard library only.
"""

from __future__ import annotations

import hashlib
import json
import logging
import os
import re
import threading
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Callable, Dict, List, Optional

try:  # POSIX file lock so several gateway processes never curate at once.
    import fcntl
except ImportError:  # pragma: no cover - Windows
    fcntl = None  # type: ignore[assignment]

from .store import TeamKnowledgeStore, tokenize

logger = logging.getLogger(__name__)

LLMFn = Callable[[List[Dict[str, str]]], str]

_SLUG_RE = re.compile(r"^[a-z0-9][a-z0-9-]{0,59}$")
_BATCH_SIZE = 20
_MAX_CONTEXT_PAGES_CHARS = 12000
_MAX_PAGE_CHARS = 8000

_SYSTEM_PROMPT = """\
You maintain a team wiki. You receive (1) the current wiki pages and (2) new \
conversation entries that teammates had with their AI assistants in public \
team channels. Fold the new entries into the wiki.

Rules:
- Only record durable team knowledge: decisions, agreed plans, project facts, \
how-tos, owners, deadlines. Ignore greetings, chit-chat and one-off questions \
with no lasting value. If nothing is worth recording, return {"pages": []}.
- Prefer updating an existing page over creating a near-duplicate.
- A teammate merely ASKING about something already recorded is not a new fact: \
do not add them as a source and do not change the page for it.
- Never invent facts. Every fact must come from the entries or existing pages.
- Attribute each fact: who said it, in which channel, on which date \
(e.g. "— 지민, #dev, 2026-11-03"; omit the channel if the entry has none).
- When a new entry changes an earlier decision, put the CURRENT decision at the \
top of the page and move the old one under a "## 변경 이력" (change history) \
section with its date. Never silently drop the old decision.
- Write titles AND page content in the language the team uses in the entries \
(Korean entries → Korean title and content).
- Page content is Markdown WITHOUT a top-level "# title" line (the title is a \
separate field). Keep each page under 6000 characters.
- slug: lowercase ASCII letters, digits and hyphens only, max 60 chars \
(e.g. "database-choice"). Reuse the existing slug when updating a page.

Respond with ONLY a JSON object, no prose, no code fences:
{"pages": [{"slug": "...", "title": "...", "content": "..."}]}
Include only pages you create or change, each with its FULL new content.
"""


@dataclass
class WikiPage:
    slug: str
    title: str
    content: str
    updated: str = ""

    def to_markdown(self) -> str:
        return (
            "---\n"
            f"title: {self.title}\n"
            f"updated: {self.updated}\n"
            "---\n\n"
            f"# {self.title}\n\n"
            f"{self.content.strip()}\n"
        )

    @classmethod
    def from_markdown(cls, slug: str, text: str) -> "WikiPage":
        title, updated, body = slug, "", text
        if text.startswith("---\n"):
            end = text.find("\n---", 4)
            if end != -1:
                for line in text[4:end].splitlines():
                    key, _, value = line.partition(":")
                    if key.strip() == "title":
                        title = value.strip() or slug
                    elif key.strip() == "updated":
                        updated = value.strip()
                body = text[end + 4:].lstrip("\n")
        heading = f"# {title}"
        if body.startswith(heading):
            body = body[len(heading):].lstrip("\n")
        return cls(slug=slug, title=title, content=body.rstrip("\n"), updated=updated)


def safe_slug(raw: str, title: str = "") -> str:
    """Return a filesystem-safe slug. Never lets an LLM-chosen slug escape the
    wiki directory (no '/', '..', absolute paths, etc.)."""
    slug = (raw or "").strip().lower()
    slug = re.sub(r"[^a-z0-9-]+", "-", slug).strip("-")[:60].strip("-")
    if _SLUG_RE.match(slug):
        return slug
    digest = hashlib.sha1((title or raw or "page").encode("utf-8")).hexdigest()[:10]
    return f"page-{digest}"


def parse_llm_pages(text: str) -> List[Dict[str, str]]:
    """Extract the {"pages": [...]} payload from an LLM reply. Tolerates code
    fences and surrounding prose; returns [] if nothing usable is found."""
    if not text:
        return []
    cleaned = re.sub(r"```(?:json)?", "", text)
    start, end = cleaned.find("{"), cleaned.rfind("}")
    if start == -1 or end <= start:
        return []
    try:
        data = json.loads(cleaned[start:end + 1])
    except json.JSONDecodeError:
        return []
    pages = data.get("pages") if isinstance(data, dict) else None
    if not isinstance(pages, list):
        return []
    result = []
    for p in pages:
        if not isinstance(p, dict):
            continue
        title = str(p.get("title", "")).strip()
        content = str(p.get("content", "")).strip()
        if not title or not content:
            continue
        result.append({"slug": str(p.get("slug", "")), "title": title, "content": content})
    return result


class TeamWiki:
    """Markdown topic pages curated from the shared store."""

    def __init__(self, store: TeamKnowledgeStore, wiki_dir: Optional[Path] = None) -> None:
        self.store = store
        self.dir = wiki_dir or (store.path.parent / "wiki")
        self._state_path = self.dir / "_state.json"
        self._lock_path = self.dir / ".lock"
        self._thread_lock = threading.Lock()

    # -- pages ---------------------------------------------------------------

    def list_pages(self) -> List[WikiPage]:
        if not self.dir.exists():
            return []
        pages = []
        for path in sorted(self.dir.glob("*.md")):
            try:
                pages.append(WikiPage.from_markdown(path.stem, path.read_text(encoding="utf-8")))
            except OSError:
                continue
        return pages

    def get_page(self, slug: str) -> Optional[WikiPage]:
        slug = safe_slug(slug)
        path = self.dir / f"{slug}.md"
        if not path.exists():
            return None
        return WikiPage.from_markdown(slug, path.read_text(encoding="utf-8"))

    def write_page(self, page: WikiPage) -> None:
        self.dir.mkdir(parents=True, exist_ok=True)
        path = self.dir / f"{safe_slug(page.slug, page.title)}.md"
        tmp = path.with_suffix(".md.tmp")
        tmp.write_text(page.to_markdown(), encoding="utf-8")
        os.replace(tmp, path)

    def search(self, query: str, limit: int = 3, max_chars: int = 1500) -> str:
        """Keyword-overlap search over pages (title matches count double)."""
        q = tokenize(query)
        if not q:
            return ""
        scored = []
        for page in self.list_pages():
            score = 2 * len(q & tokenize(page.title)) + len(q & tokenize(page.content))
            if score:
                scored.append((score, page))
        scored.sort(key=lambda t: t[0], reverse=True)
        if not scored:
            return ""
        lines = ["[TeamBrain wiki] Curated team knowledge (most relevant pages). "
                 "When you answer from it, say WHO decided it (e.g. \"지민님이 #dev에서 정했어요\")."]
        for _, page in scored[:limit]:
            body = page.content
            if len(body) > max_chars:
                body = body[:max_chars].rstrip() + "\n…(truncated — use team_wiki_read for the full page)"
            lines.append(f"\n## {page.title}  (slug: {page.slug}, updated {page.updated})\n{body}")
        return "\n".join(lines)

    # -- curation state ------------------------------------------------------

    def processed_count(self) -> int:
        try:
            return int(json.loads(self._state_path.read_text(encoding="utf-8")).get("processed", 0))
        except (OSError, ValueError, AttributeError):
            return 0

    def _save_processed(self, n: int) -> None:
        self.dir.mkdir(parents=True, exist_ok=True)
        tmp = self._state_path.with_suffix(".tmp")
        tmp.write_text(json.dumps({"processed": n}), encoding="utf-8")
        os.replace(tmp, self._state_path)

    def pending_count(self) -> int:
        return max(0, len(self.store.read_all()) - self.processed_count())

    # -- curation ------------------------------------------------------------

    def curate(self, llm: Optional[LLMFn] = None, batch_size: int = _BATCH_SIZE) -> List[str]:
        """Fold unprocessed store entries into wiki pages.

        Returns the slugs of pages written. Safe to call concurrently from
        threads or processes: if another curation is running it returns [].
        An LLM failure leaves the checkpoint untouched so entries are retried.
        """
        llm = llm or hermes_llm
        if not self._thread_lock.acquire(blocking=False):
            return []
        try:
            self.dir.mkdir(parents=True, exist_ok=True)
            with open(self._lock_path, "w") as lock_file:
                if fcntl is not None:
                    try:
                        fcntl.flock(lock_file, fcntl.LOCK_EX | fcntl.LOCK_NB)
                    except OSError:
                        return []
                return self._curate_locked(llm, batch_size)
        finally:
            self._thread_lock.release()

    def _curate_locked(self, llm: LLMFn, batch_size: int) -> List[str]:
        entries = self.store.read_all()
        done = self.processed_count()
        written: List[str] = []
        while done < len(entries):
            batch = entries[done:done + batch_size]
            reply = llm(self._build_messages(batch))
            for raw in parse_llm_pages(reply):
                slug = safe_slug(raw["slug"], raw["title"])
                page = WikiPage(
                    slug=slug,
                    title=raw["title"][:120],
                    content=raw["content"][:_MAX_PAGE_CHARS],
                    updated=datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC"),
                )
                self.write_page(page)
                if slug not in written:
                    written.append(slug)
            done += len(batch)
            self._save_processed(done)
        if written:
            logger.info("TeamBrain wiki updated: %s", ", ".join(written))
        return written

    def _build_messages(self, batch: List[Dict]) -> List[Dict[str, str]]:
        batch_tokens = set()
        for e in batch:
            batch_tokens |= tokenize(f"{e.get('user', '')} {e.get('assistant', '')}")

        pages = self.list_pages()
        # Most relevant pages in full (within a budget), the rest by title only,
        # so the LLM can update instead of duplicating.
        pages.sort(key=lambda p: len(batch_tokens & tokenize(p.title + " " + p.content)), reverse=True)
        full, titles_only, budget = [], [], _MAX_CONTEXT_PAGES_CHARS
        for p in pages:
            block = f"### slug: {p.slug}\ntitle: {p.title}\n{p.content}"
            if len(block) <= budget:
                full.append(block)
                budget -= len(block)
            else:
                titles_only.append(f"- {p.slug}: {p.title}")

        lines = []
        for e in batch:
            owner = (e.get("owner") or {}).get("user_name") or e.get("profile", "unknown")
            where = f"#{e['chat_name']}, " if e.get("chat_name") else ""
            when = str(e.get("timestamp", ""))[:10]
            lines.append(
                f"- {owner}, {where}{when}\n  user: {e.get('user', '')}\n  assistant: {e.get('assistant', '')}"
            )

        user_msg = (
            "## Current wiki pages\n"
            + ("\n\n".join(full) if full else "(none yet)")
            + ("\n\nOther pages (title only):\n" + "\n".join(titles_only) if titles_only else "")
            + "\n\n## New entries\n"
            + "\n".join(lines)
        )
        return [
            {"role": "system", "content": _SYSTEM_PROMPT},
            {"role": "user", "content": user_msg},
        ]


def hermes_llm(messages: List[Dict[str, str]]) -> str:
    """Default LLM: Hermes' own configured model (no extra key needed).

    Override per task in Hermes config.yaml if you want a cheaper model:
        auxiliary:
          teambrain_wiki:
            model: <model id>
    """
    from agent.auxiliary_client import call_llm  # only importable inside Hermes

    response = call_llm(task="teambrain_wiki", messages=messages, temperature=0.2, max_tokens=4000)
    return response.choices[0].message.content or ""

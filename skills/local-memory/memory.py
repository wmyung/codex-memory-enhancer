#!/usr/bin/env python3
"""
local-memory v2.0: Persistent memory for Codex CLI using local SQLite.
No server needed. Python stdlib only.
Now with: project-scoped DBs, importance/expiry, tags, context injection,
optional semantic search, auto-save, and export/import.

Usage:
  python3 memory.py save <content>  [-k KEY] [-c CAT] [-t TAGS] [-i 1-5] [--ttl 7d] [-p PROJECT]
  python3 memory.py search <query>  [-n LIMIT] [--semantic] [-t TAG] [-p PROJECT]
  python3 memory.py list            [-n LIMIT] [-c CAT] [-p PROJECT]
  python3 memory.py read <id]
  python3 memory.py forget <id]
  python3 memory.py recent          [-n LIMIT] [-p PROJECT]
  python3 memory.py stats           [-p PROJECT]
  python3 memory.py condense        [-n LIMIT] [-p PROJECT]
  python3 memory.py export          [-f json|markdown] [-p PROJECT]
  python3 memory.py import          [-f FILE] [-p PROJECT]
  python3 memory.py cleanup         [--dry-run] [-p PROJECT]
  python3 memory.py session-end     [-p PROJECT]
"""
import sqlite3, json, sys, os, re, time, textwrap, shutil
from pathlib import Path
from datetime import datetime, timedelta

BASE_DIR = Path.home() / ".codex" / "skills" / "local-memory"
DEFAULT_DB = BASE_DIR / "memory.sqlite3"

# ── Dangerous patterns ──
DANGEROUS_PATTERNS = [
    re.compile(r'(?:api[_-]?key|apikey|secret|token|password|passwd|pwd|credential|private_key)'
               r"['\"]?\s*[:=]\s*['\"]?\S{12,}", re.I),
    re.compile(r'sk-[A-Za-z0-9]{20,}'),
    re.compile(r'ghp_[A-Za-z0-9]{36,}'),
    re.compile(r'xox[baprs]-[A-Za-z0-9\-]{10,}'),
    re.compile(r'-----BEGIN (?:RSA |EC |OPENSSH )?PRIVATE KEY-----'),
    re.compile(r'AKIA[0-9A-Z]{16}'),
    re.compile(r'[A-Za-z0-9+/]{40,}={0,2}'),
]

_TTL_UNITS = {"h": 3600, "d": 86400, "w": 604800, "m": 2592000}


def parse_ttl(ttl_str: str) -> float | None:
    """Parse '7d' → seconds, '30m' → seconds, etc."""
    m = re.match(r'^(\d+)\s*(h|d|w|m)?$', ttl_str.strip().lower())
    if not m:
        return None
    val = int(m.group(1))
    unit = m.group(2) or "d"
    return val * _TTL_UNITS[unit]


def get_db_path(project: str = "") -> Path:
    """Get DB path: project-specific or default."""
    if project:
        proj_dir = BASE_DIR / "projects"
        proj_dir.mkdir(parents=True, exist_ok=True)
        return proj_dir / f"{project}.sqlite3"
    return DEFAULT_DB


def get_db(project: str = "") -> sqlite3.Connection:
    db_path = get_db_path(project)
    db_path.parent.mkdir(parents=True, exist_ok=True)
    db = sqlite3.connect(str(db_path))
    db.row_factory = sqlite3.Row
    db.execute("PRAGMA journal_mode=WAL")
    db.execute("PRAGMA synchronous=NORMAL")
    _init_schema(db)
    # Migration: add columns if missing (v1→v2)
    try:
        cols = [r[1] for r in db.execute("PRAGMA table_info(memories)").fetchall()]
        if "importance" not in cols:
            db.execute("ALTER TABLE memories ADD COLUMN importance INTEGER DEFAULT 3")
        if "ttl" not in cols:
            db.execute("ALTER TABLE memories ADD COLUMN ttl REAL DEFAULT NULL")
    except sqlite3.OperationalError:
        pass
    return db


def _init_schema(db):
    db.executescript("""
        CREATE TABLE IF NOT EXISTS memories (
            id          INTEGER PRIMARY KEY AUTOINCREMENT,
            key         TEXT UNIQUE,
            content     TEXT NOT NULL,
            category    TEXT DEFAULT 'general',
            tags        TEXT DEFAULT '',
            importance  INTEGER DEFAULT 1,
            ttl         REAL DEFAULT NULL,
            created_at  REAL NOT NULL,
            updated_at  REAL NOT NULL,
            access_count INTEGER DEFAULT 0
        );
        CREATE INDEX IF NOT EXISTS idx_memories_cat ON memories(category);
        CREATE INDEX IF NOT EXISTS idx_memories_updated ON memories(updated_at DESC);
        CREATE INDEX IF NOT EXISTS idx_memories_importance ON memories(importance DESC);
    """)
    # FTS5 (best-effort)
    try:
        db.executescript("""
            CREATE VIRTUAL TABLE IF NOT EXISTS memories_fts USING fts5(
                content, key, tags,
                content=memories, content_rowid=id
            );
            CREATE TRIGGER IF NOT EXISTS memories_ai AFTER INSERT ON memories BEGIN
                INSERT INTO memories_fts(rowid, content, key, tags)
                VALUES (new.id, new.content, new.key, new.tags);
            END;
            CREATE TRIGGER IF NOT EXISTS memories_ad AFTER DELETE ON memories BEGIN
                INSERT INTO memories_fts(memories_fts, rowid, content, key, tags)
                VALUES ('delete', old.id, old.content, old.key, old.tags);
            END;
            CREATE TRIGGER IF NOT EXISTS memories_au AFTER UPDATE ON memories BEGIN
                INSERT INTO memories_fts(memories_fts, rowid, content, key, tags)
                VALUES ('delete', old.id, old.content, old.key, old.tags);
                INSERT INTO memories_fts(rowid, content, key, tags)
                VALUES (new.id, new.content, new.key, new.tags);
            END;
        """)
    except sqlite3.OperationalError:
        pass


def _is_dangerous(text: str) -> str | None:
    for pat in DANGEROUS_PATTERNS:
        m = pat.search(text)
        if m:
            snippet = m.group()[:40]
            return f"Refused: content matches dangerous pattern '{snippet}...'"
    return None


def _now():
    return time.time()


def _ts(t: float) -> str:
    return datetime.fromtimestamp(t).strftime("%Y-%m-%d %H:%M")


def _tag_query(tags_str: str) -> tuple:
    """Parse tag filter like 'project:B003,type:result' into SQL."""
    if not tags_str:
        return "", []
    parts = [t.strip() for t in tags_str.split(",") if t.strip()]
    clauses = []
    for p in parts:
        clauses.append("tags LIKE ?")
    return " AND " + " AND ".join(clauses), [f"%{p}%" for p in parts]


def _purge_expired(db):
    """Remove expired memories."""
    now = _now()
    count = db.execute("DELETE FROM memories WHERE ttl IS NOT NULL AND ttl < ?", (now,)).rowcount
    if count:
        db.commit()
    return count


# ── Semantic search (optional) ──
_EMBEDDER = None

def _get_embedder():
    global _EMBEDDER
    if _EMBEDDER is not None:
        return _EMBEDDER
    try:
        from sentence_transformers import SentenceTransformer
        _EMBEDDER = SentenceTransformer("all-MiniLM-L6-v2")
        return _EMBEDDER
    except ImportError:
        return None


def _semantic_search(query: str, limit: int, project: str = "") -> list | None:
    """Semantic search using sentence-transformers (optional)."""
    embedder = _get_embedder()
    if not embedder:
        return None  # not available, fallback to FTS
    db = get_db(project)
    rows = db.execute(
        "SELECT id, key, content, category, tags, created_at, updated_at FROM memories"
    ).fetchall()
    db.close()
    if not rows:
        return []
    q_vec = embedder.encode(query)
    scored = []
    for r in rows:
        c_vec = embedder.encode(r["content"])
        sim = float(q_vec @ c_vec) / (sum(q_vec**2)**0.5 * sum(c_vec**2)**0.5 + 1e-10)
        scored.append((sim, r))
    scored.sort(key=lambda x: -x[0])
    return scored[:limit]


# ── Commands ──

def cmd_save(args):
    content = args.save
    key = args.key or None
    category = args.category or "general"
    tags = args.tags or ""
    importance = min(max(args.importance or 1, 1), 5)
    ttl_secs = parse_ttl(args.ttl) if args.ttl else None
    ttl_expire = _now() + ttl_secs if ttl_secs else None

    danger = _is_dangerous(content)
    if danger:
        print(danger); sys.exit(1)
    if key:
        danger = _is_dangerous(key)
        if danger:
            print(danger); sys.exit(1)

    db = get_db(args.project)
    now = _now()
    try:
        if key:
            existing = db.execute("SELECT id FROM memories WHERE key=?", (key,)).fetchone()
            if existing:
                db.execute("""
                    UPDATE memories SET content=?, category=?, tags=?, importance=?, ttl=?, updated_at=?
                    WHERE key=?
                """, (content, category, tags, importance, ttl_expire, now, key))
                action = "updated"
            else:
                db.execute("""
                    INSERT INTO memories(key, content, category, tags, importance, ttl, created_at, updated_at)
                    VALUES (?,?,?,?,?,?,?,?)
                """, (key, content, category, tags, importance, ttl_expire, now, now))
                action = "saved"
        else:
            cur = db.execute("""
                INSERT INTO memories(content, category, tags, importance, ttl, created_at, updated_at)
                VALUES (?,?,?,?,?,?,?)
            """, (content, category, tags, importance, ttl_expire, now, now))
            row_id = cur.lastrowid
            action = f"saved (id={row_id})"
        db.commit()
        imp_stars = "⭐" * importance
        print(f"✓ Memory {action}  {imp_stars}")
        if ttl_expire:
            days = ttl_secs / 86400 if ttl_secs else 0
            print(f"  expires: {_ts(ttl_expire)} ({days:.0f}d)")
        if args.project:
            print(f"  project: {args.project}")
    except sqlite3.IntegrityError as e:
        print(f"✗ Error: {e}")
        sys.exit(1)
    finally:
        db.close()


def cmd_search(args):
    query = args.search
    limit = min(args.limit or 10, 100)
    tag_filter = args.tag or ""

    # Try semantic first if requested
    if args.semantic:
        results = _semantic_search(query, limit, args.project)
        if results is None:
            print("(semantic search not available: pip install sentence-transformers)")
            print("Falling back to FTS5 search...\n")
        else:
            for sim, r in results:
                key_tag = r["key"] if r["key"] else f"(id={r['id']})"
                snippet = r["content"][:120].replace("\n", " ")
                print(f"  {r['id']:>4} {key_tag:25s} [{r['category']:12s}] sim={sim:.3f}")
                print(f"       {snippet}\n")
            print(f"--- {len(results)} semantic result(s) ---")
            return

    db = get_db(args.project)
    _purge_expired(db)
    tag_sql, tag_params = _tag_query(tag_filter)
    results = []

    # Try FTS5 first
    try:
        rows = db.execute(f"""
            SELECT m.id, m.key, m.content, m.category, m.tags,
                   m.created_at, m.updated_at, m.access_count, m.importance,
                   rank
            FROM memories_fts f
            JOIN memories m ON m.id = f.rowid
            WHERE memories_fts MATCH ?{tag_sql}
            ORDER BY rank
            LIMIT ?
        """, [query] + tag_params + [limit]).fetchall()
        results = rows
    except (sqlite3.OperationalError, sqlite3.DatabaseError):
        pass

    if not results:
        like_q = f"%{query}%"
        results = db.execute(f"""
            SELECT id, key, content, category, tags, created_at, updated_at, access_count, importance,
                   0 as rank
            FROM memories
            WHERE (content LIKE ? OR key LIKE ? OR tags LIKE ?){tag_sql}
            ORDER BY importance DESC, updated_at DESC
            LIMIT ?
        """, [like_q, like_q, like_q] + tag_params + [limit]).fetchall()

    if not results:
        print(f"(no results for '{query}')")
        return

    ids = [r["id"] for r in results]
    db.execute(f"UPDATE memories SET access_count = access_count + 1 WHERE id IN ({','.join('?'*len(ids))})", ids)
    db.commit()

    for r in results:
        cat_tag = f"[{r['category']}]" if r['category'] != 'general' else ""
        key_tag = r["key"] if r["key"] else f"(id={r['id']})"
        snippet = r["content"][:120].replace("\n", " ")
        stars = "⭐" * r["importance"]
        rank_str = f" score={-r['rank']:.2f}" if r['rank'] != 0 else ""
        print(f"  {r['id']:>4} {key_tag:25s} {cat_tag:12s} {_ts(r['updated_at']):16s}{rank_str} {stars}")
        print(f"       {snippet}\n")

    print(f"--- {len(results)} result(s) ---")
    db.close()


def cmd_list(args):
    limit = min(args.limit or 20, 200)
    cat_filter = args.category
    db = get_db(args.project)
    _purge_expired(db)

    if cat_filter:
        rows = db.execute("""
            SELECT id, key, content, category, tags, importance, created_at, updated_at, access_count
            FROM memories WHERE category=?
            ORDER BY importance DESC, updated_at DESC LIMIT ?
        """, (cat_filter, limit)).fetchall()
    else:
        rows = db.execute("""
            SELECT id, key, content, category, tags, importance, created_at, updated_at, access_count
            FROM memories ORDER BY importance DESC, updated_at DESC LIMIT ?
        """, (limit,)).fetchall()

    if not rows:
        print("(empty)")
        return

    for r in rows:
        key_tag = r["key"] if r["key"] else f"#{r['id']}"
        snippet = r["content"][:80].replace("\n", " ")
        stars = "⭐" * r["importance"]
        print(f"  {r['id']:>4} [{r['category']:10s}] {key_tag:25s} {_ts(r['updated_at'])} hits={r['access_count']} {stars}")
        print(f"       {snippet}\n")
    print(f"--- {len(rows)} memory(-ies) ---")
    db.close()


def cmd_read(args):
    db = get_db(args.project)
    r = db.execute("""
        SELECT id, key, content, category, tags, importance, created_at, updated_at, access_count
        FROM memories WHERE id=?
    """, (args.read,)).fetchone()
    if not r:
        print(f"(no memory with id={args.read})"); sys.exit(1)
    db.execute("UPDATE memories SET access_count = access_count + 1 WHERE id=?", (r["id"],))
    db.commit()
    stars = "⭐" * r["importance"]
    print(f"ID:        {r['id']}\nKey:       {r['key'] or '-'}\nCategory:  {r['category']}")
    print(f"Importance:{stars}  Tags: {r['tags'] or '-'}")
    print(f"Created:   {_ts(r['created_at'])}  Updated: {_ts(r['updated_at'])}")
    print(f"Accessed:  {r['access_count']} times")
    print("─" * 40)
    print(r["content"])
    db.close()


def cmd_forget(args):
    db = get_db(args.project)
    r = db.execute("SELECT id FROM memories WHERE id=?", (args.forget,)).fetchone()
    if not r:
        print(f"(no memory with id={args.forget})"); sys.exit(1)
    db.execute("DELETE FROM memories WHERE id=?", (args.forget,))
    db.commit()
    print(f"✓ Memory {args.forget} deleted")
    db.close()


def cmd_recent(args):
    limit = min(args.limit or 10, 100)
    db = get_db(args.project)
    _purge_expired(db)
    rows = db.execute("""
        SELECT id, key, content, category, tags, importance, updated_at
        FROM memories ORDER BY updated_at DESC LIMIT ?
    """, (limit,)).fetchall()
    if not rows:
        print("(no recent memories)"); return
    for r in rows:
        key_tag = r["key"] if r["key"] else f"#{r['id']}"
        snippet = r["content"][:100].replace("\n", " ")
        stars = "⭐" * r["importance"]
        print(f"  [{r['category']:10s}] {key_tag:25s} {_ts(r['updated_at'])} {stars}")
        print(f"       {snippet}\n")
    print(f"--- {len(rows)} recent ---")
    db.close()


def cmd_stats(args):
    db = get_db(args.project)
    _purge_expired(db)
    total = db.execute("SELECT COUNT(*) FROM memories").fetchone()[0]
    cats = db.execute("SELECT category, COUNT(*) as cnt FROM memories GROUP BY category ORDER BY cnt DESC").fetchall()
    fts = db.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='memories_fts'").fetchone()
    min_max = db.execute("SELECT MIN(updated_at), MAX(updated_at) FROM memories").fetchone()

    print(f"Project:     {args.project or '(default)'}")
    print(f"DB:          {get_db_path(args.project)}")
    print(f"Total:       {total} memories")
    print(f"FTS5:        {'✓ enabled' if fts else '✗ not available'}")
    print(f"Range:       {_ts(min_max[0]) if min_max and min_max[0] else '-'} ~ {_ts(min_max[1]) if min_max and min_max[1] else '-'}")
    print()
    if cats:
        print("By category:")
        for c in cats:
            print(f"  {c['category']:15s} {c['cnt']}")
    by_imp = db.execute("SELECT importance, COUNT(*) FROM memories GROUP BY importance ORDER BY importance DESC").fetchall()
    if by_imp:
        print("\nBy importance:")
        for imp, cnt in by_imp:
            print(f"  {'⭐'*imp:5s} {cnt}")

    db_path = get_db_path(args.project)
    db_size = db_path.stat().st_size if db_path.exists() else 0
    print(f"\nDB size: {db_size/1024:.1f} KB")
    db.close()


def cmd_condense(args):
    """Generate a condensed context summary for Codex injection."""
    limit = min(args.limit or 5, 20)
    db = get_db(args.project)
    _purge_expired(db)

    rows = db.execute("""
        SELECT id, key, content, category, tags, importance, updated_at
        FROM memories
        ORDER BY importance DESC, updated_at DESC
        LIMIT ?
    """, (limit * 2,)).fetchall()
    db.close()

    if not rows:
        print("(no memories to condense)"); return

    important = [r for r in rows if r["importance"] >= 4]
    recent = rows[:limit]

    seen = set()
    merged = []
    for r in important + recent:
        if r["id"] not in seen:
            seen.add(r["id"])
            merged.append(r)

    print(f"Recent Context ({len(merged)} items):\n")
    for r in merged:
        stars = "⭐" * r["importance"]
        snippet = r["content"].replace("\n", " ")[:150]
        tags = f" [{r['tags']}]" if r["tags"] else ""
        print(f"• [{r['category']}] {stars}{tags}")
        print(f"  {snippet}\n")


def cmd_export(args):
    fmt = args.format or "json"
    db = get_db(args.project)
    rows = db.execute("""
        SELECT id, key, content, category, tags, importance, created_at, updated_at, access_count
        FROM memories ORDER BY updated_at DESC
    """).fetchall()
    db.close()

    if fmt == "json":
        data = [dict(r) for r in rows]
        print(json.dumps(data, indent=2, ensure_ascii=False, default=str))
    else:
        proj_tag = f" (project: {args.project})" if args.project else ""
        print(f"# Memory Export{proj_tag}\n")
        for r in rows:
            title = r["key"] or f"Memory #{r['id']}"
            stars = "⭐" * r["importance"]
            print(f"## {title}  [{r['category']}] {stars}")
            print(f"  - ID: {r['id']}  Tags: {r['tags'] or '-'}")
            print(f"  - Created: {_ts(r['created_at'])}  Updated: {_ts(r['updated_at'])}")
            print()
            print(r["content"])
            print("\n---\n")


def cmd_import(args):
    if not args.file:
        print("Use: memory.py import -f export.json [-p PROJECT]"); sys.exit(1)
    fpath = Path(args.file)
    if not fpath.exists():
        print(f"File not found: {fpath}"); sys.exit(1)

    content = fpath.read_text()
    db = get_db(args.project)
    now = _now()
    count = 0

    try:
        data = json.loads(content)
        if isinstance(data, list):
            for item in data:
                key = item.get("key")
                c = item.get("content", "")
                cat = item.get("category", "general")
                tags = item.get("tags", "")
                imp = item.get("importance", 1)
                if _is_dangerous(c) or (key and _is_dangerous(key)):
                    continue
                if key:
                    db.execute("""
                        INSERT OR REPLACE INTO memories(key, content, category, tags, importance, created_at, updated_at)
                        VALUES (?,?,?,?,?,?,?)
                    """, (key, c, cat, tags, imp, now, now))
                else:
                    db.execute("""
                        INSERT INTO memories(content, category, tags, importance, created_at, updated_at)
                        VALUES (?,?,?,?,?,?)
                    """, (c, cat, tags, imp, now, now))
                count += 1
            db.commit()
    except json.JSONDecodeError:
        print("Only JSON format supported for import currently."); sys.exit(1)
    finally:
        db.close()
    print(f"✓ Imported {count} memories")


def cmd_cleanup(args):
    db = get_db(args.project)
    expired = db.execute("SELECT COUNT(*) FROM memories WHERE ttl IS NOT NULL AND ttl < ?", (_now(),)).fetchone()[0]
    if args.dry_run:
        print(f"  Would delete {expired} expired memories (--dry-run)")
    else:
        purged = _purge_expired(db)
        print(f"✓ Purged {purged} expired memories")
    db.close()


def cmd_session_end(args):
    db = get_db(args.project)
    purged = _purge_expired(db)
    total = db.execute("SELECT COUNT(*) FROM memories").fetchone()[0]
    print(f"✓ Session end: {purged} expired purged, {total} total memories")
    db.close()


def main():
    import argparse
    p = argparse.ArgumentParser(description="local-memory v2.0: persistent memory for Codex")

    sub = p.add_subparsers(dest="command")

    sp = sub.add_parser("save", help="Save a memory")
    sp.add_argument("save", nargs="?", metavar="CONTENT")
    sp.add_argument("-k", "--key", help="Unique key")
    sp.add_argument("-c", "--category", default="general", help="Category")
    sp.add_argument("-t", "--tags", help="Comma-separated tags")
    sp.add_argument("-i", "--importance", type=int, default=3, choices=range(1, 6))
    sp.add_argument("--ttl", help="TTL e.g. '7d', '30d', '12h'")
    sp.add_argument("-p", "--project", default="", help="Project name (isolated DB)")

    sp = sub.add_parser("search", help="Search memories")
    sp.add_argument("search", metavar="QUERY")
    sp.add_argument("-n", "--limit", type=int, default=10)
    sp.add_argument("--semantic", action="store_true")
    sp.add_argument("-t", "--tag", help="Filter by tag (e.g. 'project:B003')")
    sp.add_argument("-p", "--project", default="", help="Project name")

    sp = sub.add_parser("list", help="List memories")
    sp.add_argument("-n", "--limit", type=int, default=20)
    sp.add_argument("-c", "--category", help="Filter by category")
    sp.add_argument("-p", "--project", default="", help="Project name")

    sp = sub.add_parser("read", help="Read by ID")
    sp.add_argument("read", type=int, metavar="ID")
    sp.add_argument("-p", "--project", default="", help="Project name")

    sp = sub.add_parser("forget", help="Delete by ID")
    sp.add_argument("forget", type=int, metavar="ID")
    sp.add_argument("-p", "--project", default="", help="Project name")

    sp = sub.add_parser("recent", help="Recent memories")
    sp.add_argument("-n", "--limit", type=int, default=10)
    sp.add_argument("-p", "--project", default="", help="Project name")

    sp = sub.add_parser("stats", help="DB statistics")
    sp.add_argument("-p", "--project", default="", help="Project name")

    sp = sub.add_parser("condense", help="Condensed context for injection")
    sp.add_argument("-n", "--limit", type=int, default=5)
    sp.add_argument("-p", "--project", default="", help="Project name")

    sp = sub.add_parser("export", help="Export all memories")
    sp.add_argument("-f", "--format", choices=["json", "markdown"], default="json")
    sp.add_argument("-p", "--project", default="", help="Project name")

    sp = sub.add_parser("import", help="Import memories from JSON")
    sp.add_argument("-f", "--file", help="JSON file to import")
    sp.add_argument("-p", "--project", default="", help="Project name")

    sp = sub.add_parser("cleanup", help="Purge expired memories")
    sp.add_argument("--dry-run", action="store_true")
    sp.add_argument("-p", "--project", default="", help="Project name")

    sp = sub.add_parser("session-end", help="Session end cleanup")
    sp.add_argument("-p", "--project", default="", help="Project name")

    args = p.parse_args()

    if not args.command:
        p.print_help(); sys.exit(1)

    cmd_map = {
        "save": cmd_save, "search": cmd_search, "list": cmd_list,
        "read": cmd_read, "forget": cmd_forget, "recent": cmd_recent,
        "stats": cmd_stats, "condense": cmd_condense, "export": cmd_export,
        "import": cmd_import, "cleanup": cmd_cleanup, "session-end": cmd_session_end,
    }
    cmd_map[args.command](args)


if __name__ == "__main__":
    main()

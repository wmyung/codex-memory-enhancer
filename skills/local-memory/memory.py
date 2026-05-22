#!/usr/bin/env python3
"""
local-memory: Persistent memory for Codex CLI using local SQLite.
No server needed. Python stdlib only.

Usage:
  python3 memory.py save <content>  [-k KEY] [-c CAT] [-t TAGS]
  python3 memory.py search <query>  [-n LIMIT]
  python3 memory.py list            [-n LIMIT] [-c CAT]
  python3 memory.py read <id>
  python3 memory.py forget <id>
  python3 memory.py recent          [-n LIMIT]
  python3 memory.py stats
  python3 memory.py export          [-f json|markdown]
"""

import sqlite3, json, sys, os, re, time, textwrap
from pathlib import Path
from datetime import datetime

DB_DIR = Path.home() / ".codex" / "skills" / "local-memory"
DB_PATH = DB_DIR / "memory.sqlite3"

# ── Dangerous patterns: refuse to store ──
DANGEROUS_PATTERNS = [
    re.compile(r'(?:api[_-]?key|apikey|secret|token|password|passwd|pwd|credential|private_key)'
               r'[\'"]?\s*[:=]\s*[\'"]?\S{12,}', re.I),
    re.compile(r'sk-[A-Za-z0-9]{20,}'),
    re.compile(r'ghp_[A-Za-z0-9]{36,}'),
    re.compile(r'xox[baprs]-[A-Za-z0-9\-]{10,}'),
    re.compile(r'-----BEGIN (?:RSA |EC |OPENSSH )?PRIVATE KEY-----'),
    re.compile(r'AKIA[0-9A-Z]{16}'),
    re.compile(r'[A-Za-z0-9+/]{40,}={0,2}'),  # likely base64 secret
]


def get_db() -> sqlite3.Connection:
    DB_DIR.mkdir(parents=True, exist_ok=True)
    db = sqlite3.connect(str(DB_PATH))
    db.row_factory = sqlite3.Row
    db.execute("PRAGMA journal_mode=WAL")
    db.execute("PRAGMA synchronous=NORMAL")
    _init_schema(db)
    return db


def _init_schema(db):
    db.executescript("""
        CREATE TABLE IF NOT EXISTS memories (
            id          INTEGER PRIMARY KEY AUTOINCREMENT,
            key         TEXT UNIQUE,
            content     TEXT NOT NULL,
            category    TEXT DEFAULT 'general',
            tags        TEXT DEFAULT '',
            created_at  REAL NOT NULL,
            updated_at  REAL NOT NULL,
            access_count INTEGER DEFAULT 0
        );
        CREATE INDEX IF NOT EXISTS idx_memories_cat ON memories(category);
        CREATE INDEX IF NOT EXISTS idx_memories_updated ON memories(updated_at DESC);
    """)
    # FTS5 (best-effort — may fail on older SQLite)
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
        pass  # FTS5 not available — fallback to LIKE search


def _is_dangerous(text: str) -> str | None:
    for pat in DANGEROUS_PATTERNS:
        m = pat.search(text)
        if m:
            # Show partial match for debugging
            snippet = m.group()[:40]
            return f"Refused: content matches dangerous pattern '{snippet}...'"
    return None


def _now():
    return time.time()


def _ts(t: float) -> str:
    return datetime.fromtimestamp(t).strftime("%Y-%m-%d %H:%M")


def _tags_list(tags_str: str) -> list[str]:
    return [t.strip() for t in tags_str.split(",") if t.strip()]


# ── Commands ──

def cmd_save(args):
    content = args.save
    key = args.key or None
    category = args.category or "general"
    tags = args.tags or ""

    # Dangerous content check
    danger = _is_dangerous(content)
    if danger:
        print(danger)
        sys.exit(1)
    if key:
        danger = _is_dangerous(key)
        if danger:
            print(danger)
            sys.exit(1)

    db = get_db()
    now = _now()
    try:
        if key:
            existing = db.execute("SELECT id FROM memories WHERE key=?", (key,)).fetchone()
            if existing:
                db.execute("""
                    UPDATE memories SET content=?, category=?, tags=?, updated_at=?
                    WHERE key=?
                """, (content, category, tags, now, key))
                action = "updated"
            else:
                db.execute("""
                    INSERT INTO memories(key, content, category, tags, created_at, updated_at)
                    VALUES (?,?,?,?,?,?)
                """, (key, content, category, tags, now, now))
                action = "saved"
        else:
            cur = db.execute("""
                INSERT INTO memories(content, category, tags, created_at, updated_at)
                VALUES (?,?,?,?,?)
            """, (content, category, tags, now, now))
            row_id = cur.lastrowid
            action = f"saved (id={row_id})"
        db.commit()
        print(f"✓ Memory {action}")
    except sqlite3.IntegrityError as e:
        print(f"✗ Error: {e}")
        sys.exit(1)
    finally:
        db.close()


def cmd_search(args):
    query = args.search
    limit = min(args.limit or 10, 100)
    db = get_db()
    results = []

    # Try FTS5 first
    try:
        rows = db.execute("""
            SELECT m.id, m.key, m.content, m.category, m.tags,
                   m.created_at, m.updated_at, m.access_count,
                   rank
            FROM memories_fts f
            JOIN memories m ON m.id = f.rowid
            WHERE memories_fts MATCH ?
            ORDER BY rank
            LIMIT ?
        """, (query, limit)).fetchall()
        results = rows
    except (sqlite3.OperationalError, sqlite3.DatabaseError):
        pass

    if not results:
        # Fallback: LIKE search
        like_q = f"%{query}%"
        results = db.execute("""
            SELECT id, key, content, category, tags, created_at, updated_at, access_count,
                   0 as rank
            FROM memories
            WHERE content LIKE ? OR key LIKE ? OR tags LIKE ?
            ORDER BY updated_at DESC
            LIMIT ?
        """, (like_q, like_q, like_q, limit)).fetchall()

    if not results:
        print(f"(no results for '{query}')")
        return

    # Update access count
    ids = [r["id"] for r in results]
    db.execute(f"UPDATE memories SET access_count = access_count + 1 WHERE id IN ({','.join('?'*len(ids))})", ids)
    db.commit()

    for r in results:
        cat_tag = f"[{r['category']}]" if r['category'] != 'general' else ""
        key_tag = f"({r['key']})" if r['key'] else f"(id={r['id']})"
        snippet = r["content"][:120].replace("\n", " ")
        rank_str = f" score={-r['rank']:.2f}" if r['rank'] != 0 else ""
        print(f"  {r['id']:>4} {key_tag:30s} {cat_tag:12s} {_ts(r['updated_at']):16s}{rank_str}")
        print(f"       {snippet}")
        print()

    print(f"--- {len(results)} result(s) ---")
    db.close()


def cmd_list(args):
    limit = min(args.limit or 20, 200)
    cat_filter = args.category
    db = get_db()

    if cat_filter:
        rows = db.execute("""
            SELECT id, key, content, category, tags, created_at, updated_at, access_count
            FROM memories WHERE category=?
            ORDER BY updated_at DESC LIMIT ?
        """, (cat_filter, limit)).fetchall()
    else:
        rows = db.execute("""
            SELECT id, key, content, category, tags, created_at, updated_at, access_count
            FROM memories ORDER BY updated_at DESC LIMIT ?
        """, (limit,)).fetchall()

    if not rows:
        print("(empty)")
        return

    for r in rows:
        key_tag = r["key"] if r["key"] else f"#{r['id']}"
        snippet = r["content"][:80].replace("\n", " ")
        print(f"  {r['id']:>4}  [{r['category']:10s}] {key_tag:25s} {_ts(r['updated_at'])} hits={r['access_count']}")
        print(f"       {snippet}")
        print()
    print(f"--- {len(rows)} memory(-ies) ---")
    db.close()


def cmd_read(args):
    db = get_db()
    r = db.execute("""
        SELECT id, key, content, category, tags, created_at, updated_at, access_count
        FROM memories WHERE id=?
    """, (args.read,)).fetchone()
    if not r:
        print(f"(no memory with id={args.read})")
        sys.exit(1)

    db.execute("UPDATE memories SET access_count = access_count + 1 WHERE id=?", (r["id"],))
    db.commit()

    print(f"ID:        {r['id']}")
    print(f"Key:       {r['key'] or '-'}")
    print(f"Category:  {r['category']}")
    print(f"Tags:      {r['tags'] or '-'}")
    print(f"Created:   {_ts(r['created_at'])}")
    print(f"Updated:   {_ts(r['updated_at'])}")
    print(f"Accessed:  {r['access_count']} times")
    print("─" * 40)
    print(r["content"])
    db.close()


def cmd_forget(args):
    db = get_db()
    rid = args.forget
    r = db.execute("SELECT id FROM memories WHERE id=?", (rid,)).fetchone()
    if not r:
        print(f"(no memory with id={rid})")
        sys.exit(1)
    db.execute("DELETE FROM memories WHERE id=?", (rid,))
    db.commit()
    print(f"✓ Memory {rid} deleted")
    db.close()


def cmd_recent(args):
    limit = min(args.limit or 10, 100)
    db = get_db()
    rows = db.execute("""
        SELECT id, key, content, category, tags, updated_at
        FROM memories ORDER BY updated_at DESC LIMIT ?
    """, (limit,)).fetchall()
    if not rows:
        print("(no recent memories)")
        return
    for r in rows:
        key_tag = r["key"] if r["key"] else f"#{r['id']}"
        snippet = r["content"][:100].replace("\n", " ")
        print(f"  [{r['category']:10s}] {key_tag:25s} {_ts(r['updated_at'])}")
        print(f"       {snippet}")
        print()
    print(f"--- {len(rows)} recent ---")
    db.close()


def cmd_stats(args):
    db = get_db()
    total = db.execute("SELECT COUNT(*) FROM memories").fetchone()[0]
    cats = db.execute("""
        SELECT category, COUNT(*) as cnt FROM memories GROUP BY category ORDER BY cnt DESC
    """).fetchall()
    fts = db.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='memories_fts'").fetchone()

    minutes_ago = db.execute("""
        SELECT MIN(updated_at), MAX(updated_at) FROM memories
    """).fetchone()

    oldest = _ts(minutes_ago[0]) if minutes_ago and minutes_ago[0] else "-"
    newest = _ts(minutes_ago[1]) if minutes_ago and minutes_ago[1] else "-"

    print(f"Database:     {DB_PATH}")
    print(f"Total:        {total} memories")
    print(f"FTS5 search:  {'✓ enabled' if fts else '✗ not available (LIKE fallback)'}")
    print(f"Oldest:       {oldest}")
    print(f"Newest:       {newest}")
    print()
    if cats:
        print("By category:")
        for c in cats:
            print(f"  {c['category']:15s} {c['cnt']}")

    db_size = DB_PATH.stat().st_size if DB_PATH.exists() else 0
    print(f"\nDB size:      {db_size/1024:.1f} KB")
    db.close()


def cmd_export(args):
    fmt = args.format or "json"
    db = get_db()
    rows = db.execute("""
        SELECT id, key, content, category, tags, created_at, updated_at, access_count
        FROM memories ORDER BY updated_at DESC
    """).fetchall()

    if fmt == "json":
        data = [dict(r) for r in rows]
        print(json.dumps(data, indent=2, ensure_ascii=False, default=str))
    else:  # markdown
        print("# Memory Export\n")
        for r in rows:
            title = r['key'] or f"Memory #{r['id']}"
            print(f"## {title}  [{r['category']}]")
            print(f"  - **ID:** {r['id']}  **Tags:** {r['tags'] or '-'}")
            print(f"  - **Created:** {_ts(r['created_at'])}  **Updated:** {_ts(r['updated_at'])}")
            print(f"  - **Accessed:** {r['access_count']} times")
            print()
            print(r["content"])
            print()
            print("---")
            print()
    db.close()


# ── Main ──

def main():
    import argparse
    p = argparse.ArgumentParser(description="local-memory: persistent memory for Codex")
    sub = p.add_subparsers(dest="command")

    # save
    sp = sub.add_parser("save", help="Save a memory")
    sp.add_argument("save", nargs="?", metavar="CONTENT", help="Memory content (or pipe stdin)")
    sp.add_argument("-k", "--key", help="Unique key (optional)")
    sp.add_argument("-c", "--category", default="general", help="Category (general, preference, entity, event, case, pattern, project, task, decision, ...)")
    sp.add_argument("-t", "--tags", help="Comma-separated tags")

    # search
    sp = sub.add_parser("search", help="Search memories")
    sp.add_argument("search", metavar="QUERY", help="Search query (FTS5 or LIKE)")
    sp.add_argument("-n", "--limit", type=int, default=10, help="Max results")

    # list
    sp = sub.add_parser("list", help="List memories")
    sp.add_argument("-n", "--limit", type=int, default=20, help="Max results")
    sp.add_argument("-c", "--category", help="Filter by category")

    # read
    sp = sub.add_parser("read", help="Read a memory by ID")
    sp.add_argument("read", type=int, metavar="ID")

    # forget
    sp = sub.add_parser("forget", help="Delete a memory by ID")
    sp.add_argument("forget", type=int, metavar="ID")

    # recent
    sp = sub.add_parser("recent", help="Show recent memories")
    sp.add_argument("-n", "--limit", type=int, default=10, help="Max results")

    # stats
    sp = sub.add_parser("stats", help="Database statistics")

    # export
    sp = sub.add_parser("export", help="Export all memories")
    sp.add_argument("-f", "--format", choices=["json", "markdown"], default="json", help="Output format")

    args = p.parse_args()

    # Auto-create DB dir
    DB_DIR.mkdir(parents=True, exist_ok=True)

    if not args.command:
        p.print_help()
        sys.exit(1)

    cmd_map = {
        "save": cmd_save,
        "search": cmd_search,
        "list": cmd_list,
        "read": cmd_read,
        "forget": cmd_forget,
        "recent": cmd_recent,
        "stats": cmd_stats,
        "export": cmd_export,
    }
    cmd_map[args.command](args)


if __name__ == "__main__":
    main()

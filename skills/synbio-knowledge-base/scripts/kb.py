#!/usr/bin/env python3
"""Project-scoped UTF-8 text archive and keyword retrieval. No network access."""

import argparse
import hashlib
import json
import sqlite3
import sys
from datetime import datetime, timezone
from pathlib import Path

MAX_BYTES = 10 * 1024 * 1024
SCHEMA_VERSION = 1
META_COLUMNS = (
    "id, project, source, locator, title, imported_path, sha256, version, "
    "state, created_at, updated_at"
)


def nonempty(value):
    value = value.strip()
    if not value or "\x00" in value:
        raise argparse.ArgumentTypeError("must be nonempty and contain no NUL")
    return value


def positive_limit(value):
    try:
        result = int(value)
    except ValueError as exc:
        raise argparse.ArgumentTypeError("must be an integer") from exc
    if not 1 <= result <= 1000:
        raise argparse.ArgumentTypeError("must be between 1 and 1000")
    return result


def open_db(path, writable):
    path = Path(path).expanduser().resolve()
    if writable:
        path.parent.mkdir(parents=True, exist_ok=True)
        conn = sqlite3.connect(str(path), timeout=15)
    else:
        if not path.is_file():
            raise ValueError("Database not found; add a document first.")
        conn = sqlite3.connect(path.as_uri() + "?mode=ro", uri=True, timeout=15)
    conn.row_factory = sqlite3.Row
    try:
        version = conn.execute("PRAGMA user_version").fetchone()[0]
        if writable and version == 0:
            tables = conn.execute(
                "SELECT name FROM sqlite_master WHERE type='table'"
            ).fetchall()
            if tables:
                raise ValueError("Unrecognized database; choose a new database path.")
            with conn:
                conn.execute("""
                    CREATE TABLE documents (
                        id TEXT PRIMARY KEY,
                        project TEXT NOT NULL,
                        source TEXT NOT NULL,
                        locator TEXT NOT NULL,
                        title TEXT NOT NULL,
                        imported_path TEXT NOT NULL,
                        body TEXT NOT NULL,
                        sha256 TEXT NOT NULL,
                        version INTEGER NOT NULL,
                        state TEXT NOT NULL CHECK(state = 'READY'),
                        created_at TEXT NOT NULL,
                        updated_at TEXT NOT NULL,
                        UNIQUE(project, source)
                    )
                """)
                conn.execute("PRAGMA user_version = 1")
        elif version != SCHEMA_VERSION:
            raise ValueError("Unsupported schema version; use a compatible release.")
        return conn
    except Exception:
        conn.close()
        raise


def read_input(filename):
    path = Path(filename).expanduser().resolve(strict=True)
    if not path.is_file() or path.suffix.lower() not in {".md", ".txt"}:
        raise ValueError("Input must be a .md or .txt file; extract PDF/Word first.")
    with path.open("rb") as stream:
        raw = stream.read(MAX_BYTES + 1)
    if len(raw) > MAX_BYTES:
        raise ValueError("Input exceeds 10 MiB; split it into source-located files.")
    body = raw.decode("utf-8-sig").replace("\r\n", "\n").replace("\r", "\n")
    if not body.strip() or "\x00" in body:
        raise ValueError("Input is empty or contains NUL bytes.")
    return str(path), body


def add_document(args):
    path, body = read_input(args.file)
    source = args.source or path
    title = args.title or Path(path).name
    locator = args.locator or "Imported text; see numbered lines"
    digest = hashlib.sha256(body.encode("utf-8")).hexdigest()
    identifier = hashlib.sha256(
        json.dumps([args.project, source], ensure_ascii=False).encode("utf-8")
    ).hexdigest()[:24]
    now = datetime.now(timezone.utc).isoformat(timespec="seconds")
    conn = open_db(args.db, writable=True)
    try:
        with conn:
            old = conn.execute(
                "SELECT * FROM documents WHERE project=? AND source=?",
                (args.project, source),
            ).fetchone()
            if old is None:
                conn.execute(
                    "INSERT INTO documents VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
                    (identifier, args.project, source, locator, title, path, body,
                     digest, 1, "READY", now, now),
                )
                action = "added"
            elif all((old[key] == val) for key, val in (
                ("sha256", digest), ("locator", locator), ("title", title),
                ("imported_path", path),
            )):
                action = "unchanged"
            else:
                identifier = old["id"]
                conn.execute(
                    "UPDATE documents SET locator=?, title=?, imported_path=?, "
                    "body=?, sha256=?, version=version+1, updated_at=? "
                    "WHERE project=? AND source=?",
                    (locator, title, path, body, digest, now, args.project, source),
                )
                action = "updated"
            record = conn.execute(
                f"SELECT {META_COLUMNS} FROM documents WHERE project=? AND source=?",
                (args.project, source),
            ).fetchone()
        return {"action": action, "document": dict(record)}
    finally:
        conn.close()


def list_documents(conn, args):
    total = conn.execute(
        "SELECT COUNT(*) FROM documents WHERE project=?", (args.project,)
    ).fetchone()[0]
    rows = conn.execute(
        f"SELECT {META_COLUMNS} FROM documents WHERE project=? "
        "ORDER BY source LIMIT ? OFFSET ?",
        (args.project, args.limit, args.offset),
    ).fetchall()
    return {"project": args.project, "total": total, "offset": args.offset,
            "documents": [dict(row) for row in rows]}


def get_document(conn, args):
    row = conn.execute(
        "SELECT * FROM documents WHERE project=? AND id=?", (args.project, args.id)
    ).fetchone()
    if row is None:
        raise ValueError("Document not found in the requested project.")
    record = dict(row)
    body = record.pop("body")
    record["lines"] = [
        {"line": index, "text": line}
        for index, line in enumerate(body.splitlines(), start=1)
    ]
    return {"project": args.project, "document": record}


def search_documents(conn, args):
    terms = list(dict.fromkeys(args.query.casefold().split()))
    if not terms:
        raise ValueError("Query must contain a keyword.")
    matches = []
    cursor = conn.execute(
        "SELECT * FROM documents WHERE project=?", (args.project,)
    )
    for row in cursor:
        body = row["body"]
        folded = body.casefold()
        if not all(term in folded for term in terms):
            continue
        hits = []
        for index, line in enumerate(body.splitlines(), start=1):
            if any(term in line.casefold() for term in terms):
                hits.append({"line": index, "text": line})
        record = dict(row)
        record.pop("body")
        record["score"] = sum(folded.count(term) for term in terms)
        record["hits"] = hits[:args.max_hits]
        record["total_hit_lines"] = len(hits)
        matches.append(record)
    matches.sort(key=lambda record: (-record["score"], record["source"]))
    return {"project": args.project, "query": args.query,
            "method": "casefolded substring AND across document body",
            "total": len(matches), "documents": matches[:args.limit]}


def make_parser():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--db", required=True, type=nonempty, help="Local SQLite path")
    parser.add_argument("--project", required=True, type=nonempty,
                        help="Exact project namespace; required for every command")
    sub = parser.add_subparsers(dest="command", required=True)
    add = sub.add_parser("add", help="Add or update one text source")
    add.add_argument("file", type=nonempty)
    add.add_argument("--source", type=nonempty,
                     help="Stable unique source identity; default absolute input path")
    add.add_argument("--locator", type=nonempty, help="Original page/section, if known")
    add.add_argument("--title", type=nonempty)
    listing = sub.add_parser("list", help="List documents in one project")
    listing.add_argument("--limit", type=positive_limit, default=100)
    listing.add_argument("--offset", type=int, default=0)
    search = sub.add_parser("search", help="Keyword substring AND search")
    search.add_argument("query", type=nonempty)
    search.add_argument("--limit", type=positive_limit, default=20)
    search.add_argument("--max-hits", type=positive_limit, default=20)
    get = sub.add_parser("get", help="Read a current document with numbered lines")
    get.add_argument("id", type=nonempty)
    return parser


def main():
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")
        sys.stderr.reconfigure(encoding="utf-8")
    parser = make_parser()
    args = parser.parse_args()
    if args.command == "list" and args.offset < 0:
        parser.error("--offset must be zero or positive")
    try:
        if args.command == "add":
            result = add_document(args)
        else:
            conn = open_db(args.db, writable=False)
            try:
                result = {"list": list_documents, "search": search_documents,
                          "get": get_document}[args.command](conn, args)
            finally:
                conn.close()
        print(json.dumps(result, ensure_ascii=False, indent=2))
        return 0
    except (OSError, ValueError, sqlite3.Error) as exc:
        print(json.dumps({"error": str(exc)}, ensure_ascii=False), file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())

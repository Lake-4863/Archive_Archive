from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path

import aiosqlite


@dataclass(frozen=True)
class Article:
    source: str
    title: str
    url: str
    published_at: str | None
    summary: str
    content: str
    keywords: tuple[str, ...] = ()


async def init_db(database_path: Path) -> None:
    database_path.parent.mkdir(parents=True, exist_ok=True)
    async with aiosqlite.connect(database_path) as db:
        await db.execute(
            """
            CREATE TABLE IF NOT EXISTS articles (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                source TEXT NOT NULL,
                title TEXT NOT NULL,
                url TEXT NOT NULL UNIQUE,
                published_at TEXT,
                summary TEXT NOT NULL,
                content TEXT NOT NULL,
                fetched_at TEXT NOT NULL
            )
            """
        )
        rows = await db.execute_fetchall(
            "SELECT sql FROM sqlite_master WHERE type='table' AND name='article_search'"
        )
        if not rows:
            try:
                await db.execute(
                    "CREATE VIRTUAL TABLE article_search "
                    "USING fts5(title, summary, content, url UNINDEXED, source UNINDEXED, tokenize='trigram')"
                )
            except aiosqlite.Error:
                await db.execute(
                    "CREATE VIRTUAL TABLE article_search "
                    "USING fts5(title, summary, content, url UNINDEXED, source UNINDEXED)"
                )
        elif "trigram" not in (rows[0][0] or "").lower():
            try:
                await db.execute(
                    "CREATE VIRTUAL TABLE _article_search_new "
                    "USING fts5(title, summary, content, url UNINDEXED, source UNINDEXED, tokenize='trigram')"
                )
                await db.execute(
                    "INSERT INTO _article_search_new(rowid, title, summary, content, url, source) "
                    "SELECT rowid, title, summary, content, url, source FROM article_search"
                )
                await db.execute("DROP TABLE article_search")
                await db.execute("ALTER TABLE _article_search_new RENAME TO article_search")
            except aiosqlite.Error:
                try:
                    await db.execute("DROP TABLE IF EXISTS _article_search_new")
                except aiosqlite.Error:
                    pass
        await db.execute(
            """
            CREATE TABLE IF NOT EXISTS keywords (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                value TEXT NOT NULL UNIQUE,
                created_at TEXT NOT NULL
            )
            """
        )
        await db.execute(
            """
            CREATE TABLE IF NOT EXISTS article_keywords (
                article_id INTEGER NOT NULL,
                keyword_id INTEGER NOT NULL,
                PRIMARY KEY (article_id, keyword_id),
                FOREIGN KEY (article_id) REFERENCES articles(id) ON DELETE CASCADE,
                FOREIGN KEY (keyword_id) REFERENCES keywords(id) ON DELETE CASCADE
            )
            """
        )
        try:
            await db.execute("ALTER TABLE articles ADD COLUMN notified_at TEXT")
        except aiosqlite.Error:
            pass  # column already exists
        await db.commit()


async def upsert_articles(database_path: Path, articles: list[Article]) -> int:
    await init_db(database_path)
    inserted = 0
    async with aiosqlite.connect(database_path) as db:
        for article in articles:
            cursor = await db.execute(
                """
                INSERT OR IGNORE INTO articles
                    (source, title, url, published_at, summary, content, fetched_at)
                VALUES (?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    article.source,
                    article.title,
                    article.url,
                    article.published_at,
                    article.summary,
                    article.content,
                    datetime.now(timezone.utc).isoformat(),
                ),
            )
            if cursor.rowcount:
                inserted += 1
                await db.execute(
                    """
                    INSERT INTO article_search (rowid, title, summary, content, url, source)
                    VALUES (last_insert_rowid(), ?, ?, ?, ?, ?)
                    """,
                    (
                        article.title,
                        article.summary,
                        article.content,
                        article.url,
                        article.source,
                    ),
                )
            article_id = await _article_id(db, article.url)
            for keyword in article.keywords:
                keyword_id = await _keyword_id(db, keyword)
                if keyword_id is not None:
                    await db.execute(
                        """
                        INSERT OR IGNORE INTO article_keywords (article_id, keyword_id)
                        VALUES (?, ?)
                        """,
                        (article_id, keyword_id),
                    )
        await db.commit()
    return inserted


async def latest_articles(database_path: Path, limit: int) -> list[Article]:
    await init_db(database_path)
    async with aiosqlite.connect(database_path) as db:
        rows = await db.execute_fetchall(
            """
            SELECT source, title, url, published_at, summary, content
            FROM articles
            ORDER BY COALESCE(published_at, fetched_at) DESC
            LIMIT ?
            """,
            (limit,),
        )
    return [Article(*row) for row in rows]


async def latest_articles_by_keyword(
    database_path: Path,
    keyword: str,
    limit: int,
) -> list[Article]:
    await init_db(database_path)
    async with aiosqlite.connect(database_path) as db:
        rows = await db.execute_fetchall(
            """
            SELECT a.source, a.title, a.url, a.published_at, a.summary, a.content
            FROM articles a
            JOIN article_keywords ak ON ak.article_id = a.id
            JOIN keywords k ON k.id = ak.keyword_id
            WHERE k.value = ?
            ORDER BY COALESCE(a.published_at, a.fetched_at) DESC
            LIMIT ?
            """,
            (keyword, limit),
        )
    return [Article(*row, (keyword,)) for row in rows]


async def latest_unnotified_articles_by_keyword(
    database_path: Path,
    keyword: str,
    limit: int,
) -> list[Article]:
    await init_db(database_path)
    async with aiosqlite.connect(database_path) as db:
        rows = await db.execute_fetchall(
            """
            SELECT a.source, a.title, a.url, a.published_at, a.summary, a.content
            FROM articles a
            JOIN article_keywords ak ON ak.article_id = a.id
            JOIN keywords k ON k.id = ak.keyword_id
            WHERE k.value = ? AND a.notified_at IS NULL
            ORDER BY COALESCE(a.published_at, a.fetched_at) DESC
            LIMIT ?
            """,
            (keyword, limit),
        )
    return [Article(*row, (keyword,)) for row in rows]


async def mark_articles_notified(database_path: Path, urls: list[str]) -> None:
    if not urls:
        return
    await init_db(database_path)
    now = datetime.now(timezone.utc).isoformat()
    async with aiosqlite.connect(database_path) as db:
        await db.executemany(
            "UPDATE articles SET notified_at = ? WHERE url = ? AND notified_at IS NULL",
            [(now, url) for url in urls],
        )
        await db.commit()


async def search_articles(database_path: Path, query: str, limit: int = 8) -> list[Article]:
    await init_db(database_path)
    if not query.strip():
        return []
    async with aiosqlite.connect(database_path) as db:
        try:
            rows = await db.execute_fetchall(
                """
                SELECT a.source, a.title, a.url, a.published_at, a.summary, a.content
                FROM article_search s
                JOIN articles a ON a.id = s.rowid
                WHERE article_search MATCH ?
                ORDER BY bm25(article_search)
                LIMIT ?
                """,
                (query, limit),
            )
        except aiosqlite.Error:
            rows = []
        if rows:
            return [Article(*row) for row in rows]

        terms = [t for t in query.split() if t]
        if not terms:
            return []
        conditions = " OR ".join(
            ["(title LIKE ? OR summary LIKE ? OR content LIKE ?)"] * len(terms)
        )
        params = [p for t in terms for p in (f"%{t}%", f"%{t}%", f"%{t}%")]
        rows = await db.execute_fetchall(
            f"""
            SELECT source, title, url, published_at, summary, content
            FROM articles
            WHERE {conditions}
            ORDER BY COALESCE(published_at, fetched_at) DESC
            LIMIT ?
            """,
            (*params, limit),
        )
    return [Article(*row) for row in rows]


async def sync_keywords(database_path: Path, keywords: list[str]) -> None:
    await init_db(database_path)
    normalized = [normalize_keyword(k) for k in keywords if normalize_keyword(k)]
    async with aiosqlite.connect(database_path) as db:
        for kw in normalized:
            await db.execute(
                "INSERT OR IGNORE INTO keywords (value, created_at) VALUES (?, ?)",
                (kw, datetime.now(timezone.utc).isoformat()),
            )
        await db.commit()


async def add_keyword(database_path: Path, keyword: str) -> bool:
    await init_db(database_path)
    normalized = normalize_keyword(keyword)
    if not normalized:
        return False
    async with aiosqlite.connect(database_path) as db:
        cursor = await db.execute(
            """
            INSERT OR IGNORE INTO keywords (value, created_at)
            VALUES (?, ?)
            """,
            (normalized, datetime.now(timezone.utc).isoformat()),
        )
        await db.commit()
    return bool(cursor.rowcount)


async def delete_keyword(database_path: Path, keyword: str) -> bool:
    await init_db(database_path)
    normalized = normalize_keyword(keyword)
    async with aiosqlite.connect(database_path) as db:
        rows = await db.execute_fetchall("SELECT id FROM keywords WHERE value = ?", (normalized,))
        if not rows:
            return False
        keyword_id = int(rows[0][0])
        await db.execute("DELETE FROM article_keywords WHERE keyword_id = ?", (keyword_id,))
        cursor = await db.execute("DELETE FROM keywords WHERE value = ?", (normalized,))
        await db.commit()
    return bool(cursor.rowcount)


async def list_keywords(database_path: Path) -> list[str]:
    await init_db(database_path)
    async with aiosqlite.connect(database_path) as db:
        rows = await db.execute_fetchall(
            "SELECT value FROM keywords ORDER BY value COLLATE NOCASE"
        )
    return [row[0] for row in rows]


def normalize_keyword(keyword: str) -> str:
    return " ".join(keyword.strip().split())


async def _article_id(db: aiosqlite.Connection, url: str) -> int:
    row = await db.execute_fetchall("SELECT id FROM articles WHERE url = ?", (url,))
    return int(row[0][0])


async def _keyword_id(db: aiosqlite.Connection, keyword: str) -> int | None:
    normalized = normalize_keyword(keyword)
    if not normalized:
        return None
    row = await db.execute_fetchall("SELECT id FROM keywords WHERE value = ?", (normalized,))
    if not row:
        return None
    return int(row[0][0])

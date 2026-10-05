import sqlite3
from contextlib import contextmanager
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional
from lc.config import DB_PATH


class MemoryManager:
    """Manages long-term institutional memory, tickets, and mistake vaccines."""

    def __init__(self, db_path: Optional[Path] = None):
        self.db_path = db_path or DB_PATH
        self._init_db()

    @contextmanager
    def _get_connection(self):
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        try:
            yield conn
        finally:
            conn.close()

    def _init_db(self) -> None:
        """Create necessary tables if they don't exist."""
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS mistake_vaccines (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    stack TEXT NOT NULL,
                    symptom TEXT NOT NULL,
                    root_cause TEXT NOT NULL,
                    prevention_rule TEXT NOT NULL,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            """)
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS sessions (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    task TEXT NOT NULL,
                    status TEXT NOT NULL,
                    summary TEXT,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            """)
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS tickets (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    session_id INTEGER,
                    title TEXT NOT NULL,
                    specs TEXT NOT NULL,
                    acceptance_criteria TEXT NOT NULL,
                    definition_of_done TEXT NOT NULL,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    FOREIGN KEY (session_id) REFERENCES sessions (id)
                )
            """)
            conn.commit()

    def record_vaccine(self, stack: str, symptom: str, root_cause: str, prevention_rule: str) -> int:
        """Store a new mistake vaccine rule."""
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                INSERT INTO mistake_vaccines (stack, symptom, root_cause, prevention_rule)
                VALUES (?, ?, ?, ?)
            """, (stack.lower(), symptom, root_cause, prevention_rule))
            conn.commit()
            return cursor.lastrowid or 0

    def get_relevant_vaccines(self, stack: str = "", query: str = "", limit: int = 5) -> List[Dict[str, Any]]:
        """Retrieve relevant vaccines matching stack or keywords."""
        with self._get_connection() as conn:
            cursor = conn.cursor()
            query_lower = query.lower()
            stack_lower = stack.lower()

            cursor.execute("SELECT * FROM mistake_vaccines ORDER BY id DESC")
            all_vaccines = [dict(row) for row in cursor.fetchall()]

            if not stack_lower and not query_lower:
                return all_vaccines[:limit]

            scored: List[tuple[int, Dict[str, Any]]] = []
            for v in all_vaccines:
                score = 0
                if stack_lower and stack_lower in v["stack"]:
                    score += 5
                
                # Check symptom or root cause keywords
                for word in query_lower.split():
                    if len(word) > 2:
                        if word in v["symptom"].lower():
                            score += 2
                        if word in v["root_cause"].lower():
                            score += 1
                        if word in v["prevention_rule"].lower():
                            score += 1

                if score > 0:
                    scored.append((score, v))

            scored.sort(key=lambda x: x[0], reverse=True)
            return [v for _, v in scored[:limit]] if scored else all_vaccines[:limit]

    def list_vaccines(self) -> List[Dict[str, Any]]:
        """List all vaccines stored in the database."""
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT * FROM mistake_vaccines ORDER BY id DESC")
            return [dict(row) for row in cursor.fetchall()]

    def record_session(self, task: str, status: str, summary: str = "") -> int:
        """Log a sprint session."""
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                INSERT INTO sessions (task, status, summary)
                VALUES (?, ?, ?)
            """, (task, status, summary))
            conn.commit()
            return cursor.lastrowid or 0

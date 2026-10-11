"""OpenNow Multi-Table Relational Database Engine
==================================================
Production-grade SQLite relational engine with WAL mode, strict foreign key enforcement,
rich entity relationship queries, CMDB topology graph extraction, operational stats,
and intelligent batch upsert with foreign key resolution.

Tables:
- users (id, external_id, username, email, full_name, department, role, created_at, metadata)
- groups (id, external_id, name, description, manager_id, email, metadata)
- group_members (id, group_id, user_id, role)
- cmdb_cis (id, external_id, name, ci_type, environment, ip_address, owner_group_id, tier, health_status, attributes)
- cmdb_relationships (id, parent_ci_id, child_ci_id, relationship_type, depth)
- tasks (id, task_number, external_id, task_type, title, description, priority, status,
         caller_id, assigned_to_id, assignment_group_id, cmdb_ci_id, created_at, updated_at,
         resolved_at, closed_at, sla_due_at, custom_fields)
- journal_entries (id, task_id, author_id, entry_type, body, created_at)
- sla_instances (id, task_id, stage, percentage, target_seconds, breached, pause_duration)
"""

from __future__ import annotations

import datetime
import json
import logging
import os
import sqlite3
import unittest
from contextlib import contextmanager
from typing import Any, Dict, Generator, List, Optional, Sequence, Tuple, Union

logger = logging.getLogger("opennow.relational_db")

# Default database location
DEFAULT_DB_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "data")
DEFAULT_DB_PATH = os.path.join(DEFAULT_DB_DIR, "opennow_relational.db")


def _to_json_str(val: Any) -> str:
    """Safely converts an object, dict, or list into a serialized JSON string."""
    if val is None:
        return "{}"
    if isinstance(val, (dict, list)):
        try:
            return json.dumps(val, ensure_ascii=False)
        except (TypeError, ValueError):
            return "{}"
    if isinstance(val, str):
        val_trimmed = val.strip()
        if (val_trimmed.startswith("{") and val_trimmed.endswith("}")) or (
            val_trimmed.startswith("[") and val_trimmed.endswith("]")
        ):
            try:
                json.loads(val_trimmed)
                return val_trimmed
            except (ValueError, TypeError):
                pass
        return json.dumps({"value": val}, ensure_ascii=False)
    return json.dumps(val, ensure_ascii=False)


def _from_json_str(val: Any, default: Any = None) -> Any:
    """Parses JSON text into Python dict or list, with fallback to default."""
    if val is None:
        return default if default is not None else {}
    if isinstance(val, (dict, list)):
        return val
    if isinstance(val, str):
        val_trimmed = val.strip()
        if not val_trimmed:
            return default if default is not None else {}
        try:
            return json.loads(val_trimmed)
        except (ValueError, TypeError):
            return default if default is not None else {}
    return default if default is not None else {}


def _parse_iso_date(dt_str: Optional[str]) -> Optional[datetime.datetime]:
    """Parse ISO date strings reliably."""
    if not dt_str:
        return None
    try:
        # Remove trailing Z if present
        clean_str = dt_str.replace("Z", "+00:00")
        return datetime.datetime.fromisoformat(clean_str)
    except Exception:
        return None


class RelationalDatabase:
    """Production-grade multi-table relational database engine for OpenNow ITSM & CMDB."""

    def __init__(self, db_path: str = DEFAULT_DB_PATH):
        self.db_path = db_path
        self._is_memory = db_path == ":memory:" or "mode=memory" in db_path
        self._mem_conn: Optional[sqlite3.Connection] = None

        if self._is_memory:
            self._mem_conn = sqlite3.connect(
                self.db_path,
                timeout=30.0,
                check_same_thread=False,
                detect_types=sqlite3.PARSE_DECLTYPES | sqlite3.PARSE_COLNAMES,
            )
            self._mem_conn.row_factory = sqlite3.Row
            self._mem_conn.execute("PRAGMA foreign_keys = ON;")
            self._mem_conn.execute("PRAGMA busy_timeout = 30000;")
        else:
            self._ensure_db_dir()

        self.init_schema()

    def _ensure_db_dir(self) -> None:
        """Ensures the parent directory for SQLite file exists."""
        if not self._is_memory:
            db_dir = os.path.dirname(os.path.abspath(self.db_path))
            if db_dir and not os.path.exists(db_dir):
                os.makedirs(db_dir, exist_ok=True)

    @contextmanager
    def get_connection(self) -> Generator[sqlite3.Connection, None, None]:
        """Provides an isolated connection context with WAL mode and strict foreign keys."""
        if self._is_memory and self._mem_conn is not None:
            try:
                yield self._mem_conn
                self._mem_conn.commit()
            except Exception:
                self._mem_conn.rollback()
                raise
        else:
            conn = sqlite3.connect(
                self.db_path,
                timeout=30.0,
                detect_types=sqlite3.PARSE_DECLTYPES | sqlite3.PARSE_COLNAMES,
            )
            conn.row_factory = sqlite3.Row
            conn.execute("PRAGMA foreign_keys = ON;")
            conn.execute("PRAGMA journal_mode = WAL;")
            conn.execute("PRAGMA synchronous = NORMAL;")
            conn.execute("PRAGMA busy_timeout = 30000;")
            try:
                yield conn
                conn.commit()
            except Exception:
                conn.rollback()
                raise
            finally:
                conn.close()

    def init_schema(self) -> None:
        """Initializes multi-table relational schema with strict foreign keys and indexes."""
        with self.get_connection() as conn:
            cursor = conn.cursor()

            # 1. users
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS users (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    external_id TEXT UNIQUE,
                    username TEXT UNIQUE,
                    email TEXT,
                    full_name TEXT,
                    department TEXT,
                    role TEXT,
                    created_at TEXT NOT NULL,
                    metadata JSON DEFAULT '{}'
                );
            """)

            # 2. groups
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS groups (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    external_id TEXT UNIQUE,
                    name TEXT UNIQUE NOT NULL,
                    description TEXT,
                    manager_id INTEGER REFERENCES users(id) ON DELETE SET NULL,
                    email TEXT,
                    metadata JSON DEFAULT '{}'
                );
            """)

            # 3. group_members
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS group_members (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    group_id INTEGER NOT NULL REFERENCES groups(id) ON DELETE CASCADE,
                    user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
                    role TEXT DEFAULT 'member',
                    UNIQUE(group_id, user_id)
                );
            """)

            # 4. cmdb_cis
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS cmdb_cis (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    external_id TEXT UNIQUE,
                    name TEXT NOT NULL,
                    ci_type TEXT NOT NULL,
                    environment TEXT NOT NULL,
                    ip_address TEXT,
                    owner_group_id INTEGER REFERENCES groups(id) ON DELETE SET NULL,
                    tier INTEGER DEFAULT 2,
                    health_status TEXT DEFAULT 'healthy',
                    attributes JSON DEFAULT '{}'
                );
            """)

            # 5. cmdb_relationships
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS cmdb_relationships (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    parent_ci_id INTEGER NOT NULL REFERENCES cmdb_cis(id) ON DELETE CASCADE,
                    child_ci_id INTEGER NOT NULL REFERENCES cmdb_cis(id) ON DELETE CASCADE,
                    relationship_type TEXT NOT NULL,
                    depth INTEGER DEFAULT 1,
                    UNIQUE(parent_ci_id, child_ci_id, relationship_type)
                );
            """)

            # 6. tasks
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS tasks (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    task_number TEXT UNIQUE NOT NULL,
                    external_id TEXT UNIQUE,
                    task_type TEXT NOT NULL DEFAULT 'incident',
                    title TEXT NOT NULL,
                    description TEXT DEFAULT '',
                    priority TEXT NOT NULL DEFAULT 'P3',
                    status TEXT NOT NULL DEFAULT 'new',
                    caller_id INTEGER REFERENCES users(id) ON DELETE SET NULL,
                    assigned_to_id INTEGER REFERENCES users(id) ON DELETE SET NULL,
                    assignment_group_id INTEGER REFERENCES groups(id) ON DELETE SET NULL,
                    cmdb_ci_id INTEGER REFERENCES cmdb_cis(id) ON DELETE SET NULL,
                    created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL,
                    resolved_at TEXT,
                    closed_at TEXT,
                    sla_due_at TEXT,
                    custom_fields JSON DEFAULT '{}'
                );
            """)

            # 7. journal_entries
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS journal_entries (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    task_id INTEGER NOT NULL REFERENCES tasks(id) ON DELETE CASCADE,
                    author_id INTEGER REFERENCES users(id) ON DELETE SET NULL,
                    entry_type TEXT NOT NULL,
                    body TEXT NOT NULL,
                    created_at TEXT NOT NULL
                );
            """)

            # 8. sla_instances
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS sla_instances (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    task_id INTEGER NOT NULL REFERENCES tasks(id) ON DELETE CASCADE,
                    stage TEXT NOT NULL DEFAULT 'in_progress',
                    percentage REAL DEFAULT 0.0,
                    target_seconds INTEGER NOT NULL DEFAULT 14400,
                    breached INTEGER DEFAULT 0,
                    pause_duration INTEGER DEFAULT 0
                );
            """)

            # Indexes for ultra-fast relational joins & lookups
            indexes = [
                "CREATE INDEX IF NOT EXISTS idx_users_ext_id ON users(external_id);",
                "CREATE INDEX IF NOT EXISTS idx_users_username ON users(username);",
                "CREATE INDEX IF NOT EXISTS idx_groups_ext_id ON groups(external_id);",
                "CREATE INDEX IF NOT EXISTS idx_groups_name ON groups(name);",
                "CREATE INDEX IF NOT EXISTS idx_group_members_group ON group_members(group_id);",
                "CREATE INDEX IF NOT EXISTS idx_group_members_user ON group_members(user_id);",
                "CREATE INDEX IF NOT EXISTS idx_cmdb_cis_ext_id ON cmdb_cis(external_id);",
                "CREATE INDEX IF NOT EXISTS idx_cmdb_cis_name ON cmdb_cis(name);",
                "CREATE INDEX IF NOT EXISTS idx_cmdb_cis_owner ON cmdb_cis(owner_group_id);",
                "CREATE INDEX IF NOT EXISTS idx_cmdb_cis_health ON cmdb_cis(health_status);",
                "CREATE INDEX IF NOT EXISTS idx_cmdb_rel_parent ON cmdb_relationships(parent_ci_id);",
                "CREATE INDEX IF NOT EXISTS idx_cmdb_rel_child ON cmdb_relationships(child_ci_id);",
                "CREATE INDEX IF NOT EXISTS idx_tasks_task_number ON tasks(task_number);",
                "CREATE INDEX IF NOT EXISTS idx_tasks_ext_id ON tasks(external_id);",
                "CREATE INDEX IF NOT EXISTS idx_tasks_status ON tasks(status);",
                "CREATE INDEX IF NOT EXISTS idx_tasks_priority ON tasks(priority);",
                "CREATE INDEX IF NOT EXISTS idx_tasks_type ON tasks(task_type);",
                "CREATE INDEX IF NOT EXISTS idx_tasks_caller ON tasks(caller_id);",
                "CREATE INDEX IF NOT EXISTS idx_tasks_assigned_to ON tasks(assigned_to_id);",
                "CREATE INDEX IF NOT EXISTS idx_tasks_assignment_group ON tasks(assignment_group_id);",
                "CREATE INDEX IF NOT EXISTS idx_tasks_ci ON tasks(cmdb_ci_id);",
                "CREATE INDEX IF NOT EXISTS idx_journal_task ON journal_entries(task_id, created_at);",
                "CREATE INDEX IF NOT EXISTS idx_sla_task ON sla_instances(task_id);",
            ]
            for idx in indexes:
                cursor.execute(idx)

    # =========================================================================
    # Task Number Generator
    # =========================================================================

    def generate_task_number(
        self, task_type: str = "incident", conn: Optional[sqlite3.Connection] = None
    ) -> str:
        """Generates standard ITSM task identifier (INC000101, CHG000201, PRB000301, REQ000401)."""
        prefix_map = {
            "incident": "INC",
            "change": "CHG",
            "problem": "PRB",
            "request": "REQ",
        }
        prefix = prefix_map.get(task_type.lower(), "TSK")

        def _generate(c: sqlite3.Connection) -> str:
            cursor = c.cursor()
            cursor.execute(
                "SELECT task_number FROM tasks WHERE task_number LIKE ? ORDER BY id DESC LIMIT 1",
                (f"{prefix}%",),
            )
            row = cursor.fetchone()
            if row and row["task_number"]:
                try:
                    num_str = row["task_number"][len(prefix) :]
                    next_num = int(num_str) + 1
                    return f"{prefix}{next_num:06d}"
                except ValueError:
                    pass

            start_offsets = {
                "INC": 10001,
                "CHG": 20001,
                "PRB": 30001,
                "REQ": 40001,
                "TSK": 50001,
            }
            return f"{prefix}{start_offsets.get(prefix, 10001):06d}"

        if conn is not None:
            return _generate(conn)
        with self.get_connection() as c:
            return _generate(c)

    # =========================================================================
    # Foreign Key Resolution Helpers
    # =========================================================================

    def resolve_user_id(
        self, ref: Any, conn: Optional[sqlite3.Connection] = None
    ) -> Optional[int]:
        """Resolves an integer ID, username, email, or external_id into a user integer ID."""
        if ref is None:
            return None
        if isinstance(ref, int):
            return ref

        ref_str = str(ref).strip()
        if not ref_str:
            return None

        # Check if numeric string
        if ref_str.isdigit():
            val_int = int(ref_str)
            # Verify existence
            def _check_id(c: sqlite3.Connection) -> Optional[int]:
                cur = c.cursor()
                cur.execute("SELECT id FROM users WHERE id = ?", (val_int,))
                row = cur.fetchone()
                return row["id"] if row else None

            if conn is not None:
                res = _check_id(conn)
                if res:
                    return res
            else:
                with self.get_connection() as c:
                    res = _check_id(c)
                    if res:
                        return res

        def _lookup(c: sqlite3.Connection) -> Optional[int]:
            cur = c.cursor()
            # 1. external_id
            cur.execute("SELECT id FROM users WHERE external_id = ?", (ref_str,))
            row = cur.fetchone()
            if row:
                return row["id"]
            # 2. username
            cur.execute("SELECT id FROM users WHERE username = ?", (ref_str,))
            row = cur.fetchone()
            if row:
                return row["id"]
            # 3. email
            cur.execute("SELECT id FROM users WHERE email = ?", (ref_str,))
            row = cur.fetchone()
            if row:
                return row["id"]
            return None

        if conn is not None:
            return _lookup(conn)
        with self.get_connection() as c:
            return _lookup(c)

    def resolve_group_id(
        self, ref: Any, conn: Optional[sqlite3.Connection] = None
    ) -> Optional[int]:
        """Resolves an integer ID, group name, or external_id into a group integer ID."""
        if ref is None:
            return None
        if isinstance(ref, int):
            return ref

        ref_str = str(ref).strip()
        if not ref_str:
            return None

        if ref_str.isdigit():
            val_int = int(ref_str)

            def _check_id(c: sqlite3.Connection) -> Optional[int]:
                cur = c.cursor()
                cur.execute("SELECT id FROM groups WHERE id = ?", (val_int,))
                row = cur.fetchone()
                return row["id"] if row else None

            if conn is not None:
                res = _check_id(conn)
                if res:
                    return res
            else:
                with self.get_connection() as c:
                    res = _check_id(c)
                    if res:
                        return res

        def _lookup(c: sqlite3.Connection) -> Optional[int]:
            cur = c.cursor()
            cur.execute("SELECT id FROM groups WHERE external_id = ?", (ref_str,))
            row = cur.fetchone()
            if row:
                return row["id"]
            cur.execute("SELECT id FROM groups WHERE name = ?", (ref_str,))
            row = cur.fetchone()
            if row:
                return row["id"]
            return None

        if conn is not None:
            return _lookup(conn)
        with self.get_connection() as c:
            return _lookup(c)

    def resolve_ci_id(
        self, ref: Any, conn: Optional[sqlite3.Connection] = None
    ) -> Optional[int]:
        """Resolves an integer ID, CI name, or external_id into a CI integer ID."""
        if ref is None:
            return None
        if isinstance(ref, int):
            return ref

        ref_str = str(ref).strip()
        if not ref_str:
            return None

        if ref_str.isdigit():
            val_int = int(ref_str)

            def _check_id(c: sqlite3.Connection) -> Optional[int]:
                cur = c.cursor()
                cur.execute("SELECT id FROM cmdb_cis WHERE id = ?", (val_int,))
                row = cur.fetchone()
                return row["id"] if row else None

            if conn is not None:
                res = _check_id(conn)
                if res:
                    return res
            else:
                with self.get_connection() as c:
                    res = _check_id(c)
                    if res:
                        return res

        def _lookup(c: sqlite3.Connection) -> Optional[int]:
            cur = c.cursor()
            cur.execute("SELECT id FROM cmdb_cis WHERE external_id = ?", (ref_str,))
            row = cur.fetchone()
            if row:
                return row["id"]
            cur.execute("SELECT id FROM cmdb_cis WHERE name = ?", (ref_str,))
            row = cur.fetchone()
            if row:
                return row["id"]
            return None

        if conn is not None:
            return _lookup(conn)
        with self.get_connection() as c:
            return _lookup(c)

    # =========================================================================
    # User Management (CRUD / Upsert)
    # =========================================================================

    def upsert_user(
        self,
        external_id: Optional[str] = None,
        username: Optional[str] = None,
        email: Optional[str] = None,
        full_name: Optional[str] = None,
        department: Optional[str] = None,
        role: Optional[str] = None,
        metadata: Optional[Union[Dict[str, Any], str]] = None,
        created_at: Optional[str] = None,
        user_id: Optional[int] = None,
        conn: Optional[sqlite3.Connection] = None,
    ) -> int:
        """Creates or updates a user record with conflict resolution on external_id, username, or user_id."""
        now_iso = datetime.datetime.now(datetime.timezone.utc).isoformat()
        meta_str = _to_json_str(metadata)
        created_iso = created_at or now_iso

        def _execute(c: sqlite3.Connection) -> int:
            cur = c.cursor()
            existing_id = None

            if user_id is not None:
                cur.execute("SELECT id FROM users WHERE id = ?", (user_id,))
                r = cur.fetchone()
                if r:
                    existing_id = r["id"]

            if existing_id is None and external_id:
                cur.execute("SELECT id FROM users WHERE external_id = ?", (external_id,))
                r = cur.fetchone()
                if r:
                    existing_id = r["id"]

            if existing_id is None and username:
                cur.execute("SELECT id FROM users WHERE username = ?", (username,))
                r = cur.fetchone()
                if r:
                    existing_id = r["id"]

            if existing_id is not None:
                cur.execute(
                    """
                    UPDATE users
                    SET external_id = COALESCE(?, external_id),
                        username = COALESCE(?, username),
                        email = COALESCE(?, email),
                        full_name = COALESCE(?, full_name),
                        department = COALESCE(?, department),
                        role = COALESCE(?, role),
                        metadata = COALESCE(?, metadata)
                    WHERE id = ?
                    """,
                    (external_id, username, email, full_name, department, role, meta_str, existing_id),
                )
                return existing_id

            cur.execute(
                """
                INSERT INTO users (external_id, username, email, full_name, department, role, created_at, metadata)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (external_id, username, email, full_name, department, role, created_iso, meta_str),
            )
            return cur.lastrowid

        if conn is not None:
            return _execute(conn)
        with self.get_connection() as c:
            return _execute(c)

    def get_user(
        self, user_id_or_ref: Union[int, str], conn: Optional[sqlite3.Connection] = None
    ) -> Optional[Dict[str, Any]]:
        """Retrieves a single user by ID, username, or external_id."""
        def _get(c: sqlite3.Connection) -> Optional[Dict[str, Any]]:
            cur = c.cursor()
            resolved_id = self.resolve_user_id(user_id_or_ref, conn=c)
            if not resolved_id:
                return None
            cur.execute("SELECT * FROM users WHERE id = ?", (resolved_id,))
            row = cur.fetchone()
            if not row:
                return None
            d = dict(row)
            d["metadata"] = _from_json_str(d.get("metadata"))
            return d

        if conn is not None:
            return _get(conn)
        with self.get_connection() as c:
            return _get(c)

    # =========================================================================
    # Group Management (CRUD / Upsert / Memberships)
    # =========================================================================

    def upsert_group(
        self,
        external_id: Optional[str] = None,
        name: Optional[str] = None,
        description: Optional[str] = None,
        manager_id: Optional[int] = None,
        email: Optional[str] = None,
        metadata: Optional[Union[Dict[str, Any], str]] = None,
        group_id: Optional[int] = None,
        conn: Optional[sqlite3.Connection] = None,
    ) -> int:
        """Creates or updates a group record with conflict resolution on external_id, name, or group_id."""
        meta_str = _to_json_str(metadata)

        def _execute(c: sqlite3.Connection) -> int:
            cur = c.cursor()
            existing_id = None

            if group_id is not None:
                cur.execute("SELECT id FROM groups WHERE id = ?", (group_id,))
                r = cur.fetchone()
                if r:
                    existing_id = r["id"]

            if existing_id is None and external_id:
                cur.execute("SELECT id FROM groups WHERE external_id = ?", (external_id,))
                r = cur.fetchone()
                if r:
                    existing_id = r["id"]

            if existing_id is None and name:
                cur.execute("SELECT id FROM groups WHERE name = ?", (name,))
                r = cur.fetchone()
                if r:
                    existing_id = r["id"]

            resolved_mgr = self.resolve_user_id(manager_id, conn=c) if manager_id is not None else None

            if existing_id is not None:
                cur.execute(
                    """
                    UPDATE groups
                    SET external_id = COALESCE(?, external_id),
                        name = COALESCE(?, name),
                        description = COALESCE(?, description),
                        manager_id = COALESCE(?, manager_id),
                        email = COALESCE(?, email),
                        metadata = COALESCE(?, metadata)
                    WHERE id = ?
                    """,
                    (external_id, name, description, resolved_mgr, email, meta_str, existing_id),
                )
                return existing_id

            if not name:
                raise ValueError("Group name is required to create a new group.")

            cur.execute(
                """
                INSERT INTO groups (external_id, name, description, manager_id, email, metadata)
                VALUES (?, ?, ?, ?, ?, ?)
                """,
                (external_id, name, description, resolved_mgr, email, meta_str),
            )
            return cur.lastrowid

        if conn is not None:
            return _execute(conn)
        with self.get_connection() as c:
            return _execute(c)

    def add_group_member(
        self,
        group_id: int,
        user_id: int,
        role: str = "member",
        conn: Optional[sqlite3.Connection] = None,
    ) -> int:
        """Adds or updates a group member role with strict relational constraint checking."""
        def _execute(c: sqlite3.Connection) -> int:
            cur = c.cursor()
            res_group = self.resolve_group_id(group_id, conn=c)
            res_user = self.resolve_user_id(user_id, conn=c)
            if not res_group or not res_user:
                raise ValueError(f"Invalid group_id ({group_id}) or user_id ({user_id})")

            cur.execute(
                "SELECT id FROM group_members WHERE group_id = ? AND user_id = ?",
                (res_group, res_user),
            )
            row = cur.fetchone()
            if row:
                cur.execute(
                    "UPDATE group_members SET role = ? WHERE id = ?",
                    (role, row["id"]),
                )
                return row["id"]

            cur.execute(
                "INSERT INTO group_members (group_id, user_id, role) VALUES (?, ?, ?)",
                (res_group, res_user, role),
            )
            return cur.lastrowid

        if conn is not None:
            return _execute(conn)
        with self.get_connection() as c:
            return _execute(c)

    def get_group(
        self, group_id_or_ref: Union[int, str], conn: Optional[sqlite3.Connection] = None
    ) -> Optional[Dict[str, Any]]:
        """Retrieves a group record with its manager and members list."""
        def _get(c: sqlite3.Connection) -> Optional[Dict[str, Any]]:
            cur = c.cursor()
            resolved_id = self.resolve_group_id(group_id_or_ref, conn=c)
            if not resolved_id:
                return None
            cur.execute("SELECT * FROM groups WHERE id = ?", (resolved_id,))
            row = cur.fetchone()
            if not row:
                return None
            d = dict(row)
            d["metadata"] = _from_json_str(d.get("metadata"))

            # Manager details
            if d.get("manager_id"):
                cur.execute(
                    "SELECT id, username, full_name, email, role FROM users WHERE id = ?",
                    (d["manager_id"],),
                )
                mgr = cur.fetchone()
                d["manager"] = dict(mgr) if mgr else None
            else:
                d["manager"] = None

            # Members
            cur.execute(
                """
                SELECT gm.id, gm.role AS membership_role, u.id AS user_id, u.username, u.full_name, u.email, u.department
                FROM group_members gm
                JOIN users u ON gm.user_id = u.id
                WHERE gm.group_id = ?
                ORDER BY u.full_name ASC
                """,
                (resolved_id,),
            )
            d["members"] = [dict(r) for r in cur.fetchall()]
            return d

        if conn is not None:
            return _get(conn)
        with self.get_connection() as c:
            return _get(c)

    # =========================================================================
    # CMDB & Configuration Items (CIs & Topology)
    # =========================================================================

    def upsert_ci(
        self,
        external_id: Optional[str] = None,
        name: Optional[str] = None,
        ci_type: Optional[str] = None,
        environment: str = "production",
        ip_address: Optional[str] = None,
        owner_group_id: Optional[int] = None,
        tier: int = 2,
        health_status: str = "healthy",
        attributes: Optional[Union[Dict[str, Any], str]] = None,
        ci_id: Optional[int] = None,
        conn: Optional[sqlite3.Connection] = None,
    ) -> int:
        """Upserts a Configuration Item (CI) with conflict resolution on external_id, name, or ci_id."""
        attr_str = _to_json_str(attributes)

        def _execute(c: sqlite3.Connection) -> int:
            cur = c.cursor()
            existing_id = None

            if ci_id is not None:
                cur.execute("SELECT id FROM cmdb_cis WHERE id = ?", (ci_id,))
                r = cur.fetchone()
                if r:
                    existing_id = r["id"]

            if existing_id is None and external_id:
                cur.execute("SELECT id FROM cmdb_cis WHERE external_id = ?", (external_id,))
                r = cur.fetchone()
                if r:
                    existing_id = r["id"]

            if existing_id is None and name:
                cur.execute("SELECT id FROM cmdb_cis WHERE name = ?", (name,))
                r = cur.fetchone()
                if r:
                    existing_id = r["id"]

            resolved_owner = (
                self.resolve_group_id(owner_group_id, conn=c)
                if owner_group_id is not None
                else None
            )

            if existing_id is not None:
                cur.execute(
                    """
                    UPDATE cmdb_cis
                    SET external_id = COALESCE(?, external_id),
                        name = COALESCE(?, name),
                        ci_type = COALESCE(?, ci_type),
                        environment = COALESCE(?, environment),
                        ip_address = COALESCE(?, ip_address),
                        owner_group_id = COALESCE(?, owner_group_id),
                        tier = COALESCE(?, tier),
                        health_status = COALESCE(?, health_status),
                        attributes = COALESCE(?, attributes)
                    WHERE id = ?
                    """,
                    (
                        external_id,
                        name,
                        ci_type,
                        environment,
                        ip_address,
                        resolved_owner,
                        tier,
                        health_status,
                        attr_str,
                        existing_id,
                    ),
                )
                return existing_id

            if not name or not ci_type:
                raise ValueError("CI name and ci_type are required to create a new CI.")

            cur.execute(
                """
                INSERT INTO cmdb_cis (external_id, name, ci_type, environment, ip_address, owner_group_id, tier, health_status, attributes)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    external_id,
                    name,
                    ci_type,
                    environment,
                    ip_address,
                    resolved_owner,
                    tier,
                    health_status,
                    attr_str,
                ),
            )
            return cur.lastrowid

        if conn is not None:
            return _execute(conn)
        with self.get_connection() as c:
            return _execute(c)

    def add_ci_relationship(
        self,
        parent_ci_id: int,
        child_ci_id: int,
        relationship_type: str,
        depth: int = 1,
        conn: Optional[sqlite3.Connection] = None,
    ) -> int:
        """Adds or updates a directed CMDB relationship between two CIs."""
        def _execute(c: sqlite3.Connection) -> int:
            cur = c.cursor()
            res_parent = self.resolve_ci_id(parent_ci_id, conn=c)
            res_child = self.resolve_ci_id(child_ci_id, conn=c)
            if not res_parent or not res_child:
                raise ValueError(
                    f"Invalid CI references: parent={parent_ci_id} ({res_parent}), child={child_ci_id} ({res_child})"
                )

            cur.execute(
                """
                SELECT id FROM cmdb_relationships
                WHERE parent_ci_id = ? AND child_ci_id = ? AND relationship_type = ?
                """,
                (res_parent, res_child, relationship_type),
            )
            row = cur.fetchone()
            if row:
                cur.execute(
                    "UPDATE cmdb_relationships SET depth = ? WHERE id = ?",
                    (depth, row["id"]),
                )
                return row["id"]

            cur.execute(
                """
                INSERT INTO cmdb_relationships (parent_ci_id, child_ci_id, relationship_type, depth)
                VALUES (?, ?, ?, ?)
                """,
                (res_parent, res_child, relationship_type, depth),
            )
            return cur.lastrowid

        if conn is not None:
            return _execute(conn)
        with self.get_connection() as c:
            return _execute(c)

    def get_ci(
        self, ci_id_or_ref: Union[int, str], conn: Optional[sqlite3.Connection] = None
    ) -> Optional[Dict[str, Any]]:
        """Retrieves a single CI with owner group and immediate upstream/downstream dependencies."""
        def _get(c: sqlite3.Connection) -> Optional[Dict[str, Any]]:
            cur = c.cursor()
            resolved_id = self.resolve_ci_id(ci_id_or_ref, conn=c)
            if not resolved_id:
                return None
            cur.execute(
                """
                SELECT ci.*, g.name AS owner_group_name
                FROM cmdb_cis ci
                LEFT JOIN groups g ON ci.owner_group_id = g.id
                WHERE ci.id = ?
                """,
                (resolved_id,),
            )
            row = cur.fetchone()
            if not row:
                return None
            d = dict(row)
            d["attributes"] = _from_json_str(d.get("attributes"))

            # Parents (Upstream: who points to this CI)
            cur.execute(
                """
                SELECT p.id, p.external_id, p.name, p.ci_type, p.environment, p.health_status,
                       p.tier, r.relationship_type, r.depth
                FROM cmdb_relationships r
                JOIN cmdb_cis p ON r.parent_ci_id = p.id
                WHERE r.child_ci_id = ?
                ORDER BY r.depth ASC, p.name ASC
                """,
                (resolved_id,),
            )
            d["parents"] = [dict(r) for r in cur.fetchall()]

            # Children (Downstream: who this CI points to)
            cur.execute(
                """
                SELECT ch.id, ch.external_id, ch.name, ch.ci_type, ch.environment, ch.health_status,
                       ch.tier, r.relationship_type, r.depth
                FROM cmdb_relationships r
                JOIN cmdb_cis ch ON r.child_ci_id = ch.id
                WHERE r.parent_ci_id = ?
                ORDER BY r.depth ASC, ch.name ASC
                """,
                (resolved_id,),
            )
            d["children"] = [dict(r) for r in cur.fetchall()]
            return d

        if conn is not None:
            return _get(conn)
        with self.get_connection() as c:
            return _get(c)

    def get_cmdb_graph(
        self,
        root_ci_id: Optional[int] = None,
        max_depth: Optional[int] = None,
        conn: Optional[sqlite3.Connection] = None,
    ) -> Dict[str, Any]:
        """Extracts complete CMDB topology graph or reachable subgraph for visualization."""
        def _build_graph(c: sqlite3.Connection) -> Dict[str, Any]:
            cur = c.cursor()
            if root_ci_id is None:
                # Return entire graph
                cur.execute("""
                    SELECT ci.id, ci.external_id, ci.name, ci.ci_type, ci.environment, ci.ip_address,
                           ci.owner_group_id, g.name AS owner_group_name, ci.tier, ci.health_status,
                           ci.attributes
                    FROM cmdb_cis ci
                    LEFT JOIN groups g ON ci.owner_group_id = g.id
                    ORDER BY ci.tier ASC, ci.name ASC
                """)
                node_rows = cur.fetchall()

                cur.execute("""
                    SELECT id, parent_ci_id AS source, child_ci_id AS target, relationship_type, depth
                    FROM cmdb_relationships
                    ORDER BY depth ASC, id ASC
                """)
                edge_rows = cur.fetchall()
            else:
                resolved_root = self.resolve_ci_id(root_ci_id, conn=c)
                if not resolved_root:
                    return {"nodes": [], "edges": []}

                effective_depth = max_depth if max_depth is not None else 10

                # Recursive CTE traversing upstream and downstream up to effective_depth
                cur.execute(
                    """
                    WITH RECURSIVE downstream(ci_id, lvl) AS (
                        SELECT id, 0 FROM cmdb_cis WHERE id = ?
                        UNION
                        SELECT r.child_ci_id, d.lvl + 1
                        FROM cmdb_relationships r
                        JOIN downstream d ON r.parent_ci_id = d.ci_id
                        WHERE d.lvl < ?
                    ),
                    upstream(ci_id, lvl) AS (
                        SELECT id, 0 FROM cmdb_cis WHERE id = ?
                        UNION
                        SELECT r.parent_ci_id, u.lvl + 1
                        FROM cmdb_relationships r
                        JOIN upstream u ON r.child_ci_id = u.ci_id
                        WHERE u.lvl < ?
                    ),
                    reachable AS (
                        SELECT ci_id, lvl FROM downstream
                        UNION
                        SELECT ci_id, lvl FROM upstream
                    )
                    SELECT DISTINCT ci.id, ci.external_id, ci.name, ci.ci_type, ci.environment, ci.ip_address,
                           ci.owner_group_id, g.name AS owner_group_name, ci.tier, ci.health_status,
                           ci.attributes, MIN(rch.lvl) AS depth
                    FROM cmdb_cis ci
                    JOIN reachable rch ON ci.id = rch.ci_id
                    LEFT JOIN groups g ON ci.owner_group_id = g.id
                    GROUP BY ci.id
                    ORDER BY MIN(rch.lvl) ASC, ci.tier ASC
                    """,
                    (resolved_root, effective_depth, resolved_root, effective_depth),
                )
                node_rows = cur.fetchall()

                node_ids = [r["id"] for r in node_rows]
                if not node_ids:
                    return {"nodes": [], "edges": []}

                placeholders = ",".join("?" for _ in node_ids)
                cur.execute(
                    f"""
                    SELECT id, parent_ci_id AS source, child_ci_id AS target, relationship_type, depth
                    FROM cmdb_relationships
                    WHERE parent_ci_id IN ({placeholders}) AND child_ci_id IN ({placeholders})
                    ORDER BY depth ASC, id ASC
                    """,
                    node_ids + node_ids,
                )
                edge_rows = cur.fetchall()

            nodes = []
            for r in node_rows:
                nd = dict(r)
                nd["attributes"] = _from_json_str(nd.get("attributes"))
                nodes.append(nd)

            edges = [dict(r) for r in edge_rows]
            return {"nodes": nodes, "edges": edges}

        if conn is not None:
            return _build_graph(conn)
        with self.get_connection() as c:
            return _build_graph(c)

    # =========================================================================
    # Task Management (CRUD / Upsert / Details / Listing)
    # =========================================================================

    def upsert_task(
        self,
        task_number: Optional[str] = None,
        external_id: Optional[str] = None,
        task_type: str = "incident",
        title: Optional[str] = None,
        description: str = "",
        priority: str = "P3",
        status: str = "new",
        caller_id: Optional[Union[int, str]] = None,
        assigned_to_id: Optional[Union[int, str]] = None,
        assignment_group_id: Optional[Union[int, str]] = None,
        cmdb_ci_id: Optional[Union[int, str]] = None,
        created_at: Optional[str] = None,
        updated_at: Optional[str] = None,
        resolved_at: Optional[str] = None,
        closed_at: Optional[str] = None,
        sla_due_at: Optional[str] = None,
        custom_fields: Optional[Union[Dict[str, Any], str]] = None,
        task_id: Optional[int] = None,
        conn: Optional[sqlite3.Connection] = None,
    ) -> int:
        """Upserts a task record with foreign key resolution and conflict handling."""
        now_iso = datetime.datetime.now(datetime.timezone.utc).isoformat()
        custom_str = _to_json_str(custom_fields)

        def _execute(c: sqlite3.Connection) -> int:
            cur = c.cursor()
            existing_id = None

            if task_id is not None:
                cur.execute("SELECT id FROM tasks WHERE id = ?", (task_id,))
                r = cur.fetchone()
                if r:
                    existing_id = r["id"]

            if existing_id is None and task_number:
                cur.execute("SELECT id FROM tasks WHERE task_number = ?", (task_number,))
                r = cur.fetchone()
                if r:
                    existing_id = r["id"]

            if existing_id is None and external_id:
                cur.execute("SELECT id FROM tasks WHERE external_id = ?", (external_id,))
                r = cur.fetchone()
                if r:
                    existing_id = r["id"]

            # Resolve references
            res_caller = self.resolve_user_id(caller_id, conn=c) if caller_id is not None else None
            res_assigned = (
                self.resolve_user_id(assigned_to_id, conn=c)
                if assigned_to_id is not None
                else None
            )
            res_group = (
                self.resolve_group_id(assignment_group_id, conn=c)
                if assignment_group_id is not None
                else None
            )
            res_ci = self.resolve_ci_id(cmdb_ci_id, conn=c) if cmdb_ci_id is not None else None

            # Determine timestamps for state transitions
            eff_updated = updated_at or now_iso
            eff_resolved = resolved_at
            eff_closed = closed_at

            if existing_id is not None:
                cur.execute("SELECT status, resolved_at, closed_at FROM tasks WHERE id = ?", (existing_id,))
                prev = cur.fetchone()
                if status == "resolved" and not eff_resolved:
                    eff_resolved = prev["resolved_at"] or now_iso
                elif status == "closed" and not eff_closed:
                    eff_closed = prev["closed_at"] or now_iso

                cur.execute(
                    """
                    UPDATE tasks
                    SET task_number = COALESCE(?, task_number),
                        external_id = COALESCE(?, external_id),
                        task_type = COALESCE(?, task_type),
                        title = COALESCE(?, title),
                        description = COALESCE(?, description),
                        priority = COALESCE(?, priority),
                        status = COALESCE(?, status),
                        caller_id = COALESCE(?, caller_id),
                        assigned_to_id = COALESCE(?, assigned_to_id),
                        assignment_group_id = COALESCE(?, assignment_group_id),
                        cmdb_ci_id = COALESCE(?, cmdb_ci_id),
                        updated_at = ?,
                        resolved_at = COALESCE(?, resolved_at),
                        closed_at = COALESCE(?, closed_at),
                        sla_due_at = COALESCE(?, sla_due_at),
                        custom_fields = COALESCE(?, custom_fields)
                    WHERE id = ?
                    """,
                    (
                        task_number,
                        external_id,
                        task_type,
                        title,
                        description,
                        priority,
                        status,
                        res_caller,
                        res_assigned,
                        res_group,
                        res_ci,
                        eff_updated,
                        eff_resolved,
                        eff_closed,
                        sla_due_at,
                        custom_str,
                        existing_id,
                    ),
                )
                return existing_id

            # Insert new record
            eff_task_num = task_number or self.generate_task_number(task_type, conn=c)
            eff_title = title or f"{task_type.capitalize()} {eff_task_num}"
            eff_created = created_at or now_iso
            if status == "resolved" and not eff_resolved:
                eff_resolved = now_iso
            elif status == "closed" and not eff_closed:
                eff_closed = now_iso

            cur.execute(
                """
                INSERT INTO tasks (
                    task_number, external_id, task_type, title, description, priority, status,
                    caller_id, assigned_to_id, assignment_group_id, cmdb_ci_id,
                    created_at, updated_at, resolved_at, closed_at, sla_due_at, custom_fields
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    eff_task_num,
                    external_id,
                    task_type,
                    eff_title,
                    description,
                    priority,
                    status,
                    res_caller,
                    res_assigned,
                    res_group,
                    res_ci,
                    eff_created,
                    eff_updated,
                    eff_resolved,
                    eff_closed,
                    sla_due_at,
                    custom_str,
                ),
            )
            return cur.lastrowid

        if conn is not None:
            return _execute(conn)
        with self.get_connection() as c:
            return _execute(c)

    def add_journal_entry(
        self,
        task_id: int,
        author_id: Optional[Union[int, str]],
        entry_type: str,
        body: str,
        created_at: Optional[str] = None,
        conn: Optional[sqlite3.Connection] = None,
    ) -> int:
        """Adds a chronological journal entry/work note to a task audit trail."""
        now_iso = datetime.datetime.now(datetime.timezone.utc).isoformat()
        entry_time = created_at or now_iso

        def _execute(c: sqlite3.Connection) -> int:
            cur = c.cursor()
            # Verify task exists
            cur.execute("SELECT id FROM tasks WHERE id = ?", (task_id,))
            if not cur.fetchone():
                raise ValueError(f"Task with ID {task_id} does not exist.")

            res_author = self.resolve_user_id(author_id, conn=c) if author_id is not None else None

            cur.execute(
                """
                INSERT INTO journal_entries (task_id, author_id, entry_type, body, created_at)
                VALUES (?, ?, ?, ?, ?)
                """,
                (task_id, res_author, entry_type, body, entry_time),
            )
            entry_id = cur.lastrowid

            # Update task updated_at
            cur.execute("UPDATE tasks SET updated_at = ? WHERE id = ?", (entry_time, task_id))
            return entry_id

        if conn is not None:
            return _execute(conn)
        with self.get_connection() as c:
            return _execute(c)

    def add_sla_instance(
        self,
        task_id: int,
        stage: str = "in_progress",
        percentage: float = 0.0,
        target_seconds: int = 14400,
        breached: int = 0,
        pause_duration: int = 0,
        sla_id: Optional[int] = None,
        conn: Optional[sqlite3.Connection] = None,
    ) -> int:
        """Records or updates an SLA tracking instance on a task."""
        def _execute(c: sqlite3.Connection) -> int:
            cur = c.cursor()
            cur.execute("SELECT id FROM tasks WHERE id = ?", (task_id,))
            if not cur.fetchone():
                raise ValueError(f"Task with ID {task_id} does not exist.")

            if sla_id is not None:
                cur.execute(
                    """
                    UPDATE sla_instances
                    SET stage = ?, percentage = ?, target_seconds = ?, breached = ?, pause_duration = ?
                    WHERE id = ? AND task_id = ?
                    """,
                    (stage, percentage, target_seconds, breached, pause_duration, sla_id, task_id),
                )
                return sla_id

            cur.execute(
                """
                INSERT INTO sla_instances (task_id, stage, percentage, target_seconds, breached, pause_duration)
                VALUES (?, ?, ?, ?, ?, ?)
                """,
                (task_id, stage, percentage, target_seconds, breached, pause_duration),
            )
            return cur.lastrowid

        if conn is not None:
            return _execute(conn)
        with self.get_connection() as c:
            return _execute(c)

    def get_task_detailed(
        self, task_id_or_number: Union[int, str], conn: Optional[sqlite3.Connection] = None
    ) -> Optional[Dict[str, Any]]:
        """Returns task dict with fully joined caller object, assigned user object, assigned group object,
        affected CI object with parent & child dependencies, array of journal entries in chronological order,
        and SLA tracking instances.
        """
        def _fetch(c: sqlite3.Connection) -> Optional[Dict[str, Any]]:
            cur = c.cursor()

            # Find task
            task_row = None
            if isinstance(task_id_or_number, int) or (
                isinstance(task_id_or_number, str) and task_id_or_number.isdigit()
            ):
                cur.execute("SELECT * FROM tasks WHERE id = ?", (int(task_id_or_number),))
                task_row = cur.fetchone()

            if not task_row:
                cur.execute("SELECT * FROM tasks WHERE task_number = ?", (str(task_id_or_number),))
                task_row = cur.fetchone()

            if not task_row:
                cur.execute("SELECT * FROM tasks WHERE external_id = ?", (str(task_id_or_number),))
                task_row = cur.fetchone()

            if not task_row:
                return None

            task_dict = dict(task_row)
            task_dict["custom_fields"] = _from_json_str(task_dict.get("custom_fields"))
            t_id = task_dict["id"]

            # Caller object
            if task_dict.get("caller_id"):
                cur.execute("SELECT * FROM users WHERE id = ?", (task_dict["caller_id"],))
                u = cur.fetchone()
                if u:
                    c_dict = dict(u)
                    c_dict["metadata"] = _from_json_str(c_dict.get("metadata"))
                    task_dict["caller"] = c_dict
                else:
                    task_dict["caller"] = None
            else:
                task_dict["caller"] = None

            # Assigned user object
            if task_dict.get("assigned_to_id"):
                cur.execute("SELECT * FROM users WHERE id = ?", (task_dict["assigned_to_id"],))
                u = cur.fetchone()
                if u:
                    a_dict = dict(u)
                    a_dict["metadata"] = _from_json_str(a_dict.get("metadata"))
                    task_dict["assigned_to"] = a_dict
                else:
                    task_dict["assigned_to"] = None
            else:
                task_dict["assigned_to"] = None

            # Assignment group object
            if task_dict.get("assignment_group_id"):
                cur.execute(
                    """
                    SELECT g.*, u.full_name AS manager_name, u.username AS manager_username
                    FROM groups g
                    LEFT JOIN users u ON g.manager_id = u.id
                    WHERE g.id = ?
                    """,
                    (task_dict["assignment_group_id"],),
                )
                g = cur.fetchone()
                if g:
                    g_dict = dict(g)
                    g_dict["metadata"] = _from_json_str(g_dict.get("metadata"))
                    task_dict["assignment_group"] = g_dict
                else:
                    task_dict["assignment_group"] = None
            else:
                task_dict["assignment_group"] = None

            # Affected CI object with parent & child dependencies
            if task_dict.get("cmdb_ci_id"):
                task_dict["cmdb_ci"] = self.get_ci(task_dict["cmdb_ci_id"], conn=c)
            else:
                task_dict["cmdb_ci"] = None

            # Journal entries in chronological order
            cur.execute(
                """
                SELECT je.id, je.task_id, je.author_id, je.entry_type, je.body, je.created_at,
                       u.username AS author_username, u.full_name AS author_name, u.role AS author_role
                FROM journal_entries je
                LEFT JOIN users u ON je.author_id = u.id
                WHERE je.task_id = ?
                ORDER BY je.created_at ASC, je.id ASC
                """,
                (t_id,),
            )
            entries = []
            for r in cur.fetchall():
                ed = dict(r)
                author_obj = None
                if ed.get("author_id"):
                    author_obj = {
                        "id": ed["author_id"],
                        "username": ed.get("author_username"),
                        "full_name": ed.get("author_name"),
                        "role": ed.get("author_role"),
                    }
                ed["author"] = author_obj
                entries.append(ed)
            task_dict["journal_entries"] = entries

            # SLA instances
            cur.execute(
                """
                SELECT id, task_id, stage, percentage, target_seconds, breached, pause_duration
                FROM sla_instances
                WHERE task_id = ?
                ORDER BY id ASC
                """,
                (t_id,),
            )
            sla_list = []
            for r in cur.fetchall():
                sd = dict(r)
                sd["breached"] = bool(sd["breached"])
                sla_list.append(sd)
            task_dict["sla_instances"] = sla_list

            return task_dict

        if conn is not None:
            return _fetch(conn)
        with self.get_connection() as c:
            return _fetch(c)

    def list_tasks(
        self,
        filters: Optional[Dict[str, Any]] = None,
        pagination: Optional[Dict[str, int]] = None,
        conn: Optional[sqlite3.Connection] = None,
    ) -> List[Dict[str, Any]]:
        """Lists tasks with resolved caller and group names, parameterized search, and pagination."""
        filters = filters or {}
        pagination = pagination or {}

        limit = max(1, min(pagination.get("limit", 50), 1000))
        offset = max(0, pagination.get("offset", 0))

        # Whitelist sort column to strictly eliminate any SQL injection vector
        sort_by = pagination.get("sort_by", "created_at")
        allowed_sorts = {
            "id": "t.id",
            "task_number": "t.task_number",
            "title": "t.title",
            "task_type": "t.task_type",
            "priority": "t.priority",
            "status": "t.status",
            "created_at": "t.created_at",
            "updated_at": "t.updated_at",
            "resolved_at": "t.resolved_at",
            "sla_due_at": "t.sla_due_at",
        }
        sort_col = allowed_sorts.get(sort_by, "t.created_at")
        sort_dir = "ASC" if str(pagination.get("sort_dir", "DESC")).upper() == "ASC" else "DESC"

        where_clauses: List[str] = []
        params: List[Any] = []

        if filters.get("status"):
            val = filters["status"]
            if isinstance(val, (list, set, tuple)):
                placeholders = ",".join("?" for _ in val)
                where_clauses.append(f"t.status IN ({placeholders})")
                params.extend(val)
            else:
                where_clauses.append("t.status = ?")
                params.append(str(val))

        if filters.get("priority"):
            val = filters["priority"]
            if isinstance(val, (list, set, tuple)):
                placeholders = ",".join("?" for _ in val)
                where_clauses.append(f"t.priority IN ({placeholders})")
                params.extend(val)
            else:
                where_clauses.append("t.priority = ?")
                params.append(str(val))

        if filters.get("task_type"):
            where_clauses.append("t.task_type = ?")
            params.append(str(filters["task_type"]))

        if filters.get("caller_id") is not None:
            where_clauses.append("t.caller_id = ?")
            params.append(filters["caller_id"])

        if filters.get("assigned_to_id") is not None:
            where_clauses.append("t.assigned_to_id = ?")
            params.append(filters["assigned_to_id"])

        if filters.get("assignment_group_id") is not None:
            where_clauses.append("t.assignment_group_id = ?")
            params.append(filters["assignment_group_id"])

        if filters.get("cmdb_ci_id") is not None:
            where_clauses.append("t.cmdb_ci_id = ?")
            params.append(filters["cmdb_ci_id"])

        search_query = filters.get("query") or filters.get("search")
        if search_query:
            term = f"%{search_query}%"
            where_clauses.append("(t.title LIKE ? OR t.description LIKE ? OR t.task_number LIKE ?)")
            params.extend([term, term, term])

        if filters.get("created_after"):
            where_clauses.append("t.created_at >= ?")
            params.append(str(filters["created_after"]))

        if filters.get("created_before"):
            where_clauses.append("t.created_at <= ?")
            params.append(str(filters["created_before"]))

        where_sql = ("WHERE " + " AND ".join(where_clauses)) if where_clauses else ""

        sql = f"""
            SELECT t.id, t.task_number, t.external_id, t.task_type, t.title, t.description,
                   t.priority, t.status, t.caller_id, t.assigned_to_id, t.assignment_group_id,
                   t.cmdb_ci_id, t.created_at, t.updated_at, t.resolved_at, t.closed_at,
                   t.sla_due_at, t.custom_fields,
                   u_caller.full_name AS caller_name, u_caller.username AS caller_username, u_caller.email AS caller_email,
                   u_assignee.full_name AS assigned_to_name, u_assignee.username AS assigned_to_username,
                   g.name AS assignment_group_name,
                   ci.name AS cmdb_ci_name, ci.ci_type AS cmdb_ci_type, ci.health_status AS cmdb_ci_health
            FROM tasks t
            LEFT JOIN users u_caller ON t.caller_id = u_caller.id
            LEFT JOIN users u_assignee ON t.assigned_to_id = u_assignee.id
            LEFT JOIN groups g ON t.assignment_group_id = g.id
            LEFT JOIN cmdb_cis ci ON t.cmdb_ci_id = ci.id
            {where_sql}
            ORDER BY {sort_col} {sort_dir}
            LIMIT ? OFFSET ?
        """
        params.extend([limit, offset])

        def _query(c: sqlite3.Connection) -> List[Dict[str, Any]]:
            cur = c.cursor()
            cur.execute(sql, params)
            rows = cur.fetchall()
            results = []
            for r in rows:
                d = dict(r)
                d["custom_fields"] = _from_json_str(d.get("custom_fields"))
                results.append(d)
            return results

        if conn is not None:
            return _query(conn)
        with self.get_connection() as c:
            return _query(c)

    def count_tasks(
        self, filters: Optional[Dict[str, Any]] = None, conn: Optional[sqlite3.Connection] = None
    ) -> int:
        """Returns count of tasks matching filters."""
        filters = filters or {}
        where_clauses: List[str] = []
        params: List[Any] = []

        if filters.get("status"):
            val = filters["status"]
            if isinstance(val, (list, set, tuple)):
                placeholders = ",".join("?" for _ in val)
                where_clauses.append(f"status IN ({placeholders})")
                params.extend(val)
            else:
                where_clauses.append("status = ?")
                params.append(str(val))

        if filters.get("priority"):
            val = filters["priority"]
            if isinstance(val, (list, set, tuple)):
                placeholders = ",".join("?" for _ in val)
                where_clauses.append(f"priority IN ({placeholders})")
                params.extend(val)
            else:
                where_clauses.append("priority = ?")
                params.append(str(val))

        if filters.get("task_type"):
            where_clauses.append("task_type = ?")
            params.append(str(filters["task_type"]))

        where_sql = ("WHERE " + " AND ".join(where_clauses)) if where_clauses else ""
        sql = f"SELECT COUNT(*) AS total FROM tasks {where_sql}"

        def _execute(c: sqlite3.Connection) -> int:
            cur = c.cursor()
            cur.execute(sql, params)
            return cur.fetchone()["total"]

        if conn is not None:
            return _execute(conn)
        with self.get_connection() as c:
            return _execute(c)

    # =========================================================================
    # Operational Stats & KPI Aggregations
    # =========================================================================

    def get_operational_stats(
        self, conn: Optional[sqlite3.Connection] = None
    ) -> Dict[str, Any]:
        """Calculates enterprise ITSM operational stats and CMDB health metrics."""
        def _calc(c: sqlite3.Connection) -> Dict[str, Any]:
            cur = c.cursor()

            # Task counts
            cur.execute("SELECT COUNT(*) AS total FROM tasks")
            total_tasks = cur.fetchone()["total"]

            cur.execute("SELECT COUNT(*) AS total FROM tasks WHERE status IN ('new', 'in_progress', 'on_hold')")
            total_open = cur.fetchone()["total"]

            cur.execute("SELECT COUNT(*) AS total FROM tasks WHERE status = 'resolved'")
            total_resolved = cur.fetchone()["total"]

            cur.execute("SELECT COUNT(*) AS total FROM tasks WHERE status = 'closed'")
            total_closed = cur.fetchone()["total"]

            cur.execute("SELECT COUNT(*) AS total FROM tasks WHERE priority = 'P1'")
            p1_critical_count = cur.fetchone()["total"]

            cur.execute(
                "SELECT COUNT(*) AS total FROM tasks WHERE priority = 'P1' AND status IN ('new', 'in_progress', 'on_hold')"
            )
            open_p1_count = cur.fetchone()["total"]

            # Breakdowns
            cur.execute("SELECT status, COUNT(*) AS cnt FROM tasks GROUP BY status")
            by_status = {r["status"]: r["cnt"] for r in cur.fetchall()}

            cur.execute("SELECT priority, COUNT(*) AS cnt FROM tasks GROUP BY priority")
            by_priority = {r["priority"]: r["cnt"] for r in cur.fetchall()}

            cur.execute("SELECT task_type, COUNT(*) AS cnt FROM tasks GROUP BY task_type")
            by_type = {r["task_type"]: r["cnt"] for r in cur.fetchall()}

            # CI Health Breakdown
            cur.execute("SELECT health_status, COUNT(*) AS cnt FROM cmdb_cis GROUP BY health_status")
            ci_health_breakdown = {r["health_status"]: r["cnt"] for r in cur.fetchall()}

            # Entity Counts
            cur.execute("SELECT COUNT(*) AS total FROM users")
            total_users = cur.fetchone()["total"]

            cur.execute("SELECT COUNT(*) AS total FROM groups")
            total_groups = cur.fetchone()["total"]

            cur.execute("SELECT COUNT(*) AS total FROM cmdb_cis")
            total_cis = cur.fetchone()["total"]

            cur.execute("SELECT COUNT(*) AS total FROM cmdb_relationships")
            total_relationships = cur.fetchone()["total"]

            cur.execute("SELECT COUNT(*) AS total FROM journal_entries")
            total_journal_entries = cur.fetchone()["total"]

            # SLA Stats
            cur.execute("SELECT COUNT(*) AS total FROM sla_instances")
            total_slas = cur.fetchone()["total"]

            cur.execute("SELECT COUNT(*) AS total FROM sla_instances WHERE breached = 1")
            breached_slas = cur.fetchone()["total"]

            sla_compliance_rate = (
                round(((total_slas - breached_slas) / total_slas) * 100.0, 2)
                if total_slas > 0
                else 100.0
            )

            # MTTR Calculation in Python to handle any timestamp variance with zero error
            cur.execute(
                """
                SELECT created_at, resolved_at
                FROM tasks
                WHERE resolved_at IS NOT NULL AND status IN ('resolved', 'closed')
                """
            )
            resolved_tasks = cur.fetchall()
            durations: List[float] = []
            for r in resolved_tasks:
                dt_c = _parse_iso_date(r["created_at"])
                dt_r = _parse_iso_date(r["resolved_at"])
                if dt_c and dt_r and dt_r >= dt_c:
                    diff_hours = (dt_r - dt_c).total_seconds() / 3600.0
                    durations.append(diff_hours)

            mttr_hours = round(sum(durations) / len(durations), 2) if durations else 0.0

            return {
                "total_tasks": total_tasks,
                "total_open": total_open,
                "total_resolved": total_resolved,
                "total_closed": total_closed,
                "p1_critical_count": p1_critical_count,
                "open_p1_count": open_p1_count,
                "mttr_hours": mttr_hours,
                "sla_compliance_rate": sla_compliance_rate,
                "sla_stats": {
                    "total": total_slas,
                    "breached": breached_slas,
                    "compliance_percentage": sla_compliance_rate,
                },
                "by_status": by_status,
                "by_priority": by_priority,
                "by_type": by_type,
                "ci_health_breakdown": ci_health_breakdown,
                "total_users": total_users,
                "total_groups": total_groups,
                "total_cis": total_cis,
                "total_relationships": total_relationships,
                "total_journal_entries": total_journal_entries,
            }

        if conn is not None:
            return _calc(conn)
        with self.get_connection() as c:
            return _calc(c)

    # =========================================================================
    # Batch Insert / Upsert with Foreign Key Resolution & Conflict Handling
    # =========================================================================

    def batch_upsert_users(
        self, users: Sequence[Dict[str, Any]], conn: Optional[sqlite3.Connection] = None
    ) -> List[int]:
        """Atomically upserts a batch of users."""
        def _execute(c: sqlite3.Connection) -> List[int]:
            user_ids = []
            for u in users:
                uid = self.upsert_user(
                    external_id=u.get("external_id"),
                    username=u.get("username"),
                    email=u.get("email"),
                    full_name=u.get("full_name"),
                    department=u.get("department"),
                    role=u.get("role"),
                    metadata=u.get("metadata"),
                    created_at=u.get("created_at"),
                    user_id=u.get("id") or u.get("user_id"),
                    conn=c,
                )
                user_ids.append(uid)
            return user_ids

        if conn is not None:
            return _execute(conn)
        with self.get_connection() as c:
            return _execute(c)

    def batch_upsert_groups(
        self, groups: Sequence[Dict[str, Any]], conn: Optional[sqlite3.Connection] = None
    ) -> List[int]:
        """Atomically upserts a batch of groups with manager foreign key resolution."""
        def _execute(c: sqlite3.Connection) -> List[int]:
            group_ids = []
            for g in groups:
                gid = self.upsert_group(
                    external_id=g.get("external_id"),
                    name=g.get("name"),
                    description=g.get("description"),
                    manager_id=g.get("manager_id") or g.get("manager"),
                    email=g.get("email"),
                    metadata=g.get("metadata"),
                    group_id=g.get("id") or g.get("group_id"),
                    conn=c,
                )
                group_ids.append(gid)
            return group_ids

        if conn is not None:
            return _execute(conn)
        with self.get_connection() as c:
            return _execute(c)

    def batch_upsert_cis(
        self, cis: Sequence[Dict[str, Any]], conn: Optional[sqlite3.Connection] = None
    ) -> List[int]:
        """Atomically upserts a batch of Configuration Items with owner group resolution."""
        def _execute(c: sqlite3.Connection) -> List[int]:
            ci_ids = []
            for ci in cis:
                cid = self.upsert_ci(
                    external_id=ci.get("external_id"),
                    name=ci.get("name"),
                    ci_type=ci.get("ci_type"),
                    environment=ci.get("environment", "production"),
                    ip_address=ci.get("ip_address"),
                    owner_group_id=ci.get("owner_group_id") or ci.get("owner_group") or ci.get("owner_team"),
                    tier=ci.get("tier", 2),
                    health_status=ci.get("health_status", "healthy"),
                    attributes=ci.get("attributes") or ci.get("metadata"),
                    ci_id=ci.get("id") or ci.get("ci_id"),
                    conn=c,
                )
                ci_ids.append(cid)
            return ci_ids

        if conn is not None:
            return _execute(conn)
        with self.get_connection() as c:
            return _execute(c)

    def batch_upsert_tasks(
        self, tasks: Sequence[Dict[str, Any]], conn: Optional[sqlite3.Connection] = None
    ) -> List[int]:
        """Atomically upserts a batch of tasks, resolving foreign keys (caller, assigned_to,
        assignment_group, cmdb_ci) from string identifiers or integer IDs."""
        def _execute(c: sqlite3.Connection) -> List[int]:
            task_ids = []
            for t in tasks:
                tid = self.upsert_task(
                    task_number=t.get("task_number"),
                    external_id=t.get("external_id"),
                    task_type=t.get("task_type", "incident"),
                    title=t.get("title"),
                    description=t.get("description", ""),
                    priority=t.get("priority", "P3"),
                    status=t.get("status", "new"),
                    caller_id=t.get("caller_id") or t.get("caller"),
                    assigned_to_id=t.get("assigned_to_id") or t.get("assigned_to"),
                    assignment_group_id=t.get("assignment_group_id") or t.get("assignment_group") or t.get("assigned_team"),
                    cmdb_ci_id=t.get("cmdb_ci_id") or t.get("cmdb_ci") or t.get("ci_id") or t.get("affected_ci"),
                    created_at=t.get("created_at"),
                    updated_at=t.get("updated_at"),
                    resolved_at=t.get("resolved_at"),
                    closed_at=t.get("closed_at"),
                    sla_due_at=t.get("sla_due_at"),
                    custom_fields=t.get("custom_fields"),
                    task_id=t.get("id") or t.get("task_id"),
                    conn=c,
                )
                task_ids.append(tid)
            return task_ids

        if conn is not None:
            return _execute(conn)
        with self.get_connection() as c:
            return _execute(c)

    # =========================================================================
    # Enterprise Seed Data Generator
    # =========================================================================

    def seed_relational_data(self) -> Dict[str, int]:
        """Seeds realistic, production-grade enterprise dataset across all tables."""
        with self.get_connection() as conn:
            # 1. Users
            users_data = [
                {
                    "external_id": "USR-ADM-001",
                    "username": "admin",
                    "email": "alex.mercer@opennow.io",
                    "full_name": "Alex Mercer",
                    "department": "IT Operations",
                    "role": "admin",
                    "metadata": {"title": "Principal Systems Administrator", "location": "US-West"},
                },
                {
                    "external_id": "USR-INF-002",
                    "username": "jchen",
                    "email": "jessica.chen@opennow.io",
                    "full_name": "Dr. Jessica Chen",
                    "department": "Infrastructure Engineering",
                    "role": "manager",
                    "metadata": {"title": "VP of Infrastructure & Platform", "location": "US-East"},
                },
                {
                    "external_id": "USR-SRE-003",
                    "username": "mkowalski",
                    "email": "marcus.kowalski@opennow.io",
                    "full_name": "Marcus Kowalski",
                    "department": "Cloud Infrastructure",
                    "role": "agent",
                    "metadata": {"title": "Lead Site Reliability Engineer", "on_call": True},
                },
                {
                    "external_id": "USR-DBA-004",
                    "username": "sgupta",
                    "email": "sunita.gupta@opennow.io",
                    "full_name": "Sunita Gupta",
                    "department": "Database Administration",
                    "role": "agent",
                    "metadata": {"title": "Senior Database Architect", "certifications": ["PostgreSQL Expert", "AWS DBA"]},
                },
                {
                    "external_id": "USR-SEC-005",
                    "username": "dross",
                    "email": "david.ross@opennow.io",
                    "full_name": "David Ross",
                    "department": "Cybersecurity",
                    "role": "agent",
                    "metadata": {"title": "SecOps Incident Commander", "clearance": "Level 3"},
                },
                {
                    "external_id": "USR-APP-006",
                    "username": "erodriguez",
                    "email": "elena.rodriguez@opennow.io",
                    "full_name": "Elena Rodriguez",
                    "department": "Application Engineering",
                    "role": "agent",
                    "metadata": {"title": "Lead Microservices Architect", "focus": "Payment Services"},
                },
                {
                    "external_id": "USR-HLP-007",
                    "username": "sbrown",
                    "email": "sarah.brown@opennow.io",
                    "full_name": "Sarah Brown",
                    "department": "Global Service Desk",
                    "role": "agent",
                    "metadata": {"title": "Tier 2 Support Specialist", "shift": "EMEA Day"},
                },
                {
                    "external_id": "USR-VIP-008",
                    "username": "twilson",
                    "email": "thomas.wilson@opennow.io",
                    "full_name": "Thomas Wilson",
                    "department": "Finance & Accounting",
                    "role": "end_user",
                    "metadata": {"title": "VP of Global Treasury", "vip": True},
                },
                {
                    "external_id": "USR-USR-009",
                    "username": "rpatel",
                    "email": "rohan.patel@opennow.io",
                    "full_name": "Rohan Patel",
                    "department": "Digital Banking",
                    "role": "end_user",
                    "metadata": {"title": "Senior Product Manager", "vip": False},
                },
            ]
            user_ids = self.batch_upsert_users(users_data, conn=conn)

            # 2. Groups
            groups_data = [
                {
                    "external_id": "GRP-GSD",
                    "name": "Global Service Desk",
                    "description": "24/7 Frontline IT Support and Incident Intake",
                    "manager": "sbrown",
                    "email": "servicedesk@opennow.io",
                    "metadata": {"tier": "Tier 1/2", "sla_target_minutes": 15},
                },
                {
                    "external_id": "GRP-CLOUD",
                    "name": "Cloud Infrastructure",
                    "description": "AWS/K8s Cloud Platform, SRE, and Network Engineering",
                    "manager": "mkowalski",
                    "email": "cloud-infra@opennow.io",
                    "metadata": {"tier": "Tier 3", "pagerduty_service": "cloud-sre"},
                },
                {
                    "external_id": "GRP-DBA",
                    "name": "Database Administration",
                    "description": "Enterprise PostgreSQL, Redis, and Data Platform Operations",
                    "manager": "sgupta",
                    "email": "dba-team@opennow.io",
                    "metadata": {"tier": "Tier 3", "databases": ["PostgreSQL", "Redis", "Elasticsearch"]},
                },
                {
                    "external_id": "GRP-SECOPS",
                    "name": "Cybersecurity Incident Response",
                    "description": "Security Operations Center (SOC) and Vulnerability Management",
                    "manager": "dross",
                    "email": "soc@opennow.io",
                    "metadata": {"tier": "Tier 3", "priority_handling": "immediate"},
                },
                {
                    "external_id": "GRP-APPENG",
                    "name": "Application Engineering",
                    "description": "Core Payment, Authentication, and Customer APIs",
                    "manager": "erodriguez",
                    "email": "app-eng@opennow.io",
                    "metadata": {"tier": "Tier 3", "repos": ["payment-gw", "auth-service"]},
                },
            ]
            group_ids = self.batch_upsert_groups(groups_data, conn=conn)

            # Group memberships
            memberships = [
                ("Global Service Desk", "sbrown", "manager"),
                ("Global Service Desk", "admin", "lead"),
                ("Cloud Infrastructure", "mkowalski", "manager"),
                ("Cloud Infrastructure", "jchen", "sponsor"),
                ("Database Administration", "sgupta", "manager"),
                ("Cybersecurity Incident Response", "dross", "manager"),
                ("Application Engineering", "erodriguez", "manager"),
            ]
            for g_ref, u_ref, m_role in memberships:
                gid = self.resolve_group_id(g_ref, conn=conn)
                uid = self.resolve_user_id(u_ref, conn=conn)
                if gid and uid:
                    self.add_group_member(gid, uid, role=m_role, conn=conn)

            # 3. CMDB CIs
            cis_data = [
                {
                    "external_id": "CI-NET-01",
                    "name": "PRD-EDGE-ALB01",
                    "ci_type": "load_balancer",
                    "environment": "production",
                    "ip_address": "52.95.12.18",
                    "owner_group": "Cloud Infrastructure",
                    "tier": 1,
                    "health_status": "healthy",
                    "attributes": {"provider": "AWS ALB", "region": "us-east-1", "ssl_status": "valid"},
                },
                {
                    "external_id": "CI-K8S-01",
                    "name": "PRD-K8S-INGRESS",
                    "ci_type": "load_balancer",
                    "environment": "production",
                    "ip_address": "10.0.1.10",
                    "owner_group": "Cloud Infrastructure",
                    "tier": 1,
                    "health_status": "healthy",
                    "attributes": {"ingress_class": "nginx", "k8s_version": "v1.29.3"},
                },
                {
                    "external_id": "CI-SVC-01",
                    "name": "PRD-AUTH-SVC",
                    "ci_type": "microservice",
                    "environment": "production",
                    "ip_address": "10.0.2.14",
                    "owner_group": "Application Engineering",
                    "tier": 1,
                    "health_status": "healthy",
                    "attributes": {"framework": "FastAPI", "port": 8000, "protocol": "OIDC/OAuth2"},
                },
                {
                    "external_id": "CI-SVC-02",
                    "name": "PRD-PAYMENT-SVC",
                    "ci_type": "microservice",
                    "environment": "production",
                    "ip_address": "10.0.2.22",
                    "owner_group": "Application Engineering",
                    "tier": 1,
                    "health_status": "degraded",
                    "attributes": {"framework": "Go / gRPC", "port": 9090, "circuit_breaker": "half-open"},
                },
                {
                    "external_id": "CI-SVC-03",
                    "name": "PRD-ORDER-SVC",
                    "ci_type": "microservice",
                    "environment": "production",
                    "ip_address": "10.0.2.35",
                    "owner_group": "Application Engineering",
                    "tier": 2,
                    "health_status": "healthy",
                    "attributes": {"framework": "Node.js", "port": 3000},
                },
                {
                    "external_id": "CI-DB-01",
                    "name": "PRD-PGSQL-PRIMARY",
                    "ci_type": "database",
                    "environment": "production",
                    "ip_address": "10.0.3.50",
                    "owner_group": "Database Administration",
                    "tier": 1,
                    "health_status": "critical",
                    "attributes": {"engine": "PostgreSQL 16.2", "cluster": "db-aurora-cluster", "connections": 1420},
                },
                {
                    "external_id": "CI-DB-02",
                    "name": "PRD-PGSQL-STANDBY",
                    "ci_type": "database",
                    "environment": "production",
                    "ip_address": "10.0.3.51",
                    "owner_group": "Database Administration",
                    "tier": 1,
                    "health_status": "degraded",
                    "attributes": {"engine": "PostgreSQL 16.2", "role": "hot_standby", "replication_lag_sec": 48},
                },
                {
                    "external_id": "CI-DB-03",
                    "name": "PRD-REDIS-CLUSTER",
                    "ci_type": "database",
                    "environment": "production",
                    "ip_address": "10.0.3.70",
                    "owner_group": "Database Administration",
                    "tier": 2,
                    "health_status": "healthy",
                    "attributes": {"engine": "Redis Enterprise 7.2", "shards": 6, "memory_used_gb": 42.5},
                },
                {
                    "external_id": "CI-SRV-01",
                    "name": "PRD-K8S-CLUSTER-01",
                    "ci_type": "server",
                    "environment": "production",
                    "ip_address": "10.0.4.100",
                    "owner_group": "Cloud Infrastructure",
                    "tier": 1,
                    "health_status": "healthy",
                    "attributes": {"cloud": "AWS EKS", "nodes_count": 32, "instance_type": "m6i.4xlarge"},
                },
                {
                    "external_id": "CI-CLOUD-01",
                    "name": "PRD-VPC-CORE-01",
                    "ci_type": "cloud_service",
                    "environment": "production",
                    "ip_address": "10.0.0.0/16",
                    "owner_group": "Cloud Infrastructure",
                    "tier": 1,
                    "health_status": "healthy",
                    "attributes": {"cloud": "AWS", "cidr": "10.0.0.0/16", "azs": ["us-east-1a", "us-east-1b", "us-east-1c"]},
                },
                {
                    "external_id": "CI-STOR-01",
                    "name": "PRD-SAN-STORAGE-01",
                    "ci_type": "storage",
                    "environment": "production",
                    "ip_address": "10.0.5.10",
                    "owner_group": "Cloud Infrastructure",
                    "tier": 1,
                    "health_status": "healthy",
                    "attributes": {"type": "NVMe-oF Flash LUN", "capacity_tb": 120, "provisioned_iops": 60000},
                },
            ]
            ci_ids = self.batch_upsert_cis(cis_data, conn=conn)

            # 4. CMDB Topology Relationships
            rel_definitions = [
                ("PRD-EDGE-ALB01", "PRD-K8S-INGRESS", "connects_to", 1),
                ("PRD-K8S-INGRESS", "PRD-AUTH-SVC", "routes_traffic_to", 2),
                ("PRD-K8S-INGRESS", "PRD-PAYMENT-SVC", "routes_traffic_to", 2),
                ("PRD-K8S-INGRESS", "PRD-ORDER-SVC", "routes_traffic_to", 2),
                ("PRD-AUTH-SVC", "PRD-PGSQL-PRIMARY", "depends_on", 3),
                ("PRD-PAYMENT-SVC", "PRD-PGSQL-PRIMARY", "depends_on", 3),
                ("PRD-PAYMENT-SVC", "PRD-REDIS-CLUSTER", "depends_on", 3),
                ("PRD-ORDER-SVC", "PRD-PGSQL-PRIMARY", "depends_on", 3),
                ("PRD-PGSQL-PRIMARY", "PRD-PGSQL-STANDBY", "replicates_to", 4),
                ("PRD-PGSQL-PRIMARY", "PRD-SAN-STORAGE-01", "hosted_on", 4),
                ("PRD-AUTH-SVC", "PRD-K8S-CLUSTER-01", "runs_on", 3),
                ("PRD-PAYMENT-SVC", "PRD-K8S-CLUSTER-01", "runs_on", 3),
                ("PRD-K8S-CLUSTER-01", "PRD-VPC-CORE-01", "hosted_in", 4),
            ]
            rel_count = 0
            for parent_name, child_name, rel_type, depth in rel_definitions:
                p_id = self.resolve_ci_id(parent_name, conn=conn)
                c_id = self.resolve_ci_id(child_name, conn=conn)
                if p_id and c_id:
                    self.add_ci_relationship(p_id, c_id, rel_type, depth, conn=conn)
                    rel_count += 1

            # 5. Tasks (Enterprise ITSM)
            now = datetime.datetime.now(datetime.timezone.utc)
            t_1h_ago = (now - datetime.timedelta(hours=1)).isoformat()
            t_3h_ago = (now - datetime.timedelta(hours=3)).isoformat()
            t_5h_ago = (now - datetime.timedelta(hours=5)).isoformat()
            t_24h_ago = (now - datetime.timedelta(hours=24)).isoformat()
            t_48h_ago = (now - datetime.timedelta(hours=48)).isoformat()
            t_due_1h = (now + datetime.timedelta(hours=1)).isoformat()
            t_due_4h = (now + datetime.timedelta(hours=4)).isoformat()

            tasks_data = [
                {
                    "task_number": "INC0010001",
                    "external_id": "SN-INC-99120",
                    "task_type": "incident",
                    "title": "Production Database Failover Latency Spike & Deadlock Storm",
                    "description": "Multiple microservices reporting connection pool starvation and queries timing out on PRD-PGSQL-PRIMARY.",
                    "priority": "P1",
                    "status": "in_progress",
                    "caller": "rpatel",
                    "assigned_to": "sgupta",
                    "assignment_group": "Database Administration",
                    "cmdb_ci": "PRD-PGSQL-PRIMARY",
                    "created_at": t_1h_ago,
                    "updated_at": t_1h_ago,
                    "sla_due_at": t_due_1h,
                    "custom_fields": {"impact_assessment": "Core Banking Transactions Affected", "outage_duration_min": 35},
                },
                {
                    "task_number": "INC0010002",
                    "external_id": "SN-INC-99121",
                    "task_type": "incident",
                    "title": "Payment Gateway Microservice 504 Gateway Timeouts in US-East",
                    "description": "Upstream load balancer received elevated HTTP 504 responses from payment worker pods.",
                    "priority": "P2",
                    "status": "in_progress",
                    "caller": "twilson",
                    "assigned_to": "erodriguez",
                    "assignment_group": "Application Engineering",
                    "cmdb_ci": "PRD-PAYMENT-SVC",
                    "created_at": t_3h_ago,
                    "updated_at": t_3h_ago,
                    "sla_due_at": t_due_4h,
                    "custom_fields": {"business_unit": "Treasury", "estimated_revenue_risk_usd": 250000},
                },
                {
                    "task_number": "INC0010003",
                    "external_id": "SN-INC-98540",
                    "task_type": "incident",
                    "title": "Redis Cache Eviction Rate Anomaly on Order Session Keys",
                    "description": "High memory consumption triggered aggressive LRU evictions causing downstream latency.",
                    "priority": "P3",
                    "status": "resolved",
                    "caller": "erodriguez",
                    "assigned_to": "mkowalski",
                    "assignment_group": "Cloud Infrastructure",
                    "cmdb_ci": "PRD-REDIS-CLUSTER",
                    "created_at": t_5h_ago,
                    "updated_at": t_1h_ago,
                    "resolved_at": t_1h_ago,
                    "custom_fields": {"root_cause": "Unbounded cache TTL on temporary cart sessions", "fix_applied": "TTL capped to 1800s"},
                },
                {
                    "task_number": "INC0010004",
                    "external_id": "SN-INC-97210",
                    "task_type": "incident",
                    "title": "SSL Certificate Expiry Warning on External Edge Load Balancer",
                    "description": "Automated certbot monitor alerted wildcard certificate renewed with 3 days remaining.",
                    "priority": "P4",
                    "status": "closed",
                    "caller": "dross",
                    "assigned_to": "mkowalski",
                    "assignment_group": "Cloud Infrastructure",
                    "cmdb_ci": "PRD-EDGE-ALB01",
                    "created_at": t_48h_ago,
                    "updated_at": t_24h_ago,
                    "resolved_at": t_24h_ago,
                    "closed_at": t_24h_ago,
                    "custom_fields": {"resolution_code": "Resolved by Automated Certbot Renewal"},
                },
                {
                    "task_number": "CHG0020001",
                    "external_id": "SN-CHG-10420",
                    "task_type": "change",
                    "title": "Emergency Kernel Patching on Kubernetes Worker Nodes",
                    "description": "Apply CVE-2026-4412 Linux kernel security advisory mitigation with rolling node drains.",
                    "priority": "P2",
                    "status": "new",
                    "caller": "mkowalski",
                    "assigned_to": "mkowalski",
                    "assignment_group": "Cloud Infrastructure",
                    "cmdb_ci": "PRD-K8S-CLUSTER-01",
                    "created_at": t_3h_ago,
                    "updated_at": t_3h_ago,
                    "custom_fields": {"change_risk": "Moderate", "maintenance_window": "02:00 - 04:00 UTC", "cab_approved": True},
                },
                {
                    "task_number": "CHG0020002",
                    "external_id": "SN-CHG-10421",
                    "task_type": "change",
                    "title": "Zero-Downtime Schema Migration for PostgreSQL Core Banking Tables",
                    "description": "Add composite indexes on accounts(ledger_id, currency, status) with concurrent build.",
                    "priority": "P3",
                    "status": "in_progress",
                    "caller": "sgupta",
                    "assigned_to": "sgupta",
                    "assignment_group": "Database Administration",
                    "cmdb_ci": "PRD-PGSQL-PRIMARY",
                    "created_at": t_5h_ago,
                    "updated_at": t_1h_ago,
                    "custom_fields": {"change_risk": "Low", "rollback_plan": "DROP INDEX CONCURRENTLY"},
                },
                {
                    "task_number": "PRB0030001",
                    "external_id": "SN-PRB-00812",
                    "task_type": "problem",
                    "title": "Root Cause Investigation: High Concurrent Connection Exhaustion",
                    "description": "Recurring connection spikes in PostgreSQL primary when payment batch processing runs concurrently.",
                    "priority": "P1",
                    "status": "in_progress",
                    "caller": "jchen",
                    "assigned_to": "sgupta",
                    "assignment_group": "Database Administration",
                    "cmdb_ci": "PRD-PGSQL-PRIMARY",
                    "created_at": t_24h_ago,
                    "updated_at": t_1h_ago,
                    "custom_fields": {"known_error": True, "workaround": "PgBouncer pool ceiling increased to 2000"},
                },
                {
                    "task_number": "REQ0040001",
                    "external_id": "SN-REQ-05200",
                    "task_type": "request",
                    "title": "Provision Read-Only Analytical Replica Access for Finance Team",
                    "description": "Grant BI Tableau read-only replica credentials for quarterly reconciliations.",
                    "priority": "P3",
                    "status": "closed",
                    "caller": "twilson",
                    "assigned_to": "sgupta",
                    "assignment_group": "Database Administration",
                    "cmdb_ci": "PRD-PGSQL-STANDBY",
                    "created_at": t_48h_ago,
                    "updated_at": t_24h_ago,
                    "resolved_at": t_24h_ago,
                    "closed_at": t_24h_ago,
                    "custom_fields": {"requester_cost_center": "FIN-401", "role_granted": "readonly_analyst"},
                },
            ]
            task_ids = self.batch_upsert_tasks(tasks_data, conn=conn)

            # 6. Journal Entries (Audit Trail & Work Notes)
            journal_samples = [
                (
                    "INC0010001",
                    "rpatel",
                    "user_comment",
                    "End-users experiencing checkout timeouts and debit card processing delay on web portal.",
                    t_1h_ago,
                ),
                (
                    "INC0010001",
                    "admin",
                    "system_alert",
                    "Automated Alert: PRD-PGSQL-PRIMARY active connections reached 1420/1500 (94.6%). Deadlock rate > 12/sec.",
                    t_1h_ago,
                ),
                (
                    "INC0010001",
                    "sgupta",
                    "work_note",
                    "Investigating locks. Identified 4 queries from payment-worker blocked on foreign key checks. Initiating query terminations.",
                    t_1h_ago,
                ),
                (
                    "INC0010002",
                    "twilson",
                    "user_comment",
                    "Finance department batch payment upload failed with 504 error.",
                    t_3h_ago,
                ),
                (
                    "INC0010002",
                    "erodriguez",
                    "work_note",
                    "Payment worker pods healthy, but database latency is blocking upstream gRPC handlers. Throttling non-critical traffic.",
                    t_3h_ago,
                ),
                (
                    "CHG0020001",
                    "mkowalski",
                    "work_note",
                    "CAB approval granted. Canary node patch completed in staging with zero pod eviction errors.",
                    t_3h_ago,
                ),
                (
                    "PRB0030001",
                    "jchen",
                    "work_note",
                    "Architecture review scheduled with Database and Core Banking engineering leads.",
                    t_24h_ago,
                ),
            ]
            journal_count = 0
            for t_num, auth_usr, e_type, body, created_ts in journal_samples:
                cur = conn.cursor()
                cur.execute("SELECT id FROM tasks WHERE task_number = ?", (t_num,))
                r = cur.fetchone()
                if r:
                    t_id = r["id"]
                    self.add_journal_entry(t_id, auth_usr, e_type, body, created_at=created_ts, conn=conn)
                    journal_count += 1

            # 7. SLA Instances
            sla_samples = [
                ("INC0010001", "in_progress", 65.0, 3600, 0, 0),
                ("INC0010002", "in_progress", 35.0, 14400, 0, 0),
                ("INC0010003", "completed", 80.0, 28800, 0, 0),
                ("INC0010004", "completed", 20.0, 86400, 0, 0),
                ("PRB0030001", "in_progress", 40.0, 172800, 0, 0),
                ("REQ0040001", "completed", 50.0, 86400, 0, 0),
            ]
            sla_count = 0
            for t_num, stage, pct, target, breached, pause_d in sla_samples:
                cur = conn.cursor()
                cur.execute("SELECT id FROM tasks WHERE task_number = ?", (t_num,))
                r = cur.fetchone()
                if r:
                    t_id = r["id"]
                    self.add_sla_instance(
                        t_id,
                        stage=stage,
                        percentage=pct,
                        target_seconds=target,
                        breached=breached,
                        pause_duration=pause_d,
                        conn=conn,
                    )
                    sla_count += 1

            return {
                "users": len(user_ids),
                "groups": len(group_ids),
                "cis": len(ci_ids),
                "relationships": rel_count,
                "tasks": len(task_ids),
                "journal_entries": journal_count,
                "sla_instances": sla_count,
            }

    # =========================================================================
    # Maintenance / Testing Utilities
    # =========================================================================

    def clear_all_data(self) -> None:
        """Truncates all tables in relational order. Used in clean test cycles."""
        with self.get_connection() as conn:
            cur = conn.cursor()
            cur.execute("DELETE FROM journal_entries;")
            cur.execute("DELETE FROM sla_instances;")
            cur.execute("DELETE FROM tasks;")
            cur.execute("DELETE FROM cmdb_relationships;")
            cur.execute("DELETE FROM cmdb_cis;")
            cur.execute("DELETE FROM group_members;")
            cur.execute("DELETE FROM groups;")
            cur.execute("DELETE FROM users;")


# Default global instance
relational_db = RelationalDatabase()
RelationalDatabaseManager = RelationalDatabase


# =============================================================================
# Comprehensive Unit Tests Suite
# =============================================================================

class TestRelationalDatabase(unittest.TestCase):
    """Exhaustive test suite verifying strict foreign keys, transactions,
    JSON attributes, CMDB graph extraction, operational stats, and SQL injection defense."""

    def setUp(self):
        # Create an isolated in-memory relational database for each test
        self.db = RelationalDatabase(":memory:")

    def test_schema_and_pragmas(self):
        """Verify WAL mode compatibility, strict foreign keys enabled, and table schemas."""
        with self.db.get_connection() as conn:
            cur = conn.cursor()
            cur.execute("PRAGMA foreign_keys;")
            fk_status = cur.fetchone()[0]
            self.assertEqual(fk_status, 1, "Foreign keys PRAGMA must be strictly ON (1)")

            # Check all 8 required tables exist
            cur.execute("SELECT name FROM sqlite_master WHERE type='table'")
            tables = {row["name"] for row in cur.fetchall()}
            required_tables = {
                "users",
                "groups",
                "group_members",
                "cmdb_cis",
                "cmdb_relationships",
                "tasks",
                "journal_entries",
                "sla_instances",
            }
            self.assertTrue(required_tables.issubset(tables), f"Missing tables: {required_tables - tables}")

    def test_foreign_key_constraints_enforced(self):
        """Verify SQLite strictly rejects invalid foreign keys."""
        with self.db.get_connection() as conn:
            cur = conn.cursor()
            # 1. Attempt to insert task pointing to nonexistent caller_id
            with self.assertRaises(sqlite3.IntegrityError):
                cur.execute(
                    """
                    INSERT INTO tasks (task_number, title, task_type, priority, status, caller_id, created_at, updated_at)
                    VALUES ('INC999999', 'Invalid Task', 'incident', 'P3', 'new', 99999, '2026-10-11T00:00:00Z', '2026-10-11T00:00:00Z')
                    """
                )

            # 2. Attempt to insert journal entry pointing to nonexistent task_id
            with self.assertRaises(sqlite3.IntegrityError):
                cur.execute(
                    """
                    INSERT INTO journal_entries (task_id, entry_type, body, created_at)
                    VALUES (99999, 'work_note', 'Ghost entry', '2026-10-11T00:00:00Z')
                    """
                )

    def test_cascading_deletes_and_set_null(self):
        """Verify ON DELETE CASCADE and ON DELETE SET NULL behaviors."""
        u_id = self.db.upsert_user(username="test_caller", email="caller@test.com")
        g_id = self.db.upsert_group(name="Test Group", manager_id=u_id)
        ci_id = self.db.upsert_ci(name="Test CI", ci_type="server")
        t_id = self.db.upsert_task(
            task_number="INC009999",
            title="Cascade Test",
            caller_id=u_id,
            assignment_group_id=g_id,
            cmdb_ci_id=ci_id,
        )
        j_id = self.db.add_journal_entry(t_id, u_id, "comment", "Testing cascade delete")
        sla_id = self.db.add_sla_instance(t_id, stage="in_progress")

        # 1. Delete task -> journal entries and sla instances must cascade delete
        with self.db.get_connection() as conn:
            cur = conn.cursor()
            cur.execute("DELETE FROM tasks WHERE id = ?", (t_id,))
            cur.execute("SELECT COUNT(*) AS cnt FROM journal_entries WHERE id = ?", (j_id,))
            self.assertEqual(cur.fetchone()["cnt"], 0)
            cur.execute("SELECT COUNT(*) AS cnt FROM sla_instances WHERE id = ?", (sla_id,))
            self.assertEqual(cur.fetchone()["cnt"], 0)

        # 2. Test user deletion -> groups.manager_id should become NULL
        with self.db.get_connection() as conn:
            cur = conn.cursor()
            cur.execute("DELETE FROM users WHERE id = ?", (u_id,))
            cur.execute("SELECT manager_id FROM groups WHERE id = ?", (g_id,))
            self.assertIsNone(cur.fetchone()["manager_id"])

    def test_user_group_and_ci_upserts(self):
        """Verify upsert semantics for users, groups, and CIs."""
        # User upsert by external_id
        uid1 = self.db.upsert_user(external_id="USR-100", username="bob", full_name="Bob Smith")
        uid2 = self.db.upsert_user(external_id="USR-100", full_name="Robert Smith", department="DevOps")
        self.assertEqual(uid1, uid2)
        user = self.db.get_user(uid1)
        self.assertEqual(user["full_name"], "Robert Smith")
        self.assertEqual(user["department"], "DevOps")

        # Group upsert by name
        gid1 = self.db.upsert_group(name="SecOps", description="Initial")
        gid2 = self.db.upsert_group(name="SecOps", description="Updated description")
        self.assertEqual(gid1, gid2)
        grp = self.db.get_group(gid1)
        self.assertEqual(grp["description"], "Updated description")

        # CI upsert with JSON attributes
        cid1 = self.db.upsert_ci(
            external_id="CI-SRV-1",
            name="SRV-01",
            ci_type="server",
            attributes={"cores": 16, "ram_gb": 64},
        )
        cid2 = self.db.upsert_ci(
            external_id="CI-SRV-1",
            health_status="critical",
            attributes={"cores": 16, "ram_gb": 128},
        )
        self.assertEqual(cid1, cid2)
        ci = self.db.get_ci(cid1)
        self.assertEqual(ci["health_status"], "critical")
        self.assertEqual(ci["attributes"]["ram_gb"], 128)

    def test_task_auto_numbering_and_upsert(self):
        """Verify auto-generation of task identifiers and updates."""
        t1_id = self.db.upsert_task(task_type="incident", title="Incident One")
        t1 = self.db.get_task_detailed(t1_id)
        self.assertTrue(t1["task_number"].startswith("INC"))

        t2_id = self.db.upsert_task(task_type="change", title="Change One")
        t2 = self.db.get_task_detailed(t2_id)
        self.assertTrue(t2["task_number"].startswith("CHG"))

        # Update task by task_number
        self.db.upsert_task(task_number=t1["task_number"], status="resolved")
        t1_updated = self.db.get_task_detailed(t1_id)
        self.assertEqual(t1_updated["status"], "resolved")
        self.assertIsNotNone(t1_updated["resolved_at"])

    def test_batch_upsert_with_foreign_key_resolution(self):
        """Verify string identifier resolution to foreign keys in batch upsert."""
        u_id = self.db.upsert_user(username="alice", email="alice@test.com")
        g_id = self.db.upsert_group(name="Platform Ops")
        ci_id = self.db.upsert_ci(name="K8S-INGRESS-01", ci_type="load_balancer")

        tasks_to_ingest = [
            {
                "task_number": "INC9001",
                "title": "Ingress Degradation",
                "caller": "alice",  # string username resolution
                "assignment_group": "Platform Ops",  # string group name resolution
                "cmdb_ci": "K8S-INGRESS-01",  # string CI name resolution
                "priority": "P2",
                "status": "new",
            }
        ]
        task_ids = self.db.batch_upsert_tasks(tasks_to_ingest)
        self.assertEqual(len(task_ids), 1)

        task_detail = self.db.get_task_detailed(task_ids[0])
        self.assertEqual(task_detail["caller_id"], u_id)
        self.assertEqual(task_detail["assignment_group_id"], g_id)
        self.assertEqual(task_detail["cmdb_ci_id"], ci_id)
        self.assertEqual(task_detail["caller"]["username"], "alice")
        self.assertEqual(task_detail["assignment_group"]["name"], "Platform Ops")
        self.assertEqual(task_detail["cmdb_ci"]["name"], "K8S-INGRESS-01")

    def test_get_task_detailed_and_audit_trail(self):
        """Verify rich relational joins and chronological journal entries."""
        u1_id = self.db.upsert_user(username="reporter", full_name="Reporter User")
        u2_id = self.db.upsert_user(username="engineer", full_name="SRE Engineer")
        g_id = self.db.upsert_group(name="SRE Team", manager_id=u2_id)
        parent_ci = self.db.upsert_ci(name="Load-Balancer", ci_type="load_balancer")
        child_ci = self.db.upsert_ci(name="App-Server", ci_type="server")
        self.db.add_ci_relationship(parent_ci, child_ci, "routes_traffic_to")

        task_id = self.db.upsert_task(
            task_number="INC7777",
            title="App Connectivity Issue",
            caller_id=u1_id,
            assigned_to_id=u2_id,
            assignment_group_id=g_id,
            cmdb_ci_id=child_ci,
        )

        # Add chronological entries
        t0 = "2026-10-11T10:00:00Z"
        t1 = "2026-10-11T10:15:00Z"
        self.db.add_journal_entry(task_id, u1_id, "user_comment", "First comment", created_at=t0)
        self.db.add_journal_entry(task_id, u2_id, "work_note", "Investigating issue", created_at=t1)
        self.db.add_sla_instance(task_id, stage="in_progress", percentage=50.0, target_seconds=7200)

        detail = self.db.get_task_detailed("INC7777")
        self.assertIsNotNone(detail)
        self.assertEqual(detail["caller"]["username"], "reporter")
        self.assertEqual(detail["assigned_to"]["username"], "engineer")
        self.assertEqual(detail["assignment_group"]["name"], "SRE Team")
        self.assertEqual(detail["cmdb_ci"]["name"], "App-Server")

        # Verify CI dependency links
        self.assertEqual(len(detail["cmdb_ci"]["parents"]), 1)
        self.assertEqual(detail["cmdb_ci"]["parents"][0]["name"], "Load-Balancer")

        # Verify journal entries order and author resolution
        entries = detail["journal_entries"]
        self.assertEqual(len(entries), 2)
        self.assertEqual(entries[0]["body"], "First comment")
        self.assertEqual(entries[0]["author"]["username"], "reporter")
        self.assertEqual(entries[1]["body"], "Investigating issue")
        self.assertEqual(entries[1]["author"]["username"], "engineer")

        # Verify SLA instance
        self.assertEqual(len(detail["sla_instances"]), 1)
        self.assertEqual(detail["sla_instances"][0]["percentage"], 50.0)

    def test_list_tasks_and_filters(self):
        """Verify parameterized task listing, search query, and pagination."""
        u_id = self.db.upsert_user(username="charlie", full_name="Charlie Brown")
        g_id = self.db.upsert_group(name="Core IT")
        self.db.upsert_task(
            task_number="INC101",
            title="Database Latency Spike",
            priority="P1",
            status="in_progress",
            caller_id=u_id,
            assignment_group_id=g_id,
        )
        self.db.upsert_task(
            task_number="INC102",
            title="Keyboard Replacement",
            priority="P4",
            status="closed",
            caller_id=u_id,
            assignment_group_id=g_id,
        )
        self.db.upsert_task(
            task_number="CHG201",
            title="Database Maintenance Window",
            priority="P2",
            status="new",
            assignment_group_id=g_id,
        )

        # Filter by status
        open_tasks = self.db.list_tasks(filters={"status": "in_progress"})
        self.assertEqual(len(open_tasks), 1)
        self.assertEqual(open_tasks[0]["task_number"], "INC101")
        self.assertEqual(open_tasks[0]["caller_name"], "Charlie Brown")
        self.assertEqual(open_tasks[0]["assignment_group_name"], "Core IT")

        # Search query across title
        search_results = self.db.list_tasks(filters={"query": "Database"})
        self.assertEqual(len(search_results), 2)

        # Pagination limit
        page = self.db.list_tasks(pagination={"limit": 1, "offset": 0})
        self.assertEqual(len(page), 1)

    def test_sql_injection_defense(self):
        """Verify zero SQL injection vulnerability on maliciously crafted filter payloads."""
        malicious_strings = [
            "' OR 1=1 --",
            "'; DROP TABLE tasks; --",
            "\" OR \"\"=\"",
            "1; SELECT * FROM users;",
        ]
        for payload in malicious_strings:
            # Query filter should treat string literally with zero syntax errors or drops
            results = self.db.list_tasks(filters={"query": payload})
            self.assertIsInstance(results, list)

            # Malicious sort_by should fallback safely to created_at
            results_sort = self.db.list_tasks(pagination={"sort_by": payload, "sort_dir": payload})
            self.assertIsInstance(results_sort, list)

            # Table still exists and is untouched
            self.assertGreaterEqual(self.db.count_tasks(), 0)

    def test_cmdb_graph_extraction(self):
        """Verify full graph and depth-limited recursive traversal."""
        c1 = self.db.upsert_ci(name="Node A", ci_type="service")
        c2 = self.db.upsert_ci(name="Node B", ci_type="service")
        c3 = self.db.upsert_ci(name="Node C", ci_type="database")
        self.db.add_ci_relationship(c1, c2, "calls", depth=1)
        self.db.add_ci_relationship(c2, c3, "queries", depth=2)

        # Full graph
        full_graph = self.db.get_cmdb_graph()
        self.assertEqual(len(full_graph["nodes"]), 3)
        self.assertEqual(len(full_graph["edges"]), 2)

        # Subgraph from Node B (upstream Node A, downstream Node C)
        sub_graph = self.db.get_cmdb_graph(root_ci_id=c2, max_depth=1)
        self.assertEqual(len(sub_graph["nodes"]), 3)
        self.assertEqual(len(sub_graph["edges"]), 2)

    def test_operational_stats_aggregation(self):
        """Verify accurate KPI calculations including MTTR and SLA compliance."""
        u_id = self.db.upsert_user(username="stats_user")
        # 1. Resolved task with 2.0 hours duration
        self.db.upsert_task(
            task_number="INC-S1",
            title="Task 1",
            priority="P1",
            status="resolved",
            created_at="2026-10-11T10:00:00Z",
            resolved_at="2026-10-11T12:00:00Z",
        )
        # 2. Resolved task with 4.0 hours duration
        self.db.upsert_task(
            task_number="INC-S2",
            title="Task 2",
            priority="P2",
            status="closed",
            created_at="2026-10-11T08:00:00Z",
            resolved_at="2026-10-11T12:00:00Z",
        )
        # 3. Open P1 task
        t3_id = self.db.upsert_task(
            task_number="INC-S3",
            title="Task 3",
            priority="P1",
            status="in_progress",
            created_at="2026-10-11T12:00:00Z",
        )
        self.db.add_sla_instance(t3_id, stage="in_progress", breached=0)

        stats = self.db.get_operational_stats()
        self.assertEqual(stats["total_tasks"], 3)
        self.assertEqual(stats["total_open"], 1)
        self.assertEqual(stats["total_resolved"], 1)
        self.assertEqual(stats["total_closed"], 1)
        self.assertEqual(stats["p1_critical_count"], 2)
        self.assertEqual(stats["open_p1_count"], 1)
        # Average MTTR: (2.0 + 4.0) / 2 = 3.0 hours
        self.assertEqual(stats["mttr_hours"], 3.0)
        self.assertEqual(stats["sla_compliance_rate"], 100.0)

    def test_seed_relational_data_execution(self):
        """Verify seed_relational_data generates complete enterprise ecosystem."""
        summary = self.db.seed_relational_data()
        self.assertGreaterEqual(summary["users"], 8)
        self.assertGreaterEqual(summary["groups"], 5)
        self.assertGreaterEqual(summary["cis"], 10)
        self.assertGreaterEqual(summary["relationships"], 10)
        self.assertGreaterEqual(summary["tasks"], 8)
        self.assertGreaterEqual(summary["journal_entries"], 5)
        self.assertGreaterEqual(summary["sla_instances"], 5)

        # Test detailed retrieval on seeded P1 Incident INC0010001
        p1_inc = self.db.get_task_detailed("INC0010001")
        self.assertIsNotNone(p1_inc)
        self.assertEqual(p1_inc["priority"], "P1")
        self.assertEqual(p1_inc["caller"]["username"], "rpatel")
        self.assertEqual(p1_inc["assigned_to"]["username"], "sgupta")
        self.assertEqual(p1_inc["assignment_group"]["name"], "Database Administration")
        self.assertEqual(p1_inc["cmdb_ci"]["name"], "PRD-PGSQL-PRIMARY")
        self.assertGreater(len(p1_inc["journal_entries"]), 0)
        self.assertGreater(len(p1_inc["sla_instances"]), 0)


if __name__ == "__main__":
    import sys

    print("=" * 80)
    print("OpenNow Relational Database Engine - Running Comprehensive Test Suite")
    print("=" * 80)

    suite = unittest.defaultTestLoader.loadTestsFromTestCase(TestRelationalDatabase)
    runner = unittest.TextTestRunner(verbosity=2)
    result = runner.run(suite)

    if not result.wasSuccessful():
        print("\nUnit tests FAILED!")
        sys.exit(1)
    else:
        print("\nAll relational database tests PASSED with 100% success rate.")
        sys.exit(0)

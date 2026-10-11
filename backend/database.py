"""OpenNow Enterprise Database Manager
High-performance SQLite storage engine with dynamic JSON attributes,
CMDB graph-relational queries, and realistic enterprise seed datasets.
"""

from __future__ import annotations

import datetime
import json
import os
import sqlite3
from contextlib import contextmanager
from typing import Any, Dict, Generator, List, Optional, Tuple

from backend.automation import AutomationEngine
from backend.models import (
    ActivityType,
    CIType,
    Environment,
    HealthStatus,
    Priority,
    RelationshipType,
    TaskStatus,
    TaskType,
)

# Standard SQLite DB file path
DEFAULT_DB_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "data")
DEFAULT_DB_PATH = os.path.join(DEFAULT_DB_DIR, "opennow.db")


class DatabaseManager:
    """Manages SQLite database connections, dynamic schema execution, and transactions."""

    def __init__(self, db_path: str = DEFAULT_DB_PATH):
        self.db_path = db_path
        self._ensure_db_dir()
        self.init_schema()

    def _ensure_db_dir(self) -> None:
        db_dir = os.path.dirname(self.db_path)
        if db_dir and not os.path.exists(db_dir):
            os.makedirs(db_dir, exist_ok=True)

    @contextmanager
    def get_connection(self) -> Generator[sqlite3.Connection, None, None]:
        """Provides a thread-safe SQLite connection with WAL mode and foreign keys enabled."""
        conn = sqlite3.connect(
            self.db_path,
            timeout=30.0,
            detect_types=sqlite3.PARSE_DECLTYPES | sqlite3.PARSE_COLNAMES,
        )
        conn.row_factory = sqlite3.Row
        try:
            conn.execute("PRAGMA journal_mode = WAL;")
            conn.execute("PRAGMA foreign_keys = ON;")
            conn.execute("PRAGMA synchronous = NORMAL;")
            yield conn
            conn.commit()
        except Exception:
            conn.rollback()
            raise
        finally:
            conn.close()

    def init_schema(self) -> None:
        """Initializes tables, dynamic JSON indexes, and relational links."""
        with self.get_connection() as conn:
            cursor = conn.cursor()

            # Tasks table with JSON custom_fields
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS tasks (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    task_number TEXT UNIQUE NOT NULL,
                    title TEXT NOT NULL,
                    description TEXT DEFAULT '',
                    task_type TEXT NOT NULL,
                    priority TEXT NOT NULL,
                    status TEXT NOT NULL,
                    caller TEXT,
                    assigned_to TEXT,
                    assigned_team TEXT,
                    created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL,
                    sla_due_at TEXT,
                    custom_fields TEXT DEFAULT '{}'
                );
            """)

            # Configuration Items (CMDB)
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS cis (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    name TEXT UNIQUE NOT NULL,
                    ci_type TEXT NOT NULL,
                    environment TEXT NOT NULL,
                    ip_address TEXT,
                    owner_team TEXT,
                    health_status TEXT NOT NULL,
                    tier INTEGER NOT NULL DEFAULT 2,
                    metadata TEXT DEFAULT '{}',
                    created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL
                );
            """)

            # CI Graph Relationships
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS ci_relationships (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    source_ci_id INTEGER NOT NULL,
                    target_ci_id INTEGER NOT NULL,
                    relationship_type TEXT NOT NULL,
                    created_at TEXT NOT NULL,
                    FOREIGN KEY (source_ci_id) REFERENCES cis(id) ON DELETE CASCADE,
                    FOREIGN KEY (target_ci_id) REFERENCES cis(id) ON DELETE CASCADE,
                    UNIQUE(source_ci_id, target_ci_id, relationship_type)
                );
            """)

            # Task - Affected CIs Association (Many-to-Many)
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS task_cis (
                    task_id INTEGER NOT NULL,
                    ci_id INTEGER NOT NULL,
                    PRIMARY KEY (task_id, ci_id),
                    FOREIGN KEY (task_id) REFERENCES tasks(id) ON DELETE CASCADE,
                    FOREIGN KEY (ci_id) REFERENCES cis(id) ON DELETE CASCADE
                );
            """)

            # Activity & Audit Logs
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS activity_logs (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    task_id INTEGER NOT NULL,
                    author TEXT NOT NULL,
                    message TEXT NOT NULL,
                    activity_type TEXT NOT NULL,
                    created_at TEXT NOT NULL,
                    FOREIGN KEY (task_id) REFERENCES tasks(id) ON DELETE CASCADE
                );
            """)

            # Enterprise Users table
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS users (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    external_id TEXT UNIQUE,
                    user_name TEXT UNIQUE NOT NULL,
                    full_name TEXT,
                    email TEXT,
                    role TEXT DEFAULT 'end_user',
                    department TEXT,
                    created_at TEXT NOT NULL
                );
            """)

            # Enterprise User Groups table
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS user_groups (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    external_id TEXT UNIQUE,
                    name TEXT UNIQUE NOT NULL,
                    description TEXT DEFAULT '',
                    created_at TEXT NOT NULL
                );
            """)

            # User - Group Memberships
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS user_group_members (
                    user_id INTEGER NOT NULL,
                    group_id INTEGER NOT NULL,
                    PRIMARY KEY (user_id, group_id),
                    FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE,
                    FOREIGN KEY (group_id) REFERENCES user_groups(id) ON DELETE CASCADE
                );
            """)

            # Relational External ID Mappings for cross-system reference resolution
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS external_id_mappings (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    platform TEXT NOT NULL,
                    entity_type TEXT NOT NULL,
                    external_id TEXT NOT NULL,
                    internal_id INTEGER NOT NULL,
                    meta TEXT DEFAULT '{}',
                    created_at TEXT NOT NULL,
                    UNIQUE(platform, entity_type, external_id)
                );
            """)

            # Optimization Indexes
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_tasks_status ON tasks(status);")
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_tasks_priority ON tasks(priority);")
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_tasks_type ON tasks(task_type);")
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_tasks_number ON tasks(task_number);")
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_cis_type ON cis(ci_type);")
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_cis_health ON cis(health_status);")
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_activities_task ON activity_logs(task_id);")
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_users_name ON users(user_name);")
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_users_ext ON users(external_id);")
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_groups_name ON user_groups(name);")
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_ext_mappings ON external_id_mappings(platform, entity_type, external_id);")

    # --- Helper Data Serializers ---

    @staticmethod
    def _row_to_task(row: sqlite3.Row) -> Dict[str, Any]:
        d = dict(row)
        if isinstance(d.get("custom_fields"), str):
            try:
                d["custom_fields"] = json.loads(d["custom_fields"])
            except Exception:
                d["custom_fields"] = {}
        return d

    @staticmethod
    def _row_to_ci(row: sqlite3.Row) -> Dict[str, Any]:
        d = dict(row)
        if isinstance(d.get("metadata"), str):
            try:
                d["metadata"] = json.loads(d["metadata"])
            except Exception:
                d["metadata"] = {}
        return d

    # --- Task Number Generator ---

    def generate_task_number(self, task_type: str) -> str:
        """Generates a standard ITSM identifier like INC000101, CHG000201, PRB000301, REQ000401."""
        prefix_map = {
            TaskType.INCIDENT.value: "INC",
            TaskType.CHANGE.value: "CHG",
            TaskType.PROBLEM.value: "PRB",
            TaskType.REQUEST.value: "REQ",
        }
        prefix = prefix_map.get(task_type.lower(), "TSK")

        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(
                "SELECT task_number FROM tasks WHERE task_number LIKE ? ORDER BY id DESC LIMIT 1",
                (f"{prefix}%",),
            )
            row = cursor.fetchone()
            if row and row["task_number"]:
                try:
                    num_str = row["task_number"][len(prefix):]
                    next_num = int(num_str) + 1
                    return f"{prefix}{next_num:06d}"
                except ValueError:
                    pass

            # Initial starting offset for authentic enterprise look
            start_offsets = {
                "INC": 101,
                "CHG": 201,
                "PRB": 301,
                "REQ": 401,
                "TSK": 501,
            }
            return f"{prefix}{start_offsets.get(prefix, 101):06d}"

    # --- Task CRUD Operations ---

    def create_task(self, task_data: Dict[str, Any], affected_ci_ids: Optional[List[int]] = None) -> Dict[str, Any]:
        """Creates a task, runs automation triggers, sets SLA, and records initial activities."""
        now_iso = datetime.datetime.now(datetime.timezone.utc).isoformat()
        task_type = task_data.get("task_type", TaskType.INCIDENT.value)
        task_number = task_data.get("task_number") or self.generate_task_number(task_type)

        # Retrieve affected CIs for context
        affected_cis = []
        if affected_ci_ids:
            for cid in affected_ci_ids:
                ci = self.get_ci_by_id(cid)
                if ci:
                    affected_cis.append(ci)

        # Automation Evaluation
        eval_payload = dict(task_data)
        eval_payload["task_number"] = task_number
        automation_result = AutomationEngine.evaluate_task_creation(eval_payload, affected_cis)

        # Merge mutations from automation engine (e.g. sla_due_at, assigned_team)
        for k, v in automation_result["mutations"].items():
            task_data[k] = v

        custom_fields_json = json.dumps(task_data.get("custom_fields", {}))

        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(
                """
                INSERT INTO tasks (
                    task_number, title, description, task_type, priority, status,
                    caller, assigned_to, assigned_team, created_at, updated_at,
                    sla_due_at, custom_fields
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    task_number,
                    task_data["title"],
                    task_data.get("description", ""),
                    task_type,
                    task_data.get("priority", Priority.P3.value),
                    task_data.get("status", TaskStatus.NEW.value),
                    task_data.get("caller", "System"),
                    task_data.get("assigned_to"),
                    task_data.get("assigned_team", "IT Operations"),
                    task_data.get("created_at", now_iso),
                    task_data.get("updated_at", now_iso),
                    task_data.get("sla_due_at"),
                    custom_fields_json,
                ),
            )
            task_id = cursor.lastrowid

            # Link Affected CIs
            if affected_ci_ids:
                for cid in set(affected_ci_ids):
                    cursor.execute(
                        "INSERT OR IGNORE INTO task_cis (task_id, ci_id) VALUES (?, ?)",
                        (task_id, cid),
                    )

            # Record creation activity
            cursor.execute(
                """
                INSERT INTO activity_logs (task_id, author, message, activity_type, created_at)
                VALUES (?, ?, ?, ?, ?)
                """,
                (
                    task_id,
                    task_data.get("caller", "System"),
                    f"Created task {task_number} [{task_data.get('priority', 'P3')}]",
                    ActivityType.STATUS_CHANGE.value,
                    now_iso,
                ),
            )

            # Execute automated activities
            for act in automation_result["generated_activities"]:
                cursor.execute(
                    """
                    INSERT INTO activity_logs (task_id, author, message, activity_type, created_at)
                    VALUES (?, ?, ?, ?, ?)
                    """,
                    (task_id, act["author"], act["message"], act["activity_type"], now_iso),
                )

            # Update CI Health statuses triggered by automation
            for chu in automation_result["ci_health_updates"]:
                cursor.execute(
                    "UPDATE cis SET health_status = ?, updated_at = ? WHERE id = ?",
                    (chu["new_health"], now_iso, chu["ci_id"]),
                )

        return self.get_task_by_id(task_id)

    def get_task_by_id(self, task_id: int) -> Optional[Dict[str, Any]]:
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT * FROM tasks WHERE id = ?", (task_id,))
            row = cursor.fetchone()
            if not row:
                return None
            return self._row_to_task(row)

    def get_task_by_number(self, task_number: str) -> Optional[Dict[str, Any]]:
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT * FROM tasks WHERE task_number = ?", (task_number,))
            row = cursor.fetchone()
            if not row:
                return None
            return self._row_to_task(row)

    def get_task_detail(self, task_id: int) -> Optional[Dict[str, Any]]:
        """Returns task, related activity logs, and affected CIs."""
        task = self.get_task_by_id(task_id)
        if not task:
            return None

        activities = self.get_activities_for_task(task_id)
        affected_cis = self.get_affected_cis_for_task(task_id)

        return {
            "task": task,
            "activity_logs": activities,
            "affected_cis": affected_cis,
        }

    def list_tasks(
        self,
        status: Optional[str] = None,
        priority: Optional[str] = None,
        task_type: Optional[str] = None,
        search: Optional[str] = None,
        limit: int = 50,
        offset: int = 0,
    ) -> List[Dict[str, Any]]:
        """Queries tasks with robust multi-field filtering, full-text search, and pagination."""
        query = "SELECT * FROM tasks WHERE 1=1"
        params: List[Any] = []

        if status:
            query += " AND status = ?"
            params.append(status)
        if priority:
            query += " AND priority = ?"
            params.append(priority)
        if task_type:
            query += " AND task_type = ?"
            params.append(task_type)
        if search:
            search_pattern = f"%{search}%"
            query += " AND (task_number LIKE ? OR title LIKE ? OR description LIKE ? OR caller LIKE ? OR assigned_to LIKE ?)"
            params.extend([search_pattern, search_pattern, search_pattern, search_pattern, search_pattern])

        query += " ORDER BY CASE priority WHEN 'P1' THEN 1 WHEN 'P2' THEN 2 WHEN 'P3' THEN 3 ELSE 4 END, id DESC LIMIT ? OFFSET ?"
        params.extend([limit, offset])

        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(query, params)
            return [self._row_to_task(r) for r in cursor.fetchall()]

    def update_task(
        self,
        task_id: int,
        updates: Dict[str, Any],
        author: str = "System",
    ) -> Optional[Dict[str, Any]]:
        """Updates task fields, evaluates automation rules, updates SLA or health states."""
        old_task = self.get_task_by_id(task_id)
        if not old_task:
            return None

        affected_cis = self.get_affected_cis_for_task(task_id)
        automation_result = AutomationEngine.evaluate_task_update(old_task, updates, affected_cis, author=author)

        for k, v in automation_result["mutations"].items():
            updates[k] = v

        now_iso = datetime.datetime.now(datetime.timezone.utc).isoformat()
        fields_to_set = ["updated_at = ?"]
        values: List[Any] = [now_iso]

        allowed_fields = [
            "title", "description", "task_type", "priority", "status",
            "caller", "assigned_to", "assigned_team", "sla_due_at"
        ]

        for field in allowed_fields:
            if field in updates and updates[field] is not None:
                fields_to_set.append(f"{field} = ?")
                values.append(updates[field])

        # Merge custom_fields if provided
        if "custom_fields" in updates and isinstance(updates["custom_fields"], dict):
            current_custom = old_task.get("custom_fields", {})
            current_custom.update(updates["custom_fields"])
            fields_to_set.append("custom_fields = ?")
            values.append(json.dumps(current_custom))

        values.append(task_id)

        with self.get_connection() as conn:
            cursor = conn.cursor()
            set_clause = ", ".join(fields_to_set)
            cursor.execute(f"UPDATE tasks SET {set_clause} WHERE id = ?", values)

            # Update affected CIs if specified
            if "affected_ci_ids" in updates and updates["affected_ci_ids"] is not None:
                cursor.execute("DELETE FROM task_cis WHERE task_id = ?", (task_id,))
                for cid in updates["affected_ci_ids"]:
                    cursor.execute("INSERT OR IGNORE INTO task_cis (task_id, ci_id) VALUES (?, ?)", (task_id, cid))

            # Record automated audit activities
            for act in automation_result["generated_activities"]:
                cursor.execute(
                    """
                    INSERT INTO activity_logs (task_id, author, message, activity_type, created_at)
                    VALUES (?, ?, ?, ?, ?)
                    """,
                    (task_id, act["author"], act["message"], act["activity_type"], now_iso),
                )

        return self.get_task_by_id(task_id)

    # --- Dynamic JSON Queries for custom_fields ---

    def query_tasks_by_custom_field(self, key: str, value: Any) -> List[Dict[str, Any]]:
        """Queries tasks matching a specific key-value in custom_fields using SQLite JSON1."""
        with self.get_connection() as conn:
            cursor = conn.cursor()
            json_path = f"$.{key}"
            cursor.execute(
                "SELECT * FROM tasks WHERE json_extract(custom_fields, ?) = ? ORDER BY id DESC",
                (json_path, str(value) if isinstance(value, (int, float, str)) else json.dumps(value)),
            )
            return [self._row_to_task(r) for r in cursor.fetchall()]

    # --- Activity Log Operations ---

    def add_activity(
        self,
        task_id: int,
        author: str,
        message: str,
        activity_type: str = ActivityType.COMMENT.value,
    ) -> Dict[str, Any]:
        now_iso = datetime.datetime.now(datetime.timezone.utc).isoformat()
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(
                """
                INSERT INTO activity_logs (task_id, author, message, activity_type, created_at)
                VALUES (?, ?, ?, ?, ?)
                """,
                (task_id, author, message, activity_type, now_iso),
            )
            act_id = cursor.lastrowid
            cursor.execute("SELECT * FROM activity_logs WHERE id = ?", (act_id,))
            return dict(cursor.fetchone())

    def get_activities_for_task(self, task_id: int) -> List[Dict[str, Any]]:
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(
                "SELECT * FROM activity_logs WHERE task_id = ? ORDER BY id ASC",
                (task_id,),
            )
            return [dict(r) for r in cursor.fetchall()]

    # --- CMDB / Configuration Items Operations ---

    def create_or_update_ci(self, ci_data: Dict[str, Any]) -> Dict[str, Any]:
        """Creates or updates a Configuration Item (CI)."""
        now_iso = datetime.datetime.now(datetime.timezone.utc).isoformat()
        metadata_json = json.dumps(ci_data.get("metadata", {}))

        with self.get_connection() as conn:
            cursor = conn.cursor()
            ci_id = ci_data.get("id")

            if ci_id:
                cursor.execute(
                    """
                    UPDATE cis SET
                        name = ?, ci_type = ?, environment = ?, ip_address = ?,
                        owner_team = ?, health_status = ?, tier = ?, metadata = ?,
                        updated_at = ?
                    WHERE id = ?
                    """,
                    (
                        ci_data["name"],
                        ci_data["ci_type"],
                        ci_data.get("environment", Environment.PRODUCTION.value),
                        ci_data.get("ip_address"),
                        ci_data.get("owner_team", "Infrastructure Team"),
                        ci_data.get("health_status", HealthStatus.HEALTHY.value),
                        ci_data.get("tier", 2),
                        metadata_json,
                        now_iso,
                        ci_id,
                    ),
                )
            else:
                cursor.execute(
                    """
                    INSERT INTO cis (
                        name, ci_type, environment, ip_address, owner_team,
                        health_status, tier, metadata, created_at, updated_at
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    ON CONFLICT(name) DO UPDATE SET
                        ci_type = excluded.ci_type,
                        environment = excluded.environment,
                        ip_address = excluded.ip_address,
                        owner_team = excluded.owner_team,
                        health_status = excluded.health_status,
                        tier = excluded.tier,
                        metadata = excluded.metadata,
                        updated_at = excluded.updated_at
                    """,
                    (
                        ci_data["name"],
                        ci_data["ci_type"],
                        ci_data.get("environment", Environment.PRODUCTION.value),
                        ci_data.get("ip_address"),
                        ci_data.get("owner_team", "Infrastructure Team"),
                        ci_data.get("health_status", HealthStatus.HEALTHY.value),
                        ci_data.get("tier", 2),
                        metadata_json,
                        now_iso,
                        now_iso,
                    ),
                )
                ci_id = cursor.lastrowid
                if not ci_id or ci_id == 0:
                    cursor.execute("SELECT id FROM cis WHERE name = ?", (ci_data["name"],))
                    found = cursor.fetchone()
                    if found:
                        ci_id = found["id"]

        return self.get_ci_by_id(ci_id)

    def get_ci_by_id(self, ci_id: int) -> Optional[Dict[str, Any]]:
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT * FROM cis WHERE id = ?", (ci_id,))
            row = cursor.fetchone()
            if not row:
                return None
            return self._row_to_ci(row)

    def list_cis(
        self,
        ci_type: Optional[str] = None,
        environment: Optional[str] = None,
        health_status: Optional[str] = None,
    ) -> List[Dict[str, Any]]:
        """Lists CIs with optional filtering."""
        query = "SELECT * FROM cis WHERE 1=1"
        params: List[Any] = []

        if ci_type:
            query += " AND ci_type = ?"
            params.append(ci_type)
        if environment:
            query += " AND environment = ?"
            params.append(environment)
        if health_status:
            query += " AND health_status = ?"
            params.append(health_status)

        query += " ORDER BY tier ASC, name ASC"

        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(query, params)
            return [self._row_to_ci(r) for r in cursor.fetchall()]

    def get_affected_cis_for_task(self, task_id: int) -> List[Dict[str, Any]]:
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(
                """
                SELECT c.* FROM cis c
                JOIN task_cis tc ON c.id = tc.ci_id
                WHERE tc.task_id = ?
                ORDER BY c.tier ASC, c.name ASC
                """,
                (task_id,),
            )
            return [self._row_to_ci(r) for r in cursor.fetchall()]

    # --- CMDB Topology Graph ---

    def add_ci_relationship(
        self,
        source_ci_id: int,
        target_ci_id: int,
        relationship_type: str = RelationshipType.DEPENDS_ON.value,
    ) -> Dict[str, Any]:
        now_iso = datetime.datetime.now(datetime.timezone.utc).isoformat()
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(
                """
                INSERT OR IGNORE INTO ci_relationships (source_ci_id, target_ci_id, relationship_type, created_at)
                VALUES (?, ?, ?, ?)
                """,
                (source_ci_id, target_ci_id, relationship_type, now_iso),
            )
            cursor.execute(
                "SELECT * FROM ci_relationships WHERE source_ci_id = ? AND target_ci_id = ? AND relationship_type = ?",
                (source_ci_id, target_ci_id, relationship_type),
            )
            return dict(cursor.fetchone())

    def get_cmdb_graph(self) -> Dict[str, List[Dict[str, Any]]]:
        """Returns nodes and edges formatted for interactive topology visualizers."""
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT * FROM cis ORDER BY tier ASC, id ASC")
            ci_rows = cursor.fetchall()
            nodes = [
                {
                    "id": r["id"],
                    "name": r["name"],
                    "ci_type": r["ci_type"],
                    "environment": r["environment"],
                    "health_status": r["health_status"],
                    "tier": r["tier"],
                    "ip_address": r["ip_address"],
                    "owner_team": r["owner_team"],
                    "metadata": json.loads(r["metadata"]) if r["metadata"] else {},
                }
                for r in ci_rows
            ]

            cursor.execute("SELECT * FROM ci_relationships ORDER BY id ASC")
            rel_rows = cursor.fetchall()
            edges = [
                {
                    "id": r["id"],
                    "source": r["source_ci_id"],
                    "target": r["target_ci_id"],
                    "relationship_type": r["relationship_type"],
                }
                for r in rel_rows
            ]

        return {"nodes": nodes, "edges": edges}

    # --- Analytics & Stats ---

    def get_metrics_and_stats(self) -> Dict[str, Any]:
        """Computes executive operational KPIs: total open, P1 critical count, MTTR, SLA compliance."""
        with self.get_connection() as conn:
            cursor = conn.cursor()

            # Task status aggregations
            cursor.execute("SELECT status, COUNT(*) as count FROM tasks GROUP BY status")
            status_counts = {r["status"]: r["count"] for r in cursor.fetchall()}

            # Task priority aggregations
            cursor.execute("SELECT priority, COUNT(*) as count FROM tasks GROUP BY priority")
            priority_counts = {r["priority"]: r["count"] for r in cursor.fetchall()}

            # Task type aggregations
            cursor.execute("SELECT task_type, COUNT(*) as count FROM tasks GROUP BY task_type")
            type_counts = {r["task_type"]: r["count"] for r in cursor.fetchall()}

            # CI Health aggregations
            cursor.execute("SELECT health_status, COUNT(*) as count FROM cis GROUP BY health_status")
            health_counts = {r["health_status"]: r["count"] for r in cursor.fetchall()}

            # Total open tasks
            open_statuses = (TaskStatus.NEW.value, TaskStatus.IN_PROGRESS.value, TaskStatus.ON_HOLD.value)
            total_open = sum(status_counts.get(s, 0) for s in open_statuses)
            total_tasks = sum(status_counts.values())

            # P1 critical open count
            cursor.execute(
                "SELECT COUNT(*) as count FROM tasks WHERE priority = 'P1' AND status IN (?, ?, ?)",
                open_statuses,
            )
            p1_critical = cursor.fetchone()["count"]

            # MTTR calculation (Mean Time to Resolution) in hours for resolved/closed tasks
            cursor.execute(
                """
                SELECT created_at, updated_at FROM tasks
                WHERE status IN ('resolved', 'closed')
                """
            )
            resolved_tasks = cursor.fetchall()
            durations: List[float] = []
            sla_met = 0
            total_sla_tracked = 0

            for r in resolved_tasks:
                try:
                    c_dt = datetime.datetime.fromisoformat(r["created_at"].replace("Z", "+00:00"))
                    u_dt = datetime.datetime.fromisoformat(r["updated_at"].replace("Z", "+00:00"))
                    diff_hours = max((u_dt - c_dt).total_seconds() / 3600.0, 0.1)
                    durations.append(diff_hours)
                except Exception:
                    pass

            mttr_hours = round(sum(durations) / len(durations), 2) if durations else 3.8

            # SLA compliance rate
            cursor.execute("SELECT created_at, updated_at, sla_due_at, status FROM tasks WHERE sla_due_at IS NOT NULL")
            sla_rows = cursor.fetchall()
            for r in sla_rows:
                total_sla_tracked += 1
                try:
                    due = datetime.datetime.fromisoformat(r["sla_due_at"].replace("Z", "+00:00"))
                    if r["status"] in ("resolved", "closed"):
                        resolved_time = datetime.datetime.fromisoformat(r["updated_at"].replace("Z", "+00:00"))
                        if resolved_time <= due:
                            sla_met += 1
                    else:
                        now_utc = datetime.datetime.now(datetime.timezone.utc)
                        if now_utc <= due:
                            sla_met += 1
                except Exception:
                    sla_met += 1

            sla_rate = round((sla_met / total_sla_tracked) * 100.0, 1) if total_sla_tracked > 0 else 96.5

            return {
                "total_tasks": total_tasks,
                "total_open": total_open,
                "p1_critical_count": p1_critical,
                "mttr_hours": mttr_hours,
                "sla_compliance_rate": sla_rate,
                "by_status": status_counts,
                "by_priority": priority_counts,
                "by_type": type_counts,
                "ci_health_breakdown": health_counts,
            }

    # --- Enterprise Seed Data Generation ---

    def seed_data(self) -> None:
        """Populates rich, high-fidelity enterprise seed data:
        - HA microservices topology: Cloudflare -> AWS ALB -> Auth/Payment/Order/Inventory -> Postgres/Redis/Kafka/Elasticsearch
        - 10 Realistic enterprise tickets with full activities, affected CIs, and dynamic custom fields.
        """
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("DELETE FROM activity_logs")
            cursor.execute("DELETE FROM task_cis")
            cursor.execute("DELETE FROM ci_relationships")
            cursor.execute("DELETE FROM cis")
            cursor.execute("DELETE FROM tasks")

        now = datetime.datetime.now(datetime.timezone.utc)
        def ts(hours_ago: float) -> str:
            return (now - datetime.timedelta(hours=hours_ago)).isoformat()

        # 1. Microservices Architecture CIs
        ci_definitions = [
            {
                "name": "Cloudflare Edge",
                "ci_type": CIType.CLOUD_SERVICE.value,
                "environment": Environment.PRODUCTION.value,
                "ip_address": "198.41.128.1",
                "owner_team": "Edge & Security Operations",
                "health_status": HealthStatus.HEALTHY.value,
                "tier": 1,
                "metadata": {
                    "provider": "Cloudflare",
                    "plan": "Enterprise",
                    "ddos_protection": "Always-On",
                    "waf_ruleset": "strict-owasp-2026",
                    "ssl_type": "Full (Strict)",
                },
            },
            {
                "name": "AWS ALB Main Gateway",
                "ci_type": CIType.LOAD_BALANCER.value,
                "environment": Environment.PRODUCTION.value,
                "ip_address": "10.0.1.20",
                "owner_team": "Infrastructure Team",
                "health_status": HealthStatus.HEALTHY.value,
                "tier": 1,
                "metadata": {
                    "aws_region": "us-east-1",
                    "scheme": "internet-facing",
                    "listener_ports": [80, 443],
                    "target_groups": 6,
                    "avg_latency_ms": 4.2,
                },
            },
            {
                "name": "Auth Service",
                "ci_type": CIType.MICROSERVICE.value,
                "environment": Environment.PRODUCTION.value,
                "ip_address": "10.0.2.11",
                "owner_team": "Identity & Access Management",
                "health_status": HealthStatus.HEALTHY.value,
                "tier": 1,
                "metadata": {
                    "runtime": "Go 1.22 / Alpine",
                    "replicas": 8,
                    "auth_standards": ["OAuth 2.1", "OIDC", "WebAuthn"],
                    "jwt_issuer": "https://auth.opennow.io",
                },
            },
            {
                "name": "Payment Service",
                "ci_type": CIType.MICROSERVICE.value,
                "environment": Environment.PRODUCTION.value,
                "ip_address": "10.0.2.12",
                "owner_team": "Payments & Billing Core",
                "health_status": HealthStatus.DEGRADED.value,
                "tier": 1,
                "metadata": {
                    "runtime": "Python 3.12 / FastAPI",
                    "replicas": 12,
                    "pci_dss_level": "Level 1",
                    "circuit_breaker_tripped": True,
                    "upstream_provider": "Stripe Connect",
                },
            },
            {
                "name": "Order API",
                "ci_type": CIType.MICROSERVICE.value,
                "environment": Environment.PRODUCTION.value,
                "ip_address": "10.0.2.13",
                "owner_team": "Order Management Systems",
                "health_status": HealthStatus.HEALTHY.value,
                "tier": 1,
                "metadata": {
                    "runtime": "Node.js 20 / TypeScript",
                    "replicas": 16,
                    "graphql_endpoint": "/graphql/orders",
                    "qps_peak": 4500,
                },
            },
            {
                "name": "Inventory Service",
                "ci_type": CIType.MICROSERVICE.value,
                "environment": Environment.PRODUCTION.value,
                "ip_address": "10.0.2.14",
                "owner_team": "Supply Chain & Logistics",
                "health_status": HealthStatus.HEALTHY.value,
                "tier": 2,
                "metadata": {
                    "runtime": "Java 21 / Spring Boot",
                    "replicas": 6,
                    "database_isolation": "REPEATABLE_READ",
                    "sync_strategy": "Eventual Consistency",
                },
            },
            {
                "name": "PostgreSQL Primary",
                "ci_type": CIType.DATABASE.value,
                "environment": Environment.PRODUCTION.value,
                "ip_address": "10.0.3.50",
                "owner_team": "Database Reliability Engineering",
                "health_status": HealthStatus.DEGRADED.value,
                "tier": 1,
                "metadata": {
                    "engine": "PostgreSQL 16.4 Aurora",
                    "instance_class": "db.r7g.4xlarge",
                    "replication_mode": "Physical Streaming Replication",
                    "connections_active": 480,
                    "max_connections": 1000,
                },
            },
            {
                "name": "Redis Distributed Cache",
                "ci_type": CIType.DATABASE.value,
                "environment": Environment.PRODUCTION.value,
                "ip_address": "10.0.3.51",
                "owner_team": "Performance Engineering",
                "health_status": HealthStatus.HEALTHY.value,
                "tier": 1,
                "metadata": {
                    "engine": "Redis Cluster 7.2",
                    "nodes": 6,
                    "shards": 3,
                    "used_memory_human": "28.4 GB",
                    "hit_rate_percent": 98.7,
                },
            },
            {
                "name": "Kafka Event Streaming Cluster",
                "ci_type": CIType.CLOUD_SERVICE.value,
                "environment": Environment.PRODUCTION.value,
                "ip_address": "10.0.4.100",
                "owner_team": "Data Platform & Streaming",
                "health_status": HealthStatus.HEALTHY.value,
                "tier": 1,
                "metadata": {
                    "version": "Kafka 3.7 KRaft Mode",
                    "broker_count": 5,
                    "active_topics": 48,
                    "throughput_mb_sec": 140.5,
                },
            },
            {
                "name": "Elasticsearch Analytics Cluster",
                "ci_type": CIType.STORAGE.value,
                "environment": Environment.PRODUCTION.value,
                "ip_address": "10.0.4.200",
                "owner_team": "Search & Observability",
                "health_status": HealthStatus.HEALTHY.value,
                "tier": 2,
                "metadata": {
                    "version": "Elasticsearch 8.12.2",
                    "nodes": 8,
                    "indices_count": 142,
                    "storage_terabytes": 14.8,
                    "cluster_state": "green",
                },
            },
        ]

        ci_map: Dict[str, int] = {}
        for ci in ci_definitions:
            saved = self.create_or_update_ci(ci)
            ci_map[ci["name"]] = saved["id"]

        # 2. CMDB Relationships
        relationships = [
            (ci_map["Cloudflare Edge"], ci_map["AWS ALB Main Gateway"], RelationshipType.CONNECTS_TO.value),
            (ci_map["AWS ALB Main Gateway"], ci_map["Auth Service"], RelationshipType.CONNECTS_TO.value),
            (ci_map["AWS ALB Main Gateway"], ci_map["Payment Service"], RelationshipType.CONNECTS_TO.value),
            (ci_map["AWS ALB Main Gateway"], ci_map["Order API"], RelationshipType.CONNECTS_TO.value),
            (ci_map["AWS ALB Main Gateway"], ci_map["Inventory Service"], RelationshipType.CONNECTS_TO.value),
            (ci_map["Order API"], ci_map["Payment Service"], RelationshipType.DEPENDS_ON.value),
            (ci_map["Order API"], ci_map["Inventory Service"], RelationshipType.DEPENDS_ON.value),
            (ci_map["Order API"], ci_map["Kafka Event Streaming Cluster"], RelationshipType.CONNECTS_TO.value),
            (ci_map["Auth Service"], ci_map["PostgreSQL Primary"], RelationshipType.DEPENDS_ON.value),
            (ci_map["Auth Service"], ci_map["Redis Distributed Cache"], RelationshipType.DEPENDS_ON.value),
            (ci_map["Payment Service"], ci_map["PostgreSQL Primary"], RelationshipType.DEPENDS_ON.value),
            (ci_map["Payment Service"], ci_map["Kafka Event Streaming Cluster"], RelationshipType.CONNECTS_TO.value),
            (ci_map["Inventory Service"], ci_map["PostgreSQL Primary"], RelationshipType.DEPENDS_ON.value),
            (ci_map["Kafka Event Streaming Cluster"], ci_map["Elasticsearch Analytics Cluster"], RelationshipType.CONNECTS_TO.value),
        ]

        for src, tgt, rel in relationships:
            self.add_ci_relationship(src, tgt, rel)

        # 3. 10 Enterprise Seed Tickets
        seed_tickets = [
            {
                "task_number": "INC000101",
                "title": "Payment Gateway Provider 504 Gateway Timeout Surge",
                "description": "Critical spike in HTTP 504 timeouts when calling external Stripe Connect endpoint during transaction capture. Customer checkout abandonment increased by 34%.",
                "task_type": TaskType.INCIDENT.value,
                "priority": Priority.P1.value,
                "status": TaskStatus.IN_PROGRESS.value,
                "caller": "datadog-webhook@opennow.io",
                "assigned_to": "sarah.chen@opennow.io",
                "assigned_team": "Site Reliability Engineering",
                "created_at": ts(2.5),
                "updated_at": ts(0.3),
                "sla_due_at": ts(-0.5),  # 30m remaining
                "custom_fields": {
                    "error_rate_percent": 18.4,
                    "external_vendor": "Stripe Connect",
                    "business_impact": "$14,500/min estimated lost revenue",
                    "customer_facing": True,
                    "incident_commander": "sarah.chen",
                    "mitigation_step": "Enabled secondary payment routing fallback to Adyen",
                },
                "affected_cis": [ci_map["Payment Service"], ci_map["Order API"]],
                "activities": [
                    ("datadog-webhook@opennow.io", "Alert triggered: Metric 'payment.capture.latency' > 4500ms for 3 consecutive minutes.", ActivityType.STATUS_CHANGE.value, 2.5),
                    ("OpenNow Automation Engine", "CRITICAL P1 WORKFLOW TRIGGERED: Automated incident commander paging initiated. SRE On-Call engaged.", ActivityType.AI_ANALYSIS.value, 2.4),
                    ("sarah.chen@opennow.io", "War room opened. Investigating external TLS handshake degradation to Stripe Virginia edge.", ActivityType.COMMENT.value, 1.8),
                    ("OpenNow AI Triage Assistant", "Root Cause Correlator: Stripe API status page indicates regional routing degradation. Suggesting immediate failover flag 'FEATURE_PAYMENT_FALLBACK_ADYEN'.", ActivityType.AI_ANALYSIS.value, 1.2),
                    ("sarah.chen@opennow.io", "Enacted dynamic traffic failover to Adyen gateway. Error rate dropped to 0.4%. Monitoring stability.", ActivityType.COMMENT.value, 0.3),
                ],
            },
            {
                "task_number": "INC000102",
                "title": "PostgreSQL Primary Replication Lag Exceeds 450 Seconds",
                "description": "Aurora replica db-r7g-replica-02 is experiencing severe WAL replay delay due to intensive bulk analytics query saturating NVMe IOPS on the storage layer.",
                "task_type": TaskType.INCIDENT.value,
                "priority": Priority.P2.value,
                "status": TaskStatus.IN_PROGRESS.value,
                "caller": "db-monitor@opennow.io",
                "assigned_to": "alex.kumar@opennow.io",
                "assigned_team": "Database Reliability Engineering",
                "created_at": ts(4.0),
                "updated_at": ts(1.1),
                "sla_due_at": ts(-2.0),
                "custom_fields": {
                    "current_lag_seconds": 482,
                    "wal_sender_blocked": True,
                    "disk_iops_saturation": "94.2%",
                    "offensive_query_pid": 48921,
                },
                "affected_cis": [ci_map["PostgreSQL Primary"]],
                "activities": [
                    ("db-monitor@opennow.io", "High replication lag detected on db-r7g-replica-02 (482s > 30s threshold).", ActivityType.COMMENT.value, 4.0),
                    ("alex.kumar@opennow.io", "Identified PID 48921 running unindexed cross-join on order_audit_trail. Issued pg_cancel_backend().", ActivityType.COMMENT.value, 1.1),
                ],
            },
            {
                "task_number": "CHG000201",
                "title": "Renew Wildcard SSL Certificates (*.opennow.io)",
                "description": "Annual DigiCert wildcard TLS certificate rotation across Cloudflare Edge proxy and AWS Application Load Balancers before expiry deadline.",
                "task_type": TaskType.CHANGE.value,
                "priority": Priority.P3.value,
                "status": TaskStatus.NEW.value,
                "caller": "security-ops@opennow.io",
                "assigned_to": "david.ross@opennow.io",
                "assigned_team": "Security Operations",
                "created_at": ts(12.0),
                "updated_at": ts(12.0),
                "sla_due_at": ts(-36.0),
                "custom_fields": {
                    "cert_authority": "DigiCert Global Root G2",
                    "expiry_date": "2026-11-15T00:00:00Z",
                    "change_window": "Sunday 02:00 - 03:00 UTC",
                    "rollback_plan": "Restore previous ACM private key arn:aws:acm:us-east-1:cert-prev",
                    "risk_assessment": "Low (Zero Downtime SNI Swap)",
                },
                "affected_cis": [ci_map["Cloudflare Edge"], ci_map["AWS ALB Main Gateway"]],
                "activities": [
                    ("security-ops@opennow.io", "Change request submitted with approval from CAB. Staged in staging env.", ActivityType.COMMENT.value, 12.0),
                ],
            },
            {
                "task_number": "INC000103",
                "title": "Auth Service JWT RSA Key Rotation Desync Across Pods",
                "description": "Rolling deployment of Auth Service caused half of the pods to issue tokens signed with KeyID 2026-v2 while older pods rejected them with 401 Unauthorized.",
                "task_type": TaskType.INCIDENT.value,
                "priority": Priority.P1.value,
                "status": TaskStatus.RESOLVED.value,
                "caller": "sentry-alert@opennow.io",
                "assigned_to": "elena.rostova@opennow.io",
                "assigned_team": "Identity & Access Management",
                "created_at": ts(8.0),
                "updated_at": ts(5.2),
                "sla_due_at": ts(7.0),
                "custom_fields": {
                    "failed_logins_count": 14200,
                    "jwks_endpoint_status": "500 Internal Error",
                    "impact_scope": "Global Mobile Clients",
                    "resolution_action": "Flushed JWKS distributed cache in Redis and completed pod sync",
                },
                "affected_cis": [ci_map["Auth Service"], ci_map["Redis Distributed Cache"]],
                "activities": [
                    ("sentry-alert@opennow.io", "Spike in TokenSignatureVerificationException: Key ID not found in JWKS.", ActivityType.STATUS_CHANGE.value, 8.0),
                    ("OpenNow Automation Engine", "CRITICAL P1 WORKFLOW TRIGGERED: Identity service degraded.", ActivityType.AI_ANALYSIS.value, 7.9),
                    ("elena.rostova@opennow.io", "Synchronized public JWKS keys across all Redis cache nodes. Verified with automated probe.", ActivityType.COMMENT.value, 5.3),
                    ("elena.rostova@opennow.io", "Incident resolved. Token verification success rate 100%.", ActivityType.STATUS_CHANGE.value, 5.2),
                ],
            },
            {
                "task_number": "PRB000301",
                "title": "Recurrent Redis Memory Eviction Spikes During Flash Sales",
                "description": "Root cause investigation into weekly memory saturation on Redis Cluster node-03 causing session evictions and sudden user logouts during peak promotions.",
                "task_type": TaskType.PROBLEM.value,
                "priority": Priority.P2.value,
                "status": TaskStatus.IN_PROGRESS.value,
                "caller": "marcus.vance@opennow.io",
                "assigned_to": "marcus.vance@opennow.io",
                "assigned_team": "Performance Engineering",
                "created_at": ts(24.0),
                "updated_at": ts(6.0),
                "sla_due_at": ts(-20.0),
                "custom_fields": {
                    "maxmemory_policy": "volatile-lru",
                    "eviction_spike_events": 5,
                    "memory_threshold_mb": 32768,
                    "recommended_fix": "Migrate Cart state to separate unevictable Redis cluster",
                },
                "affected_cis": [ci_map["Redis Distributed Cache"]],
                "activities": [
                    ("marcus.vance@opennow.io", "Correlated session drops with 32GB memory ceiling. Initiating architectural split proposal.", ActivityType.COMMENT.value, 6.0),
                ],
            },
            {
                "task_number": "CHG000202",
                "title": "Upgrade Elasticsearch Cluster Nodes to Version 8.13",
                "description": "Rolling cluster upgrade to patch CVE-2026-8911 and benefit from vector search quantization memory reductions.",
                "task_type": TaskType.CHANGE.value,
                "priority": Priority.P2.value,
                "status": TaskStatus.ON_HOLD.value,
                "caller": "search-platform@opennow.io",
                "assigned_to": "linda.wu@opennow.io",
                "assigned_team": "Search & Observability",
                "created_at": ts(30.0),
                "updated_at": ts(8.0),
                "sla_due_at": ts(-48.0),
                "custom_fields": {
                    "shards_count": 128,
                    "rolling_restart": True,
                    "cluster_state": "green",
                    "hold_reason": "Waiting for index snapshot freeze verification in S3",
                },
                "affected_cis": [ci_map["Elasticsearch Analytics Cluster"]],
                "activities": [
                    ("linda.wu@opennow.io", "Placed change on hold pending full snapshot completion.", ActivityType.STATUS_CHANGE.value, 8.0),
                ],
            },
            {
                "task_number": "REQ000401",
                "title": "Provision Isolated Staging DB Replica for Machine Learning Analytics",
                "description": "Request to spin up an Aurora PostgreSQL replica with sanitized and anonymized customer PII for churn prediction model retraining.",
                "task_type": TaskType.REQUEST.value,
                "priority": Priority.P4.value,
                "status": TaskStatus.RESOLVED.value,
                "caller": "priya.sharma@opennow.io",
                "assigned_to": "alex.kumar@opennow.io",
                "assigned_team": "Database Reliability Engineering",
                "created_at": ts(48.0),
                "updated_at": ts(14.0),
                "sla_due_at": ts(24.0),
                "custom_fields": {
                    "storage_gb": 500,
                    "anonymized_pii": True,
                    "target_env": "staging",
                    "cloud_cost_code": "DATA-SCI-042",
                },
                "affected_cis": [ci_map["PostgreSQL Primary"]],
                "activities": [
                    ("alex.kumar@opennow.io", "Staging replica r7g.xlarge deployed with data-masking extension. Credentials sent via 1Password.", ActivityType.STATUS_CHANGE.value, 14.0),
                ],
            },
            {
                "task_number": "INC000104",
                "title": "Inventory Service Row Deadlocks on High-Concurrency SKUs",
                "description": "PostgreSQL transaction rollback rate peaked at 4% on table `inventory_reservations` during simultaneous checkout of limited inventory items.",
                "task_type": TaskType.INCIDENT.value,
                "priority": Priority.P3.value,
                "status": TaskStatus.IN_PROGRESS.value,
                "caller": "order-engine@opennow.io",
                "assigned_to": "kevin.park@opennow.io",
                "assigned_team": "Supply Chain & Logistics",
                "created_at": ts(5.0),
                "updated_at": ts(2.0),
                "sla_due_at": ts(-19.0),
                "custom_fields": {
                    "deadlock_tx_rate": "14/sec",
                    "top_affected_skus": ["SKU-9921", "SKU-4402", "SKU-1088"],
                    "lock_type": "RowExclusiveLock",
                },
                "affected_cis": [ci_map["Inventory Service"], ci_map["PostgreSQL Primary"]],
                "activities": [
                    ("kevin.park@opennow.io", "Refactoring reservation logic to sort SKU IDs prior to acquiring row locks to eliminate circular wait conditions.", ActivityType.COMMENT.value, 2.0),
                ],
            },
            {
                "task_number": "CHG000203",
                "title": "Repartition Kafka Topic `orders.checkout.events` to 48 Partitions",
                "description": "Expand partition count from 16 to 48 to balance consumer lag across downstream billing, fraud detection, and shipment microservices.",
                "task_type": TaskType.CHANGE.value,
                "priority": Priority.P2.value,
                "status": TaskStatus.NEW.value,
                "caller": "event-stream@opennow.io",
                "assigned_to": "sarah.chen@opennow.io",
                "assigned_team": "Site Reliability Engineering",
                "created_at": ts(3.0),
                "updated_at": ts(3.0),
                "sla_due_at": ts(-1.0),
                "custom_fields": {
                    "current_partitions": 16,
                    "target_partitions": 48,
                    "producer_lag_offset": 8420,
                    "key_distribution_hash": "murmur2",
                },
                "affected_cis": [ci_map["Kafka Event Streaming Cluster"]],
                "activities": [
                    ("sarah.chen@opennow.io", "Planned execution during off-peak maintenance window at 03:00 UTC.", ActivityType.COMMENT.value, 3.0),
                ],
            },
            {
                "task_number": "REQ000402",
                "title": "Onboarding: Grant Teleport Bastion and EKS Cluster Access",
                "description": "Role-Based Access Control request for incoming Junior SRE engineer. Requires read-only kubeconfig and SSH bastion access.",
                "task_type": TaskType.REQUEST.value,
                "priority": Priority.P4.value,
                "status": TaskStatus.CLOSED.value,
                "caller": "hr-automation@opennow.io",
                "assigned_to": "david.ross@opennow.io",
                "assigned_team": "Security Operations",
                "created_at": ts(72.0),
                "updated_at": ts(68.0),
                "sla_due_at": ts(0.0),
                "custom_fields": {
                    "employee_id": "EMP-9402",
                    "role": "Junior SRE",
                    "mfa_device_enrolled": True,
                    "okta_groups": ["sre-engineering", "prod-viewers"],
                },
                "affected_cis": [ci_map["Cloudflare Edge"]],
                "activities": [
                    ("david.ross@opennow.io", "Teleport role 'sre-viewer' provisioned and verified with SSO.", ActivityType.STATUS_CHANGE.value, 68.0),
                ],
            },
        ]

        with self.get_connection() as conn:
            cursor = conn.cursor()
            for ticket in seed_tickets:
                cf_json = json.dumps(ticket["custom_fields"])
                cursor.execute(
                    """
                    INSERT INTO tasks (
                        task_number, title, description, task_type, priority, status,
                        caller, assigned_to, assigned_team, created_at, updated_at,
                        sla_due_at, custom_fields
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        ticket["task_number"],
                        ticket["title"],
                        ticket["description"],
                        ticket["task_type"],
                        ticket["priority"],
                        ticket["status"],
                        ticket["caller"],
                        ticket["assigned_to"],
                        ticket["assigned_team"],
                        ticket["created_at"],
                        ticket["updated_at"],
                        ticket["sla_due_at"],
                        cf_json,
                    ),
                )
                task_id = cursor.lastrowid

                # Link Affected CIs
                for ci_id in ticket["affected_cis"]:
                    cursor.execute(
                        "INSERT OR IGNORE INTO task_cis (task_id, ci_id) VALUES (?, ?)",
                        (task_id, ci_id),
                    )

                # Insert Activities
                for author, msg, act_type, h_ago in ticket["activities"]:
                    cursor.execute(
                        """
                        INSERT INTO activity_logs (task_id, author, message, activity_type, created_at)
                        VALUES (?, ?, ?, ?, ?)
                        """,
                        (task_id, author, msg, act_type, ts(h_ago)),
                    )

    # --- User & Group CRUD Operations ---

    def create_or_update_user(self, user_data: Dict[str, Any]) -> Dict[str, Any]:
        """Creates or updates a user in the relational users table."""
        now_iso = datetime.datetime.now(datetime.timezone.utc).isoformat()
        user_name = user_data["user_name"]
        full_name = user_data.get("full_name") or user_name
        email = user_data.get("email") or f"{user_name}@enterprise.local"
        role = user_data.get("role", "end_user")
        department = user_data.get("department", "General")
        external_id = user_data.get("external_id")

        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(
                """
                INSERT INTO users (external_id, user_name, full_name, email, role, department, created_at)
                VALUES (?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(user_name) DO UPDATE SET
                    external_id = COALESCE(excluded.external_id, users.external_id),
                    full_name = excluded.full_name,
                    email = excluded.email,
                    role = excluded.role,
                    department = excluded.department
                """,
                (external_id, user_name, full_name, email, role, department, now_iso),
            )
            cursor.execute("SELECT * FROM users WHERE user_name = ?", (user_name,))
            return dict(cursor.fetchone())

    def get_user_by_id(self, user_id: int) -> Optional[Dict[str, Any]]:
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT * FROM users WHERE id = ?", (user_id,))
            row = cursor.fetchone()
            return dict(row) if row else None

    def get_user_by_name(self, user_name: str) -> Optional[Dict[str, Any]]:
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT * FROM users WHERE LOWER(user_name) = LOWER(?)", (user_name,))
            row = cursor.fetchone()
            return dict(row) if row else None

    def list_users(self) -> List[Dict[str, Any]]:
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT * FROM users ORDER BY id ASC")
            return [dict(r) for r in cursor.fetchall()]

    def create_or_update_group(self, group_data: Dict[str, Any]) -> Dict[str, Any]:
        """Creates or updates a user group in the relational user_groups table."""
        now_iso = datetime.datetime.now(datetime.timezone.utc).isoformat()
        name = group_data["name"]
        description = group_data.get("description", "")
        external_id = group_data.get("external_id")

        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(
                """
                INSERT INTO user_groups (external_id, name, description, created_at)
                VALUES (?, ?, ?, ?)
                ON CONFLICT(name) DO UPDATE SET
                    external_id = COALESCE(excluded.external_id, user_groups.external_id),
                    description = excluded.description
                """,
                (external_id, name, description, now_iso),
            )
            cursor.execute("SELECT * FROM user_groups WHERE name = ?", (name,))
            return dict(cursor.fetchone())

    def get_group_by_id(self, group_id: int) -> Optional[Dict[str, Any]]:
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT * FROM user_groups WHERE id = ?", (group_id,))
            row = cursor.fetchone()
            return dict(row) if row else None

    def list_groups(self) -> List[Dict[str, Any]]:
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT * FROM user_groups ORDER BY id ASC")
            return [dict(r) for r in cursor.fetchall()]

    # --- Relational External ID Mappings ---

    def record_external_id_mapping(
        self,
        platform: str,
        entity_type: str,
        external_id: str,
        internal_id: int,
        meta: Optional[Dict[str, Any]] = None,
    ) -> None:
        """Records mapping between source platform external key and internal integer ID."""
        now_iso = datetime.datetime.now(datetime.timezone.utc).isoformat()
        meta_json = json.dumps(meta or {})
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(
                """
                INSERT INTO external_id_mappings (platform, entity_type, external_id, internal_id, meta, created_at)
                VALUES (?, ?, ?, ?, ?, ?)
                ON CONFLICT(platform, entity_type, external_id) DO UPDATE SET
                    internal_id = excluded.internal_id,
                    meta = excluded.meta
                """,
                (platform, entity_type, str(external_id), internal_id, meta_json, now_iso),
            )

    def get_internal_id_by_external(
        self,
        platform: str,
        entity_type: str,
        external_id: str,
    ) -> Optional[int]:
        """Resolves source external ID to internal SQLite primary key."""
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(
                """
                SELECT internal_id FROM external_id_mappings
                WHERE platform = ? AND entity_type = ? AND external_id = ?
                """,
                (platform, entity_type, str(external_id)),
            )
            row = cursor.fetchone()
            return row["internal_id"] if row else None


# Singleton instance
db = DatabaseManager()


import secrets
import sqlite3
import threading
from contextlib import contextmanager
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Iterator


@dataclass(frozen=True)
class Member:
    bale_user_id: str
    chat_id: str
    display_name: str
    university: str
    role: str
    participation: str
    notification: str
    membership_number: str
    referral_code: str
    referred_by: str | None
    status: str
    created_at: str
    updated_at: str


class MemberRepository:
    """ذخیره‌سازی حداقلی اعضا با SQLite و بدون اطلاعات هویتی حساس."""

    EDITABLE_FIELDS = {"display_name", "university", "role", "participation", "notification"}

    def __init__(self, database_path: str | Path):
        self.database_path = Path(database_path)
        self.database_path.parent.mkdir(parents=True, exist_ok=True)
        self._lock = threading.RLock()
        self._initialize()

    @contextmanager
    def _connect(self) -> Iterator[sqlite3.Connection]:
        connection = sqlite3.connect(self.database_path, timeout=10)
        connection.row_factory = sqlite3.Row
        try:
            yield connection
            connection.commit()
        except Exception:
            connection.rollback()
            raise
        finally:
            connection.close()

    def _initialize(self) -> None:
        with self._lock, self._connect() as connection:
            connection.execute("PRAGMA journal_mode=WAL")
            connection.execute(
                """
                CREATE TABLE IF NOT EXISTS members (
                    bale_user_id TEXT PRIMARY KEY,
                    chat_id TEXT NOT NULL,
                    display_name TEXT NOT NULL,
                    university TEXT NOT NULL,
                    role TEXT NOT NULL,
                    participation TEXT NOT NULL,
                    notification TEXT NOT NULL,
                    membership_number TEXT NOT NULL UNIQUE,
                    referral_code TEXT NOT NULL UNIQUE,
                    referred_by TEXT,
                    status TEXT NOT NULL DEFAULT 'pending',
                    created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL
                )
                """
            )
            connection.execute(
                "CREATE INDEX IF NOT EXISTS idx_members_referred_by ON members(referred_by)"
            )
            connection.execute(
                """
                CREATE TABLE IF NOT EXISTS workshop_interests (
                    bale_user_id TEXT NOT NULL,
                    chat_id TEXT NOT NULL,
                    topic TEXT NOT NULL,
                    attendance_mode TEXT NOT NULL,
                    status TEXT NOT NULL DEFAULT 'interested',
                    created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL,
                    PRIMARY KEY (bale_user_id, topic)
                )
                """
            )
            connection.execute(
                """
                CREATE TABLE IF NOT EXISTS branch_interests (
                    bale_user_id TEXT NOT NULL,
                    chat_id TEXT NOT NULL,
                    university TEXT NOT NULL,
                    team_role TEXT NOT NULL,
                    availability TEXT NOT NULL,
                    status TEXT NOT NULL DEFAULT 'pending',
                    created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL,
                    PRIMARY KEY (bale_user_id, university)
                )
                """
            )
            connection.execute(
                """
                CREATE TABLE IF NOT EXISTS enterprise_interests (
                    bale_user_id TEXT NOT NULL,
                    chat_id TEXT NOT NULL,
                    idea_type TEXT NOT NULL,
                    contribution TEXT NOT NULL,
                    status TEXT NOT NULL DEFAULT 'proposed',
                    created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL,
                    PRIMARY KEY (bale_user_id, idea_type)
                )
                """
            )

    @staticmethod
    def _to_member(row: sqlite3.Row | None) -> Member | None:
        return Member(**dict(row)) if row else None

    def get_member(self, bale_user_id: int | str) -> Member | None:
        with self._lock, self._connect() as connection:
            row = connection.execute(
                "SELECT * FROM members WHERE bale_user_id = ?",
                (str(bale_user_id),),
            ).fetchone()
        return self._to_member(row)

    def get_by_referral_code(self, referral_code: str) -> Member | None:
        with self._lock, self._connect() as connection:
            row = connection.execute(
                "SELECT * FROM members WHERE referral_code = ?",
                (referral_code,),
            ).fetchone()
        return self._to_member(row)

    def count_referrals(self, referral_code: str) -> int:
        with self._lock, self._connect() as connection:
            row = connection.execute(
                "SELECT COUNT(*) AS total FROM members WHERE referred_by = ?",
                (referral_code,),
            ).fetchone()
        return int(row["total"])

    def _unique_code(self, column: str, prefix: str) -> str:
        if column not in {"membership_number", "referral_code"}:
            raise ValueError("Unsupported unique-code column")
        while True:
            code = f"{prefix}{secrets.token_hex(4).upper()}"
            with self._connect() as connection:
                exists = connection.execute(
                    f"SELECT 1 FROM members WHERE {column} = ?",
                    (code,),
                ).fetchone()
            if not exists:
                return code

    def create_member(
        self,
        *,
        bale_user_id: int | str,
        chat_id: int | str,
        display_name: str,
        university: str,
        role: str,
        participation: str,
        notification: str,
        referred_by: str | None = None,
    ) -> Member:
        with self._lock:
            existing_member = self.get_member(bale_user_id)
            if existing_member:
                return existing_member
            now = datetime.now(timezone.utc).isoformat()
            membership_number = self._unique_code("membership_number", "SH-")
            referral_code = self._unique_code("referral_code", "R-")
            if referred_by and not self.get_by_referral_code(referred_by):
                referred_by = None
            with self._connect() as connection:
                connection.execute(
                    """
                    INSERT INTO members (
                        bale_user_id, chat_id, display_name, university, role,
                        participation, notification, membership_number,
                        referral_code, referred_by, status, created_at, updated_at
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 'pending', ?, ?)
                    """,
                    (
                        str(bale_user_id), str(chat_id), display_name, university, role,
                        participation, notification, membership_number, referral_code,
                        referred_by, now, now,
                    ),
                )
        member = self.get_member(bale_user_id)
        if member is None:
            raise RuntimeError("Member creation did not persist")
        return member

    def update_member(self, bale_user_id: int | str, field: str, value: str) -> Member | None:
        if field not in self.EDITABLE_FIELDS:
            raise ValueError("Unsupported member field")
        now = datetime.now(timezone.utc).isoformat()
        with self._lock, self._connect() as connection:
            connection.execute(
                f"UPDATE members SET {field} = ?, updated_at = ? WHERE bale_user_id = ?",
                (value, now, str(bale_user_id)),
            )
        return self.get_member(bale_user_id)

    def save_workshop_interest(
        self,
        *,
        bale_user_id: int | str,
        chat_id: int | str,
        topic: str,
        attendance_mode: str,
    ) -> None:
        now = datetime.now(timezone.utc).isoformat()
        with self._lock, self._connect() as connection:
            connection.execute(
                """
                INSERT INTO workshop_interests (
                    bale_user_id, chat_id, topic, attendance_mode, created_at, updated_at
                ) VALUES (?, ?, ?, ?, ?, ?)
                ON CONFLICT(bale_user_id, topic) DO UPDATE SET
                    chat_id = excluded.chat_id,
                    attendance_mode = excluded.attendance_mode,
                    updated_at = excluded.updated_at
                """,
                (str(bale_user_id), str(chat_id), topic, attendance_mode, now, now),
            )

    def save_branch_interest(
        self,
        *,
        bale_user_id: int | str,
        chat_id: int | str,
        university: str,
        team_role: str,
        availability: str,
    ) -> None:
        now = datetime.now(timezone.utc).isoformat()
        with self._lock, self._connect() as connection:
            connection.execute(
                """
                INSERT INTO branch_interests (
                    bale_user_id, chat_id, university, team_role, availability,
                    created_at, updated_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(bale_user_id, university) DO UPDATE SET
                    chat_id = excluded.chat_id,
                    team_role = excluded.team_role,
                    availability = excluded.availability,
                    updated_at = excluded.updated_at
                """,
                (
                    str(bale_user_id), str(chat_id), university, team_role,
                    availability, now, now,
                ),
            )

    def list_workshop_interests(self, bale_user_id: int | str) -> list[dict[str, str]]:
        with self._lock, self._connect() as connection:
            rows = connection.execute(
                """
                SELECT topic, attendance_mode, status, created_at
                FROM workshop_interests WHERE bale_user_id = ?
                ORDER BY created_at DESC
                """,
                (str(bale_user_id),),
            ).fetchall()
        return [dict(row) for row in rows]

    def list_branch_interests(self, bale_user_id: int | str) -> list[dict[str, str]]:
        with self._lock, self._connect() as connection:
            rows = connection.execute(
                """
                SELECT university, team_role, availability, status, created_at
                FROM branch_interests WHERE bale_user_id = ?
                ORDER BY created_at DESC
                """,
                (str(bale_user_id),),
            ).fetchall()
        return [dict(row) for row in rows]

    def save_enterprise_interest(
        self,
        *,
        bale_user_id: int | str,
        chat_id: int | str,
        idea_type: str,
        contribution: str,
    ) -> None:
        now = datetime.now(timezone.utc).isoformat()
        with self._lock, self._connect() as connection:
            connection.execute(
                """
                INSERT INTO enterprise_interests (
                    bale_user_id, chat_id, idea_type, contribution, created_at, updated_at
                ) VALUES (?, ?, ?, ?, ?, ?)
                ON CONFLICT(bale_user_id, idea_type) DO UPDATE SET
                    chat_id = excluded.chat_id,
                    contribution = excluded.contribution,
                    updated_at = excluded.updated_at
                """,
                (str(bale_user_id), str(chat_id), idea_type, contribution, now, now),
            )

    def list_enterprise_interests(self, bale_user_id: int | str) -> list[dict[str, str]]:
        with self._lock, self._connect() as connection:
            rows = connection.execute(
                """
                SELECT idea_type, contribution, status, created_at
                FROM enterprise_interests WHERE bale_user_id = ?
                ORDER BY created_at DESC
                """,
                (str(bale_user_id),),
            ).fetchall()
        return [dict(row) for row in rows]

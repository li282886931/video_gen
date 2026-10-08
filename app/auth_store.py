import hashlib
import hmac
import secrets
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, List, Optional
from uuid import uuid4

from .db import MySQLSettings, ensure_mysql_database, get_mysql_connection
from .task_store import utc_now


def hash_password(password: str, salt: Optional[str] = None) -> str:
    salt = salt or secrets.token_hex(16)
    digest = hashlib.pbkdf2_hmac("sha256", password.encode("utf-8"), salt.encode("utf-8"), 120_000)
    return f"pbkdf2_sha256${salt}${digest.hex()}"


def verify_password(password: str, password_hash: str) -> bool:
    try:
        algorithm, salt, expected = password_hash.split("$", 2)
    except ValueError:
        return False
    if algorithm != "pbkdf2_sha256":
        return False
    actual = hash_password(password, salt).split("$", 2)[2]
    return hmac.compare_digest(actual, expected)


class MySQLAuthStore:
    def __init__(self, settings: MySQLSettings):
        self.settings = settings
        ensure_mysql_database(settings)
        self.init_schema()
        self.seed_defaults()

    def register(self, username: str, password: str, display_name: str = "", role: str = "user") -> Dict[str, Any]:
        account = {
            "id": f"acct_{uuid4().hex[:12]}",
            "username": username.strip(),
            "display_name": display_name.strip() or username.strip(),
            "role": role,
            "status": "active",
            "created_at": utc_now(),
        }
        with self._connection() as connection:
            with connection.cursor() as cursor:
                cursor.execute("SELECT id FROM accounts WHERE username = %s", (account["username"],))
                if cursor.fetchone():
                    raise ValueError("username_exists")
                cursor.execute(
                    """
                    INSERT INTO accounts
                    (id, username, password_hash, display_name, role, status, created_at)
                    VALUES (%s, %s, %s, %s, %s, %s, %s)
                    """,
                    (
                        account["id"],
                        account["username"],
                        hash_password(password),
                        account["display_name"],
                        account["role"],
                        account["status"],
                        account["created_at"],
                    ),
                )
                cursor.execute(
                    """
                    INSERT INTO wallets (account_id, balance, updated_at)
                    VALUES (%s, %s, %s)
                    ON DUPLICATE KEY UPDATE account_id=account_id
                    """,
                    (account["id"], 0, utc_now()),
                )
            connection.commit()
        return account

    def login(self, username: str, password: str) -> Dict[str, Any]:
        account = self.get_account_by_username(username)
        if not account or not verify_password(password, account["password_hash"]):
            raise PermissionError("invalid_credentials")
        if account["status"] != "active":
            raise PermissionError("account_disabled")
        token = secrets.token_urlsafe(32)
        expires_at = (datetime.now(timezone.utc) + timedelta(days=7)).isoformat()
        with self._connection() as connection:
            with connection.cursor() as cursor:
                cursor.execute(
                    """
                    INSERT INTO sessions (token, account_id, expires_at, created_at)
                    VALUES (%s, %s, %s, %s)
                    """,
                    (token, account["id"], expires_at, utc_now()),
                )
            connection.commit()
        return {"token": token, "token_type": "bearer", "expires_at": expires_at, "user": self._public_account(account)}

    def account_from_token(self, token: str) -> Optional[Dict[str, Any]]:
        with self._connection() as connection:
            with connection.cursor() as cursor:
                cursor.execute(
                    """
                    SELECT a.* FROM sessions s
                    JOIN accounts a ON a.id = s.account_id
                    WHERE s.token = %s AND s.expires_at > %s AND a.status = 'active'
                    """,
                    (token, datetime.now(timezone.utc).isoformat()),
                )
                account = cursor.fetchone()
        return self._public_account(account) if account else None

    def get_account_by_username(self, username: str) -> Optional[Dict[str, Any]]:
        with self._connection() as connection:
            with connection.cursor() as cursor:
                cursor.execute("SELECT * FROM accounts WHERE username = %s", (username.strip(),))
                return cursor.fetchone()

    def wallet(self, account_id: str) -> Dict[str, Any]:
        with self._connection() as connection:
            with connection.cursor() as cursor:
                cursor.execute("SELECT * FROM wallets WHERE account_id = %s", (account_id,))
                wallet = cursor.fetchone()
                if not wallet:
                    cursor.execute(
                        "INSERT INTO wallets (account_id, balance, updated_at) VALUES (%s, %s, %s)",
                        (account_id, 0, utc_now()),
                    )
                    connection.commit()
                    wallet = {"account_id": account_id, "balance": 0, "updated_at": utc_now()}
                cursor.execute(
                    """
                    SELECT id, type, amount, balance_after, note, created_at
                    FROM wallet_transactions
                    WHERE account_id = %s
                    ORDER BY created_at DESC, id DESC
                    LIMIT 50
                    """,
                    (account_id,),
                )
                transactions = [self._transaction_from_row(row) for row in cursor.fetchall()]
        return {
            "account_id": wallet["account_id"],
            "balance": float(wallet["balance"]),
            "updated_at": wallet["updated_at"],
            "transactions": transactions,
        }

    def recharge(self, account_id: str, amount: float, note: str = "") -> Dict[str, Any]:
        if amount <= 0:
            raise ValueError("amount_must_be_positive")
        return self._change_balance(account_id, "recharge", amount, note)

    def consume(self, account_id: str, amount: float, note: str = "") -> Dict[str, Any]:
        if amount <= 0:
            raise ValueError("amount_must_be_positive")
        return self._change_balance(account_id, "consume", -amount, note)

    def init_schema(self) -> None:
        with self._connection() as connection:
            with connection.cursor() as cursor:
                for statement in self._schema_statements():
                    cursor.execute(statement)
            connection.commit()

    def seed_defaults(self) -> None:
        try:
            self.register("local-user", "local-password", "本地用户", role="admin")
        except ValueError:
            return

    def _change_balance(self, account_id: str, transaction_type: str, delta: float, note: str) -> Dict[str, Any]:
        with self._connection() as connection:
            with connection.cursor() as cursor:
                cursor.execute("SELECT balance FROM wallets WHERE account_id = %s FOR UPDATE", (account_id,))
                wallet = cursor.fetchone()
                if not wallet:
                    cursor.execute(
                        "INSERT INTO wallets (account_id, balance, updated_at) VALUES (%s, %s, %s)",
                        (account_id, 0, utc_now()),
                    )
                    balance = 0.0
                else:
                    balance = float(wallet["balance"])
                new_balance = balance + float(delta)
                if new_balance < 0:
                    raise ValueError("insufficient_balance")
                now = utc_now()
                cursor.execute("UPDATE wallets SET balance = %s, updated_at = %s WHERE account_id = %s", (new_balance, now, account_id))
                cursor.execute(
                    """
                    INSERT INTO wallet_transactions
                    (id, account_id, type, amount, balance_after, note, created_at)
                    VALUES (%s, %s, %s, %s, %s, %s, %s)
                    """,
                    (f"txn_{uuid4().hex[:12]}", account_id, transaction_type, abs(delta), new_balance, note, now),
                )
            connection.commit()
        return self.wallet(account_id)

    def _connection(self):
        return get_mysql_connection(self.settings)

    def _public_account(self, account: Dict[str, Any]) -> Dict[str, Any]:
        return {
            "id": account["id"],
            "username": account["username"],
            "display_name": account["display_name"],
            "role": account["role"],
            "status": account["status"],
            "created_at": account["created_at"],
        }

    def _transaction_from_row(self, row: Dict[str, Any]) -> Dict[str, Any]:
        return {
            "id": row["id"],
            "type": row["type"],
            "amount": float(row["amount"]),
            "balance_after": float(row["balance_after"]),
            "note": row["note"],
            "created_at": row["created_at"],
        }

    def _schema_statements(self) -> List[str]:
        return [
            """
            CREATE TABLE IF NOT EXISTS accounts (
              id VARCHAR(64) PRIMARY KEY,
              username VARCHAR(128) NOT NULL UNIQUE,
              password_hash VARCHAR(255) NOT NULL,
              display_name VARCHAR(255) NOT NULL,
              role VARCHAR(64) NOT NULL,
              status VARCHAR(64) NOT NULL,
              created_at VARCHAR(64) NOT NULL
            ) CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci
            """,
            """
            CREATE TABLE IF NOT EXISTS sessions (
              token VARCHAR(128) PRIMARY KEY,
              account_id VARCHAR(64) NOT NULL,
              expires_at VARCHAR(64) NOT NULL,
              created_at VARCHAR(64) NOT NULL,
              INDEX idx_sessions_account_id (account_id),
              CONSTRAINT fk_sessions_account FOREIGN KEY (account_id) REFERENCES accounts(id)
            ) CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci
            """,
            """
            CREATE TABLE IF NOT EXISTS wallets (
              account_id VARCHAR(64) PRIMARY KEY,
              balance DECIMAL(12, 2) NOT NULL DEFAULT 0,
              updated_at VARCHAR(64) NOT NULL,
              CONSTRAINT fk_wallets_account FOREIGN KEY (account_id) REFERENCES accounts(id)
            ) CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci
            """,
            """
            CREATE TABLE IF NOT EXISTS wallet_transactions (
              id VARCHAR(64) PRIMARY KEY,
              account_id VARCHAR(64) NOT NULL,
              type VARCHAR(32) NOT NULL,
              amount DECIMAL(12, 2) NOT NULL,
              balance_after DECIMAL(12, 2) NOT NULL,
              note TEXT NOT NULL,
              created_at VARCHAR(64) NOT NULL,
              INDEX idx_wallet_transactions_account_id (account_id),
              CONSTRAINT fk_wallet_transactions_account FOREIGN KEY (account_id) REFERENCES accounts(id)
            ) CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci
            """,
        ]

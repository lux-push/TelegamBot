import sqlite3
from pathlib import Path
from datetime import datetime

BASE_DIR = Path(__file__).resolve().parent


class Database:
    def __init__(self):
        self.connection = sqlite3.connect(BASE_DIR / "bot_data.db")
        self.cursor = self.connection.cursor()
        self.create_tables()

    def create_tables(self):
        """Создаёт необходимые таблицы"""
        with self.connection:
            self.cursor.execute("""
                CREATE TABLE IF NOT EXISTS applications (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    user_id INTEGER,
                    platform TEXT,
                    citizen TEXT,
                    age_ok INTEGER DEFAULT 0,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            """)

            self.cursor.execute("""
                CREATE TABLE IF NOT EXISTS stats (
                    date TEXT,
                    platform_avito INTEGER DEFAULT 0,
                    platform_kufar INTEGER DEFAULT 0,
                    total INTEGER DEFAULT 0
                )
            """)

            self.cursor.execute("""
                CREATE TABLE IF NOT EXISTS managers (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    chat_id INTEGER UNIQUE
                )
            """)

            self.connection.commit()

    def add_application(self, user_id: int, platform: str, citizen: str, age_ok: int = 1):
        """Добавляет новую заявку"""
        with self.connection:
            self.cursor.execute(
                "INSERT INTO applications (user_id, platform, citizen, age_ok) VALUES (?, ?, ?, ?)",
                (user_id, platform, citizen, age_ok)
            )

            if age_ok:
                today = datetime.now().strftime("%Y-%m-%d")
                self.cursor.execute(
                    "INSERT OR IGNORE INTO stats (date) VALUES (?)",
                    (today,)
                )
                if platform == "Авито":
                    self.cursor.execute(
                        "UPDATE stats SET platform_avito = platform_avito + 1, total = total + 1 WHERE date = ?",
                        (today,)
                    )
                else:
                    self.cursor.execute(
                        "UPDATE stats SET platform_kufar = platform_kufar + 1, total = total + 1 WHERE date = ?",
                        (today,)
                    )

            self.connection.commit()

    def get_applications_count(self) -> int:
        """Возвращает общее количество заявок"""
        with self.connection:
            result = self.cursor.execute("SELECT COUNT(*) FROM applications").fetchone()
            return result[0] if result else 0

    def get_today_stats(self) -> dict:
        """Статистика за сегодня"""
        today = datetime.now().strftime("%Y-%m-%d")
        with self.connection:
            result = self.cursor.execute(
                "SELECT platform_avito, platform_kufar, total FROM stats WHERE date = ?",
                (today,)
            ).fetchone()
            return {
                "avito": result[0] if result else 0,
                "kufar": result[1] if result else 0,
                "total": result[2] if result else 0
            }

    def add_manager(self, chat_id: int) -> bool:
        """Добавляет менеджера по chat_id. True если добавлен новый."""
        with self.connection:
            cur = self.cursor.execute(
                "INSERT OR IGNORE INTO managers (chat_id) VALUES (?)",
                (chat_id,)
            )
            self.connection.commit()
            return cur.rowcount > 0

    def delete_manager(self, chat_id: int) -> bool:
        """Удаляет менеджера по chat_id. True если был удалён."""
        with self.connection:
            cur = self.cursor.execute(
                "DELETE FROM managers WHERE chat_id = ?",
                (chat_id,)
            )
            self.connection.commit()
            return cur.rowcount > 0

    def get_managers(self):
        """Возвращает всех менеджеров"""
        with self.connection:
            return self.cursor.execute(
                "SELECT chat_id FROM managers ORDER BY id DESC"
            ).fetchall()

    def clear_applications(self, platform: str | None = None) -> int:
        """
        Удаляет заявки из таблицы applications.

        :param platform:
            - "Авито" — очистить только Авито
            - "Куфар" — очистить только Куфар
            - None — очистить все заявки
        :return: количество удалённых заявок
        """
        with self.connection:
            if platform is not None:
                cur = self.cursor.execute(
                    "DELETE FROM applications WHERE platform = ?",
                    (platform,)
                )
            else:
                cur = self.cursor.execute("DELETE FROM applications")

            self.connection.commit()
            return cur.rowcount

    def close(self):
        self.connection.close()
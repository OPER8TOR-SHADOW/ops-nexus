import sqlite3
from pathlib import Path

from .schema import SCHEMA


DATABASE = Path(__file__).parent / "ops_nexus.db"


class Database:

    def __init__(self):

        self.connection = sqlite3.connect(DATABASE)

        self.connection.row_factory = sqlite3.Row

        self.cursor = self.connection.cursor()

    def create(self):

        self.cursor.executescript(SCHEMA)

        self.connection.commit()

    def execute(self, sql, params=()):

        self.cursor.execute(sql, params)

        self.connection.commit()

    def fetchone(self, sql, params=()):

        return self.cursor.execute(sql, params).fetchone()

    def fetchall(self, sql, params=()):

        return self.cursor.execute(sql, params).fetchall()

    def close(self):

        self.connection.close()
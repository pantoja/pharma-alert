import sqlite3
from datetime import datetime
import os

class Database:
    def __init__(self, db_name="prices.db"):
        self.db_path = os.path.join(os.path.dirname(os.path.dirname(__file__)), db_name)
        self.init_db()

    def init_db(self):
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS price_history (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    timestamp DATETIME,
                    pharmacy TEXT,
                    product_name TEXT,
                    unit_price REAL,
                    total_price REAL,
                    shipping_cost REAL,
                    total_effective_price REAL,
                    is_kit BOOLEAN,
                    kit_size INTEGER,
                    is_best_offer BOOLEAN
                )
            """)
            # Tenta adicionar a coluna total_price caso a tabela já exista sem ela
            try:
                cursor.execute("ALTER TABLE price_history ADD COLUMN total_price REAL")
            except sqlite3.OperationalError:
                pass # Coluna já existe ou tabela nova
            conn.commit()

    def save_price(self, pharmacy, product_name, unit_price, total_price, shipping_cost, total_effective_price, is_kit=False, kit_size=1, is_best_offer=False):
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()
            cursor.execute("""
                INSERT INTO price_history 
                (timestamp, pharmacy, product_name, unit_price, total_price, shipping_cost, total_effective_price, is_kit, kit_size, is_best_offer)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (datetime.now(), pharmacy, product_name, unit_price, total_price, shipping_cost, total_effective_price, is_kit, kit_size, is_best_offer))
            conn.commit()

    def get_last_price(self, pharmacy, product_name):
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()
            cursor.execute("""
                SELECT total_effective_price FROM price_history 
                WHERE pharmacy = ? AND product_name = ?
                ORDER BY timestamp DESC LIMIT 1
            """, (pharmacy, product_name))
            result = cursor.fetchone()
            return result[0] if result else None

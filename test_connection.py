"""Test MySQL connection"""

import os
from urllib.parse import urlparse, unquote

from dotenv import load_dotenv
import pymysql

load_dotenv()

db_url = os.getenv("DATABASE_URL")
print(f"Connection String: {db_url}\n")

try:
    if not db_url:
        raise ValueError("DATABASE_URL is not set in .env")

    parsed = urlparse(db_url)
    conn = pymysql.connect(
        host=parsed.hostname or "localhost",
        port=parsed.port or 3306,
        user=unquote(parsed.username or ""),
        password=unquote(parsed.password or ""),
        database=(parsed.path or "").lstrip("/"),
        charset="utf8mb4",
    )
    
    print("MySQL Connection Successful!")
    
    # Verify database
    cursor = conn.cursor()
    cursor.execute("SHOW TABLES;")
    tables = cursor.fetchall()
    
    print(f"Tables in database: {len(tables)}")
    for table in tables:
        print(f"  - {table[0]}")
    
    cursor.close()
    conn.close()
    
except Exception as e:
    print(f"Connection Failed: {e}")
    print("\nTroubleshooting:")
    print("1. Check MySQL is running (Services -> MySQL80)")
    print("2. Verify DATABASE_URL in .env has the correct URL-encoded password")
    print("3. Verify database exists: violence_detection_db")

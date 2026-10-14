#!/usr/bin/env python3
"""
UniGlide Food Delivery Bot - Production Entrypoint
Runs live using:
    python main.py
"""
import os
import sys
import asyncio
from dotenv import load_dotenv

load_dotenv()

# Automatically ensure parent directory for SQLite database exists
db_path = os.getenv("DB_PATH", "data/bot_database.db")
db_dir = os.path.dirname(db_path)
if db_dir:
    os.makedirs(db_dir, exist_ok=True)

import database as db
import bot

def main():
    asyncio.run(db.init_db())
    bot.main()

if __name__ == "__main__":
    main()

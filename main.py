#!/usr/bin/env python3
"""
UniGlide Food Delivery Bot - Production Entrypoint
Runs bot whether executed from root workspace directory or child project folder.
"""
import os
import sys
import asyncio

current_dir = os.path.dirname(os.path.abspath(__file__))
anbo_dir = os.path.join(current_dir, "anbo")

if current_dir not in sys.path:
    sys.path.insert(0, current_dir)

# Prioritize anbo directory in path and as working directory if it exists
if os.path.exists(anbo_dir):
    if anbo_dir not in sys.path:
        sys.path.insert(0, anbo_dir)
    os.chdir(anbo_dir)

from dotenv import load_dotenv
# Load .env from anbo directory and workspace root
if os.path.exists(os.path.join(current_dir, ".env")):
    load_dotenv(os.path.join(current_dir, ".env"))
if os.path.exists(os.path.join(anbo_dir, ".env")):
    load_dotenv(os.path.join(anbo_dir, ".env"))
load_dotenv()

# Automatically ensure parent directory for SQLite database exists
db_path = os.getenv("DB_PATH", "data/bot_database.db")
db_dir = os.path.dirname(db_path)
if db_dir:
    os.makedirs(db_dir, exist_ok=True)

from anbo import database as db
from anbo import bot

def main():
    asyncio.run(db.init_db())
    bot.main()

if __name__ == "__main__":
    main()


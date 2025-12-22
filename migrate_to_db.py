#!/usr/bin/env python3
"""
Migration script to transfer existing JSON data to the SQLite database.
Run this once to migrate your existing data.
"""

import db

if __name__ == "__main__":
    print("=" * 60)
    print("BLG Exam - JSON to SQLite Migration Script")
    print("=" * 60)
    print()
    print("This script will migrate your existing JSON data to SQLite.")
    print()
    
    response = input("Do you want to proceed with migration? (yes/no): ").strip().lower()
    if response not in ['yes', 'y']:
        print("Migration cancelled.")
        exit(0)
    
    print()
    print("Starting migration...")
    print("-" * 60)
    
    db.migrate_from_json()
    
    print("-" * 60)
    print()
    print("Migration complete!")
    print()
    print("IMPORTANT: Your original JSON files have NOT been deleted.")
    print("You can now safely use the application with the new database.")
    print()
    print("To verify the migration, you can:")
    print("1. Start the application: python3 app.py")
    print("2. Log in with your existing credentials")
    print("3. Check that your pools and progress are still there")
    print()
    print("=" * 60)

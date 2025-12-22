# Database Migration - SQLite Implementation

## Overview

The BLG Exam application has been upgraded from JSON file storage to a proper SQLite database. This fixes several critical issues including:

1. **Session Bug Fix**: Uploaded problem sets now correctly persist and are used in sessions (instead of always defaulting to the built-in set)
2. **Data Integrity**: Proper database constraints prevent data corruption
3. **Performance**: Faster queries and better concurrent access
4. **Reliability**: ACID transactions ensure data consistency

## What Changed

### Before (JSON Files)
- Users stored in: `data/users.json`
- Pools stored in: `data/pools.json` and `data/pools_{username}.json`
- Progress stored in: `data/progress_{pool_id}.json`
- Gamestates stored in: `data/gamestate_{user_id}.json`
- Sessions stored in: In-memory dictionary (lost on restart)

### After (SQLite Database)
- All data centralized in: `data/blg_exam.db`
- Tables: `users`, `pools`, `progress`, `gamestates`, `sessions`
- Proper foreign keys and constraints
- Persistent sessions (survive server restarts)
- Better query performance with indexes

## Database Schema

### Users Table
```sql
- username (PRIMARY KEY)
- password_hash
- created_at
```

### Pools Table
```sql
- id (PRIMARY KEY)
- username (FOREIGN KEY to users)
- orig_name
- file_path
- created_at
```

### Progress Table
```sql
- id (AUTO INCREMENT)
- username (FOREIGN KEY to users)
- pool_id (FOREIGN KEY to pools)
- question_id
- box, correct_streak, incorrect_count
- last_seen, due, updated_at
- UNIQUE(username, pool_id, question_id)
```

### Gamestates Table
```sql
- username (PRIMARY KEY, FOREIGN KEY to users)
- points, rank, answer_streak, daily_streak
- last_active
- badges (JSON), history (JSON)
```

### Sessions Table
```sql
- sid (PRIMARY KEY)
- username (FOREIGN KEY to users)
- pool_id (FOREIGN KEY to pools)
- pool_data, exam_set, wrong_set (JSON)
- current_index, num_questions
- progress_data (JSON)
- created_at, updated_at
```

## Migration Instructions

### Option 1: Automatic Migration (Recommended)

Run the migration script to automatically transfer your existing data:

```bash
python3 migrate_to_db.py
```

This will:
- Create the SQLite database
- Migrate all users from `data/users.json`
- Migrate all pools from `data/pools.json`
- Migrate user-specific pools from `data/pools_{username}.json`
- Preserve all your existing data

### Option 2: Fresh Start

If you don't have existing data or want to start fresh:

```bash
python3 db.py
```

This initializes an empty database.

## Verification

After migration, verify everything works:

1. Start the application:
   ```bash
   python3 app.py
   ```

2. Log in with your existing credentials

3. Check that:
   - Your uploaded problem sets appear in the pools list
   - You can start a quiz with an uploaded set
   - The uploaded set is actually used (not the default set)
   - Your progress is preserved
   - Your points and rank are correct

## Bug Fix Details

### The Session Problem Set Bug

**Before**: When you uploaded a problem set and started a quiz, the system would:
1. Save the pool metadata to JSON files
2. Read the pool ID into the session
3. BUT when loading questions, it would sometimes fall back to the default set due to race conditions or missing session data

**After**: With the database:
1. Pool is saved with a unique ID and proper foreign keys
2. Session is created with explicit `pool_id` reference
3. Database ensures the session always has the correct pool
4. Foreign key constraints prevent orphaned sessions

## Rollback (If Needed)

If you need to rollback to the JSON-based system:

1. Stop the application
2. Restore the original `webgui.py` from git history
3. Delete `data/blg_exam.db`
4. Restart the application

However, the database version is more reliable and we recommend keeping it.

## Technical Details

### File Changes
- `db.py` - New database module with all SQL operations
- `webgui.py` - Updated to use database instead of JSON files
- `migrate_to_db.py` - Migration script

### Dependencies
No new dependencies! SQLite is built into Python's standard library.

### Performance
- Database queries are indexed for fast lookups
- Session management is now O(1) instead of scanning files
- Progress tracking uses prepared statements for efficiency

### Data Safety
- All database operations use transactions
- Constraints prevent invalid data states
- Original JSON files are not deleted during migration

## Troubleshooting

### Issue: "database is locked"
**Solution**: Only one process can write to SQLite at a time. Make sure you don't have multiple instances of the app running.

### Issue: "no such table"
**Solution**: Run `python3 db.py` to initialize the database.

### Issue: "UNIQUE constraint failed"
**Solution**: You may have duplicate data. Check your JSON files for duplicates before migration.

### Issue: Sessions not persisting
**Solution**: Make sure the `data/` directory is writable and the database file exists.

## Support

If you encounter any issues:
1. Check the terminal output for error messages
2. Verify the database exists: `ls -la data/blg_exam.db`
3. Check database integrity: `sqlite3 data/blg_exam.db "PRAGMA integrity_check;"`
4. Review the application logs

## Future Improvements

With the database in place, we can now add:
- User analytics and detailed statistics
- Search functionality across all pools
- Export/import features
- Backup and restore capabilities
- Multi-user support improvements

# Session Bug - Before and After

## BEFORE (JSON Files) ❌

```
User uploads problem set "jk100"
    ↓
Saved to: data/pools_username.json
    {
      "id": "abc123",
      "path": "data/abc123_jk100.csv", 
      "orig_name": "jk100"
    }
    ↓
User clicks "Start Quiz" on jk100
    ↓
Session created in memory:
    app_state[sid] = {
      'pool': [...questions...],
      'set': [...selected questions...],
      ...
    }
    session['pool_id'] = 'abc123'
    ↓
    ⚠️ PROBLEM: Which pool do we use?
    - Session might be lost (in-memory only)
    - pool_id in session, but pool data in memory
    - Race conditions reading JSON files
    - No guarantee pool_id matches actual questions
    ↓
Result: Often falls back to default/builtin set ❌
```

## AFTER (SQLite Database) ✅

```
User uploads problem set "jk100"
    ↓
Saved to database:
    INSERT INTO pools (id, username, orig_name, file_path)
    VALUES ('abc123', 'user', 'jk100', 'data/abc123_jk100.csv')
    ↓
    ✓ Pool exists in database with foreign key to user
    ↓
User clicks "Start Quiz" on jk100
    ↓
Session created in database:
    INSERT INTO sessions (sid, username, pool_id, pool_data, ...)
    VALUES ('xyz', 'user', 'abc123', [...], ...)
    ↓
    ✓ Session has FOREIGN KEY to pools(id)
    ✓ Database ensures pool 'abc123' exists
    ✓ Session persists even if server restarts
    ↓
User answers questions:
    - Load session: SELECT * FROM sessions WHERE sid='xyz'
    - Pool ID is guaranteed: session.pool_id = 'abc123'
    - Database enforces referential integrity
    ↓
End session and save progress:
    - pool_id = session.pool_id  # Always correct!
    - INSERT INTO progress (username, pool_id, question_id, ...)
      VALUES ('user', 'abc123', 'q1', ...)
    ↓
    ✓ Foreign key ensures progress linked to correct pool
    ✓ Unique constraint prevents duplicates
    ↓
Result: Always uses the correct uploaded set ✅
```

## Key Differences

| Aspect | Before (JSON) | After (SQLite) |
|--------|---------------|----------------|
| **Session Storage** | In-memory dict | Database table |
| **Pool Reference** | String in session var | Foreign key constraint |
| **Data Integrity** | None | Enforced by database |
| **Persistence** | Lost on restart | Survives restarts |
| **Concurrent Access** | Race conditions | ACID transactions |
| **Pool Validation** | Manual checks | Automatic via FK |
| **Progress Tracking** | Separate JSON files | Linked via FK |

## The Fix in Action

### Upload Flow
```python
# BEFORE
pools = read_pools()  # Read from JSON file
pools.append({'id': pid, 'path': dest, 'orig_name': pname})
write_pools(pools)  # Write back to JSON file

# AFTER  
db.create_pool(pid, username, pname, dest)  # One atomic operation
```

### Session Creation Flow
```python
# BEFORE
app_state[sid] = {  # In-memory only
    'pool': pool_questions,
    'set': exam_set,
    'progress': progress
}
session['pool_id'] = pid  # Separate from pool data

# AFTER
db.create_session(sid, username, pid, pool_data, exam_set, num, progress_data)
# ↑ Single transaction with FK to pools(id)
session['pool_id'] = pid  # Backed by database
```

### Progress Saving Flow
```python
# BEFORE
pool_id = session.get('pool_id')  # Might be missing/wrong
prog_fp = f"data/progress_{pool_id}.json"  # File might not exist
# Write to JSON file (no validation)

# AFTER
pool_id = session.get('pool_id')  # Always correct (from database session)
username = current_user()
db.save_bulk_progress(username, pool_id, progress_dict)
# ↑ Foreign key ensures pool_id is valid
# ↑ Unique constraint prevents duplicates
# ↑ Transaction ensures consistency
```

## Why This Fixes the Bug

1. **Foreign Key Constraints**: The database enforces that `sessions.pool_id` must reference an existing `pools.id`. You can't create a session for a non-existent pool.

2. **Atomic Operations**: Session creation is a single database transaction. Either it all succeeds (with valid pool_id) or it all fails. No partial states.

3. **Persistent State**: Sessions survive server restarts because they're in the database, not in-memory. No more lost pool associations.

4. **Data Validation**: Can't save progress for a pool that doesn't exist. The database rejects invalid foreign keys.

5. **Explicit Relationships**: The schema clearly defines user → pools → progress relationships. No ambiguity.

## Testing the Fix

```bash
# 1. Upload a problem set via web UI
#    → Creates entry in pools table

# 2. Start a quiz with that set  
#    → Creates entry in sessions table with pool_id FK

# 3. Answer questions
#    → Session.pool_id is always the uploaded pool ID

# 4. End session
#    → Progress saved with correct pool_id FK

# 5. Restart server
#    → Session persists in database

# 6. Resume or start new quiz
#    → Pool_id correctly retrieved from database
```

The bug is fixed because the database structure ENFORCES correct behavior, rather than relying on application logic to track pools correctly.

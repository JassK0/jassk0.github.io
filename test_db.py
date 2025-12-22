#!/usr/bin/env python3
"""
Test script to verify database operations work correctly.
"""

import db
import os

def test_database():
    print("Testing BLG Exam Database Operations")
    print("=" * 60)
    
    # Test 1: Check if database exists
    if os.path.exists(db.DB_PATH):
        print("✓ Database file exists")
    else:
        print("✗ Database file missing - initializing...")
        db.init_db()
    
    # Test 2: Query users
    try:
        users = db.get_all_users()
        print(f"✓ Found {len(users)} user(s) in database")
        for username in users.keys():
            print(f"  - {username}")
    except Exception as e:
        print(f"✗ Error querying users: {e}")
        return False
    
    # Test 3: Query pools
    try:
        pools = db.get_pools()
        print(f"✓ Found {len(pools)} pool(s) in database")
        for pool in pools:
            print(f"  - {pool['orig_name']} (ID: {pool['id'][:8]}...)")
    except Exception as e:
        print(f"✗ Error querying pools: {e}")
        return False
    
    # Test 4: Query gamestates
    try:
        leaderboard = db.get_leaderboard()
        print(f"✓ Found {len(leaderboard)} gamestate(s)")
        for entry in leaderboard:
            print(f"  - {entry['username']}: {entry['points']} points, {entry['rank']}")
    except Exception as e:
        print(f"✗ Error querying gamestates: {e}")
        return False
    
    # Test 5: Test session creation and retrieval (if user exists)
    if users:
        try:
            test_username = list(users.keys())[0]
            test_sid = "test_session_12345"
            
            # Create a test session
            db.create_session(
                test_sid,
                test_username,
                "builtin",
                [],  # pool_data
                [],  # exam_set
                10,  # num_questions
                {}   # progress_data
            )
            print(f"✓ Created test session")
            
            # Retrieve it
            session = db.get_session(test_sid)
            if session:
                print(f"✓ Retrieved test session successfully")
                # Clean up
                db.delete_session(test_sid)
                print(f"✓ Deleted test session")
            else:
                print(f"✗ Failed to retrieve test session")
        except Exception as e:
            print(f"✗ Error testing sessions: {e}")
            # Try to clean up
            try:
                db.delete_session(test_sid)
            except:
                pass
    
    print("=" * 60)
    print("All tests completed!")
    return True

if __name__ == "__main__":
    test_database()

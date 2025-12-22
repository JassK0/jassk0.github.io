#!/usr/bin/env python3
"""
Pre-deployment verification script.
Tests all critical functionality before going live.
"""

import sys
import os

def run_checks():
    print("=" * 70)
    print("BLG EXAM - PRE-DEPLOYMENT VERIFICATION")
    print("=" * 70)
    print()
    
    all_passed = True
    
    # Check 1: Syntax validation
    print("1. Checking Python syntax...")
    result = os.system("python3 -m py_compile webgui.py db.py 2>&1")
    if result == 0:
        print("   ✅ All Python files compile successfully")
    else:
        print("   ❌ Syntax errors found")
        all_passed = False
    print()
    
    # Check 2: Database exists and is accessible
    print("2. Checking database...")
    import db
    if os.path.exists(db.DB_PATH):
        print(f"   ✅ Database exists at {db.DB_PATH}")
        # Check tables
        try:
            users = db.get_all_users()
            pools = db.get_pools()
            print(f"   ✅ Found {len(users)} user(s)")
            print(f"   ✅ Found {len(pools)} pool(s)")
        except Exception as e:
            print(f"   ❌ Database error: {e}")
            all_passed = False
    else:
        print(f"   ❌ Database not found at {db.DB_PATH}")
        all_passed = False
    print()
    
    # Check 3: Required modules
    print("3. Checking dependencies...")
    try:
        import flask
        print(f"   ✅ Flask {flask.__version__} installed")
    except ImportError:
        print("   ⚠️  Flask not installed (required for web server)")
        print("      Run: pip install -r requirements.txt")
    
    try:
        from werkzeug.security import generate_password_hash
        print("   ✅ Werkzeug available (password hashing)")
    except ImportError:
        print("   ❌ Werkzeug not available")
        all_passed = False
    print()
    
    # Check 4: Critical database operations
    print("4. Testing database operations...")
    try:
        # Test session creation
        test_sid = "precheck_session"
        db.create_session(test_sid, None, "builtin", [], [], 10, {})
        session = db.get_session(test_sid)
        if session:
            print("   ✅ Session creation/retrieval works")
            db.delete_session(test_sid)
            print("   ✅ Session deletion works")
        else:
            print("   ❌ Session retrieval failed")
            all_passed = False
    except Exception as e:
        print(f"   ❌ Session operations failed: {e}")
        all_passed = False
    print()
    
    # Check 5: File structure
    print("5. Checking file structure...")
    required_files = [
        'webgui.py',
        'db.py',
        'main.py',
        'app.py',
        'requirements.txt',
        'templates/index.html',
        'templates/question.html',
        'data/blg_exam.db'
    ]
    for file in required_files:
        if os.path.exists(file):
            print(f"   ✅ {file}")
        else:
            print(f"   ⚠️  {file} not found")
    print()
    
    # Check 6: Deprecated functions removed
    print("6. Checking for deprecated code...")
    with open('webgui.py', 'r') as f:
        content = f.read()
        if 'app_state[' in content:
            print("   ❌ Old in-memory app_state still referenced")
            all_passed = False
        else:
            print("   ✅ No references to deprecated app_state")
    print()
    
    # Final verdict
    print("=" * 70)
    if all_passed:
        print("✅ ALL CHECKS PASSED - READY FOR DEPLOYMENT")
        print()
        print("To start the server:")
        print("    python3 app.py")
        print()
        print("The application will run on: http://localhost:5004")
        print("=" * 70)
        return 0
    else:
        print("❌ SOME CHECKS FAILED - REVIEW ISSUES BEFORE DEPLOYMENT")
        print("=" * 70)
        return 1

if __name__ == "__main__":
    sys.exit(run_checks())

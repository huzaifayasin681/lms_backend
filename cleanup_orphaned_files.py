#!/usr/bin/env python
"""
Script to clean up orphaned file records in the database.
Orphaned records are database entries that point to files that don't exist on disk.
"""
import os
import sqlite3
from datetime import datetime

def cleanup_orphaned_files(db_path='lms.db', dry_run=True):
    """
    Clean up orphaned file records in the database.
    
    Args:
        db_path: Path to SQLite database
        dry_run: If True, only report issues without making changes
    """
    print(f"Starting cleanup at {datetime.now()}")
    print(f"Database: {db_path}")
    print(f"Mode: {'DRY RUN' if dry_run else 'LIVE'}")
    print("-" * 50)
    
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    
    # Get all file content records
    cursor.execute("""
        SELECT id, course_id, title, file_path, file_name 
        FROM course_content 
        WHERE content_type = 'file' AND active = 1 AND file_path IS NOT NULL
    """)
    
    records = cursor.fetchall()
    print(f"Found {len(records)} file records to check")
    
    orphaned_records = []
    valid_records = []
    
    for record in records:
        record_id, course_id, title, file_path, file_name = record
        
        # Check if file exists
        if os.path.exists(file_path):
            valid_records.append(record)
            print(f"OK ID {record_id}: {file_name} - File exists")
        else:
            orphaned_records.append(record)
            print(f"MISSING ID {record_id}: {file_name} - FILE MISSING: {file_path}")
    
    print("\n" + "=" * 50)
    print(f"SUMMARY:")
    print(f"Valid records: {len(valid_records)}")
    print(f"Orphaned records: {len(orphaned_records)}")
    
    if orphaned_records:
        print(f"\nOrphaned records to {'WOULD BE' if dry_run else 'WILL BE'} deactivated:")
        for record in orphaned_records:
            record_id, course_id, title, file_path, file_name = record
            print(f"  - ID {record_id}: {title} ({file_name})")
        
        if not dry_run:
            # Deactivate orphaned records instead of deleting them
            orphaned_ids = [str(record[0]) for record in orphaned_records]
            placeholders = ','.join(['?' for _ in orphaned_ids])
            
            cursor.execute(f"""
                UPDATE course_content 
                SET active = 0, updated_at = datetime('now')
                WHERE id IN ({placeholders})
            """, orphaned_ids)
            
            conn.commit()
            print(f"\nOK Deactivated {len(orphaned_records)} orphaned records")
        else:
            print(f"\nWARNING: Run with dry_run=False to actually clean up these records")
    else:
        print(f"\nOK No orphaned records found - database is clean!")
    
    conn.close()
    print(f"\nCleanup completed at {datetime.now()}")

if __name__ == "__main__":
    import sys
    
    # Check command line arguments
    dry_run = True
    if len(sys.argv) > 1 and sys.argv[1].lower() in ['--live', '--execute', '--real']:
        dry_run = False
        print("WARNING: LIVE MODE - Changes will be made to the database!")
        response = input("Are you sure? Type 'yes' to continue: ")
        if response.lower() != 'yes':
            print("Cancelled.")
            sys.exit(1)
    
    cleanup_orphaned_files(dry_run=dry_run)
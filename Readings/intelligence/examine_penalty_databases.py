#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Examine the penalty databases to understand their structure"""

import sqlite3
import os
from pathlib import Path

def examine_database(db_path, db_name):
    print(f"\n{'='*60}")
    print(f"EXAMINING: {db_name}")
    print(f"Path: {db_path}")
    print(f"Size: {os.path.getsize(db_path) / (1024*1024):.2f} MB")
    print(f"{'='*60}")
    
    try:
        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()
        
        # Get all tables
        cursor.execute("SELECT name FROM sqlite_master WHERE type='table';")
        tables = cursor.fetchall()
        
        print(f"Tables found: {len(tables)}")
        for table in tables:
            table_name = table[0]
            print(f"\n--- TABLE: {table_name} ---")
            
            # Get table schema
            cursor.execute(f"PRAGMA table_info({table_name})")
            columns = cursor.fetchall()
            print("Columns:")
            for col in columns:
                print(f"  {col[1]} ({col[2]})")
            
            # Get row count
            cursor.execute(f"SELECT COUNT(*) FROM {table_name}")
            count = cursor.fetchone()[0]
            print(f"Row count: {count:,}")
            
            # Show sample data
            if count > 0:
                cursor.execute(f"SELECT * FROM {table_name} LIMIT 3")
                samples = cursor.fetchall()
                print("Sample data:")
                for i, sample in enumerate(samples, 1):
                    print(f"  Row {i}: {sample}")
        
        conn.close()
        
    except Exception as e:
        print(f"Error examining database: {e}")

def main():
    print("PENALTY DATABASE EXAMINATION")
    print("="*60)
    
    data_dir = Path("D:/AI/New folder/data")
    
    # Check penalty_database.db
    penalty_db = data_dir / "penalty_database.db"
    if penalty_db.exists():
        examine_database(str(penalty_db), "penalty_database.db")
    else:
        print(f"penalty_database.db not found at {penalty_db}")
    
    # Check penalty_intelligence.db
    penalty_intel_db = data_dir / "penalty_intelligence.db"
    if penalty_intel_db.exists():
        examine_database(str(penalty_intel_db), "penalty_intelligence.db")
    else:
        print(f"penalty_intelligence.db not found at {penalty_intel_db}")

if __name__ == "__main__":
    main()
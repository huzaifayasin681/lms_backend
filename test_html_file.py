#!/usr/bin/env python
"""
Quick test to verify HTML file can be read and served
"""
import os
import mimetypes

def test_html_file():
    file_path = 'uploads/CS101/FYP_SQLI_a6d5c058.html'
    
    print(f"Testing HTML file: {file_path}")
    print("-" * 50)
    
    # Check if file exists
    if not os.path.exists(file_path):
        print("ERROR File does not exist")
        return False
    
    print(f"OK File exists")
    
    # Check file size
    file_size = os.path.getsize(file_path)
    print(f"OK File size: {file_size} bytes")
    
    # Check if readable
    if not os.access(file_path, os.R_OK):
        print("ERROR File is not readable")
        return False
    
    print(f"OK File is readable")
    
    # Check MIME type
    mime_type, _ = mimetypes.guess_type(file_path)
    print(f"OK MIME type: {mime_type}")
    
    # Try to read first few lines
    try:
        with open(file_path, 'r', encoding='utf-8') as f:
            first_lines = f.readline()[:100]
            print(f"OK File content preview: {first_lines}...")
    except Exception as e:
        print(f"ERROR reading file: {e}")
        return False
    
    print("\nOK All tests passed - HTML file should be servable")
    return True

if __name__ == "__main__":
    test_html_file()
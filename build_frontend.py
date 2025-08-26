#!/usr/bin/env python3
"""
Script to build the React frontend and copy it to the backend directory
"""
import os
import shutil
import subprocess
import sys

def run_command(cmd, cwd=None):
    """Run a command and return success status"""
    try:
        result = subprocess.run(cmd, shell=True, cwd=cwd, check=True, 
                              capture_output=True, text=True)
        print(f"✅ {cmd}")
        return True
    except subprocess.CalledProcessError as e:
        print(f"❌ {cmd}")
        print(f"Error: {e.stderr}")
        return False

def main():
    # Paths
    backend_dir = os.path.dirname(os.path.abspath(__file__))
    project_root = os.path.dirname(backend_dir)
    frontend_dir = os.path.join(project_root, 'frontend')
    frontend_build_dir = os.path.join(frontend_dir, 'build')
    backend_build_dir = os.path.join(backend_dir, 'build')
    
    print("🏗️  Building React frontend...")
    print(f"Frontend directory: {frontend_dir}")
    print(f"Backend directory: {backend_dir}")
    
    # Check if frontend directory exists
    if not os.path.exists(frontend_dir):
        print(f"❌ Frontend directory not found: {frontend_dir}")
        return False
    
    # Build the React app
    print("\n📦 Installing dependencies...")
    if not run_command("npm install", cwd=frontend_dir):
        return False
    
    print("\n🔨 Building React app...")
    if not run_command("npm run build", cwd=frontend_dir):
        return False
    
    # Copy build to backend
    if os.path.exists(backend_build_dir):
        print(f"\n🗑️  Removing existing build directory: {backend_build_dir}")
        shutil.rmtree(backend_build_dir)
    
    print(f"\n📁 Copying build to backend: {backend_build_dir}")
    shutil.copytree(frontend_build_dir, backend_build_dir)
    
    print("\n✅ Frontend build completed successfully!")
    print(f"📂 Build files copied to: {backend_build_dir}")
    print("\n🚀 You can now run: python myapp.py")
    
    return True

if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)
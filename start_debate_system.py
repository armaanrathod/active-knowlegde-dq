#!/usr/bin/env python3
"""
Start script for the Active Knowledge Debate System
This script helps users get started quickly
"""

import os
import sys
import subprocess
import webbrowser
import time
from pathlib import Path

def check_dependencies():
    """Check if required dependencies are installed"""
    try:
        import flask
        import flask_cors
        import requests
        print("✅ All dependencies found")
        return True
    except ImportError as e:
        print(f"❌ Missing dependency: {e}")
        print("Installing required packages...")
        subprocess.run([sys.executable, "-m", "pip", "install", "flask", "flask-cors", "requests"])
        return True

def start_system():
    """Start the debate system"""
    print("🚀 Starting Active Knowledge Debate System...")
    print("="*50)
    
    # Check dependencies
    if not check_dependencies():
        print("Failed to install dependencies. Exiting.")
        return
    
    # Get current directory
    current_dir = Path(__file__).parent.absolute()
    backend_file = current_dir / "backend_debate.py"
    html_file = current_dir / "html"
    
    print(f"📁 Working directory: {current_dir}")
    print(f"🐍 Backend file: {backend_file}")
    print(f"🌐 Frontend file: {html_file}")
    
    if not backend_file.exists():
        print("❌ backend_debate.py not found!")
        return
    
    if not html_file.exists():
        print("❌ html file not found!")
        return
    
    print("\n🔧 Starting Flask backend...")
    print("Backend will run on http://localhost:5000")
    print("Frontend available at file://" + str(html_file))
    print("\n⚠️  Note: This demo requires Ollama running on localhost:11434")
    print("Visit https://ollama.ai to install Ollama if not already available")
    print("\n🎯 Features:")
    print("- 5 points FOR and AGAINST each topic")
    print("- User interaction with 3 questions per round")
    print("- Automatic relevance tracking")
    print("- Graceful exit at 40% relevance threshold")
    print("\n" + "="*50)
    print("Starting in 3 seconds... (Press Ctrl+C to cancel)")
    
    try:
        time.sleep(3)
        
        # Open browser with HTML file
        html_url = f"file://{html_file}"
        webbrowser.open(html_url)
        print(f"🌐 Opened browser to: {html_url}")
        
        # Start Flask backend
        print("🚀 Starting Flask backend (Ctrl+C to stop)...")
        os.chdir(current_dir)
        subprocess.run([sys.executable, "backend_debate.py"])
        
    except KeyboardInterrupt:
        print("\n\n👋 Stopping debate system...")
        print("Thank you for using Active Knowledge Debate System!")

if __name__ == "__main__":
    start_system()
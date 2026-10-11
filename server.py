#!/usr/bin/env python3
"""OpenNow - Free, AI-Native Enterprise Service Platform & CMDB Engine
Root server launcher.
"""

import sys
import os

# Set UTF-8 encoding for standard output on Windows
if sys.platform.startswith("win"):
    import io
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')
    sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding='utf-8', errors='replace')

# Ensure project root is in sys.path
PROJECT_ROOT = os.path.dirname(os.path.abspath(__file__))
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

import uvicorn

if __name__ == "__main__":
    port = 8000
    if len(sys.argv) > 1:
        try:
            port = int(sys.argv[1])
        except ValueError:
            pass

    print("=" * 68)
    print("  [*] Starting OpenNow - AI-Native Enterprise Service Platform")
    print(f"  [+] Dashboard: http://localhost:{port}")
    print(f"  [+] Interactive API Docs: http://localhost:{port}/docs")
    print("=" * 68)
    uvicorn.run("backend.api:app", host="0.0.0.0", port=port, reload=False)

#!/usr/bin/env python3
import sys
print("Python version:", sys.version)
print("Python path:", sys.path)

try:
    import flask
    print("Flask is available!")
    print("Flask version:", flask.__version__)
except ImportError as e:
    print("Flask is not available:", e)

try:
    import http.server
    import socketserver
    print("Built-in http.server is available")
except ImportError as e:
    print("http.server not available:", e)

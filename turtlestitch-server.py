#!/usr/bin/env python3
"""
Simple HTTP server for TurtleStitch offline mode.
Serves static files and adds CORS headers for Moonraker API calls.
"""
import http.server
import socketserver
import os

PORT = 3000
DIRECTORY = '/home/pi/turtlestitch'

class CORSHTTPRequestHandler(http.server.SimpleHTTPRequestHandler):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, directory=DIRECTORY, **kwargs)
    
    def end_headers(self):
        # Allow CORS for Moonraker API calls
        self.send_header('Access-Control-Allow-Origin', '*')
        self.send_header('Access-Control-Allow-Methods', 'GET, POST, OPTIONS')
        self.send_header('Access-Control-Allow-Headers', 'Content-Type, X-Api-Key')
        super().end_headers()
    
    def do_OPTIONS(self):
        self.send_response(200)
        self.end_headers()

if __name__ == '__main__':
    with socketserver.TCPServer(('0.0.0.0', PORT), CORSHTTPRequestHandler) as httpd:
        print(f'Serving TurtleStitch at http://0.0.0.0:{PORT}')
        httpd.serve_forever()

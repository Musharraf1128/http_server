#!/usr/bin/env python3

from queue import Queue
from concurrent.futures import ThreadPoolExecutor
import threading
import os

class HTTPServer:
        
    # HTTP Status codes
    STATUS_CODES = {
        200: "OK",
        201: "Created",
        400: "Bad Request",
        403: "Forbidden",
        404: "Not Found",
        405: "Method Not Allowed",
        415: "Unsupported Media Type",
        500: "Internal Server Error",
        503: "Service Unavailable"
    }
    
    # Supported file types and their content types
    CONTENT_TYPES = {
        '.html': 'text/html; charset=utf-8',
        '.txt': 'application/octet-stream',
        '.png': 'application/octet-stream',
        '.jpg': 'application/octet-stream',
        '.jpeg': 'application/octet-stream'
    }
    
    def __init__(self, host="127.0.0.1", port=8080, max_threads=10):
        self.host = host
        self.port = port
        self.max_threads = max_threads
        self.resources_dir = 'resources'
        self.uploads_dir = os.path.join(self.resources_dir, 'uploads')
        
        # Thread pool and connection management
        self.thread_pool = ThreadPoolExecutor(max_workers=max_threads)
        self.connection_queue = Queue()
        self.active_threads = 0
        self.lock = threading.Lock()
        
        # Create uploads directory if it doesn't exist
        os.makedirs(self.uploads_dir, exist_ok=True)
        
        # Server socket (initialized in start())
        self.server_socket = None


 

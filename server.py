#!/usr/bin/env python3

from queue import Queue
from concurrent.futures import ThreadPoolExecutor
import threading
import os
from datetime import datetime
import socket 
import sys

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

    

    def log(self, message, thread_id=None):
        # Log a message with timestamp and optional thread ID.
        
        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        if thread_id:
            print(f"[{timestamp}] [{thread_id}] {message}")
        else:
            print(f"[{timestamp}] {message}")

    

    def start(self):
        # Start the HTTP server, bind to address, and begin accepting connections.

        try:
            # Create TCP socket
            self.server_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            self.server_socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
            
            # Bind to address and port
            self.server_socket.bind((self.host, self.port))
            
            # Listen for connections (queue size of 50)
            self.server_socket.listen(50)
            
            # Log server startup
            self.log(f"HTTP Server started on http://{self.host}:{self.port}")
            self.log(f"Thread pool size: {self.max_threads}")
            self.log(f"Serving files from '{self.resources_dir}' directory")
            self.log("Press Ctrl+C to stop the server")
            
            # Accept connections in a loop
            while True:
                try:
                    client_socket, client_address = self.server_socket.accept()
                    
                    # Check thread pool status
                    with self.lock:
                        if self.active_threads < self.max_threads:
                            self.active_threads += 1
                            # Submit to thread pool
                            self.thread_pool.submit(
                                self.handle_client_wrapper, 
                                client_socket, 
                                client_address
                            )
                        else:
                            # Thread pool saturated, queue the connection
                            self.log("Warning: Thread pool saturated, queuing connection")
                            self.connection_queue.put((client_socket, client_address))
                            
                except KeyboardInterrupt:
                    self.log("Server shutting down...")
                    break
                except Exception as e:
                    self.log(f"Error accepting connection: {e}")
                    
        except Exception as e:
            self.log(f"Fatal error starting server: {e}")
        finally:
            if self.server_socket:
                self.server_socket.close()
            self.thread_pool.shutdown(wait=True)
        
    

    def handle_client_wrapper(self, client_socket, client_address):
        # Wrapper for handle_client that manages thread pool count and dequeuing.
            
        try:
            self.handle_client(client_socket, client_address)
        finally:
            # Decrement active threads and check queue
            with self.lock:
                self.active_threads -= 1
                
                # Check if there are queued connections
                if not self.connection_queue.empty():
                    queued_socket, queued_address = self.connection_queue.get()
                    self.log(f"Connection dequeued, assigned to new thread")
                    self.active_threads += 1
                    self.thread_pool.submit(
                        self.handle_client_wrapper,
                        queued_socket,
                        queued_address
                    )

    

    def handle_client(self, client_socket, client_address):
        # Handle a client connection, supporting persistent connections.
        
        thread_id = threading.current_thread().name
        self.log(f"Connection from {client_address[0]}:{client_address[1]}", thread_id)
        
        # Set socket timeout for persistent connections
        client_socket.settimeout(30)
        
        request_count = 0
        max_requests = 100
        
        try:
            while request_count < max_requests:
                try:
                    # Receive request data
                    request_data = client_socket.recv(8192)
                    
                    if not request_data:
                        break
                    
                    request_count += 1
                    
                    # Parse the HTTP request
                    request_text = request_data.decode('utf-8', errors='ignore')
                    parsed_request = self.parse_request(request_text)
                    
                    if not parsed_request:
                        self.send_error(client_socket, 400, "Bad Request", thread_id)
                        break
                    
                    method, path, version, headers, body = parsed_request
                    
                    self.log(f"Request: {method} {path} {version}", thread_id)
                    
                    # Validate Host header
                    if not self.validate_host(headers):
                        if 'host' not in headers:
                            self.log(f"Missing Host header", thread_id)
                            self.send_error(client_socket, 400, "Bad Request", thread_id)
                        else:
                            self.log(f"Host validation failed: {headers.get('host', 'N/A')}", thread_id)
                            self.send_error(client_socket, 403, "Forbidden", thread_id)
                        break
                    
                    self.log(f"Host validation: {headers.get('host', 'N/A')} ✓", thread_id)
                    
                    # Determine connection persistence
                    keep_alive = self.should_keep_alive(version, headers)
                    
                    # Route request based on method
                    if method == "GET":
                        self.handle_get(client_socket, path, headers, thread_id, keep_alive)
                    elif method == "POST":
                        self.handle_post(client_socket, path, headers, body, thread_id, keep_alive)
                    else:
                        self.send_error(client_socket, 405, "Method Not Allowed", thread_id, keep_alive)
                    
                    # Check if connection should be closed
                    if not keep_alive:
                        self.log(f"Connection: close", thread_id)
                        break
                    
                    self.log(f"Connection: keep-alive", thread_id)
                    
                except socket.timeout:
                    self.log(f"Connection timeout", thread_id)
                    break
                except Exception as e:
                    self.log(f"Error handling request: {e}", thread_id)
                    break
                    
        finally:
            client_socket.close()
            self.log(f"Connection closed", thread_id)
    

    
    def parse_request(self, request_text):
        # Parse an HTTP request into its components.
        
        try:
            # Split request into lines
            lines = request_text.split('\r\n')
            
            # Parse request line
            request_line = lines[0]
            parts = request_line.split(' ')
            
            if len(parts) != 3:
                return None
            
            method, path, version = parts
            
            # Parse headers
            headers = {}
            body_start = 0
            
            for i, line in enumerate(lines[1:], 1):
                if line == '':
                    body_start = i + 1
                    break
                
                if ':' in line:
                    key, value = line.split(':', 1)
                    headers[key.strip().lower()] = value.strip()
            
            # Extract body if present
            body = '\r\n'.join(lines[body_start:]) if body_start > 0 else ''
            
            return method, path, version, headers, body
            
        except Exception:
            return None
    
    

    def should_keep_alive(self, version, headers):
        # Determine if connection should be kept alive based on HTTP version and headers.
            
        connection_header = headers.get('connection', '').lower()
        if version == "HTTP/1.1":
            # HTTP/1.1 defaults to keep-alive unless explicitly closed
            return connection_header != 'close'
        else:
            # HTTP/1.0 defaults to close unless explicitly keep-alive
            return connection_header == 'keep-alive'
 

    def validate_host(self, headers):
        # Validate the Host header matches the server's address.
        
        if 'host' not in headers:
            return False
        
        host_header = headers['host']
        
        # Valid host formats
        valid_hosts = [
            f"{self.host}:{self.port}",
            f"localhost:{self.port}",
            f"127.0.0.1:{self.port}"
        ]
        
        # Also accept without port if using default port 80
        if self.port == 80:
            valid_hosts.extend([self.host, "localhost", "127.0.0.1"])
        
        return host_header in valid_hosts
 

    def validate_path(self, path):
        # Validate and sanitize the requested path to prevent directory traversal attacks.
            
        # Remove query string if present
        path = path.split('?')[0]
        
        # Check for directory traversal patterns
        if '..' in path or path.startswith('//'):
            return None
        
        # Handle root path
        if path == '/' or path == '':
            path = '/index.html'
        
        # Remove leading slash for file system path
        if path.startswith('/'):
            path = path[1:]
        
        # Construct full path
        full_path = os.path.join(self.resources_dir, path)
        
        # Canonicalize path
        try:
            full_path = os.path.abspath(full_path)
            resources_path = os.path.abspath(self.resources_dir)
            
            # Ensure the path is within resources directory
            if not full_path.startswith(resources_path):
                return None
            
            return full_path
        except Exception:
            return None
    


    def get_http_date(self):
        # Get current date in RFC 7231 format for HTTP headers.
        
        from email.utils import formatdate
        return formatdate(timeval=None, localtime=False, usegmt=True)

    def handle_get(self, client_socket, path, headers, thread_id, keep_alive):
        # Handle GET requests for serving files.
        
        # Validate path
        file_path = self.validate_path(path)
        
        if not file_path:
            self.log(f"Path traversal attempt blocked: {path}", thread_id)
            self.send_error(client_socket, 403, "Forbidden", thread_id, keep_alive)
            return
        
        # Check if file exists
        if not os.path.isfile(file_path):
            self.log(f"File not found: {path}", thread_id)
            self.send_error(client_socket, 404, "Not Found", thread_id, keep_alive)
            return
        
        # Get file extension
        _, ext = os.path.splitext(file_path)
        ext = ext.lower()
        
        # Check if file type is supported
        if ext not in self.CONTENT_TYPES:
            self.log(f"Unsupported file type: {ext}", thread_id)
            self.send_error(client_socket, 415, "Unsupported Media Type", thread_id, keep_alive)
            return
        
        try:
            # Read file in binary mode
            with open(file_path, 'rb') as f:
                file_data = f.read()
            
            file_size = len(file_data)
            content_type = self.CONTENT_TYPES[ext]
            filename = os.path.basename(file_path)
            
            # Prepare response headers
            response_headers = {
                'Content-Type': content_type,
                'Content-Length': str(file_size),
                'Date': self.get_http_date(),
                'Server': 'Multi-threaded HTTP Server',
                'Connection': 'keep-alive' if keep_alive else 'close'
            }
            
            # Add Keep-Alive header if connection persists
            if keep_alive:
                response_headers['Keep-Alive'] = 'timeout=30, max=100'
            
            # For binary files, add Content-Disposition header
            if content_type == 'application/octet-stream':
                response_headers['Content-Disposition'] = f'attachment; filename="{filename}"'
                self.log(f"Sending binary file: {filename} ({file_size} bytes)", thread_id)
            else:
                self.log(f"Serving HTML file: {filename} ({file_size} bytes)", thread_id)
            
            # Send response
            self.send_response(client_socket, 200, response_headers, file_data)
            self.log(f"Response: 200 OK ({file_size} bytes transferred)", thread_id)
            
        except Exception as e:
            self.log(f"Error reading file: {e}", thread_id)
            self.send_error(client_socket, 500, "Internal Server Error", thread_id, keep_alive)
    


    def handle_post(self, client_socket, path, headers, body, thread_id, keep_alive):
        # Handle POST requests for JSON data upload.
        return None
    



    def send_response(self, client_socket, status_code, headers, body):
        # Send an HTTP response to the client.
        return None
        
        # Build status line 
        status_text = self.STATUS_CODES.get(status_code, "Unknown")
        status_line = f"HTTP/1.1 {status_code} {status_text}\r\n"
        
        # Build headers
        header_lines = []
        for key, value in headers.items():
            header_lines.append(f"{key}: {value}\r\n")
        
        # Combine status line, headers, and body
        response = status_line.encode('utf-8')
        response += ''.join(header_lines).encode('utf-8')
        response += b'\r\n'
        
        # Add body
        if isinstance(body, str):
            response += body.encode('utf-8')
        else:
            response += body
        
        # Send response
        client_socket.sendall(response)
    


    def send_error(self, client_socket, status_code, message, thread_id, keep_alive=False):
        # Send an HTTP error response.
        
        error_body = f"""<!DOCTYPE html>
<html>
<head><title>{status_code} {message}</title></head>
<body>
<h1>{status_code} {message}</h1>
<p>The server encountered an error processing your request.</p>
</body>
</html>"""
        
        headers = {
            'Content-Type': 'text/html; charset=utf-8',
            'Content-Length': str(len(error_body)),
            'Date': self.get_http_date(),
            'Server': 'Multi-threaded HTTP Server',
            'Connection': 'keep-alive' if keep_alive else 'close'
        }
        
        if status_code == 503:
            headers['Retry-After'] = '10'
        
        self.send_response(client_socket, status_code, headers, error_body)
        self.log(f"Response: {status_code} {message}", thread_id)
    


def main():
    # Main entry point for the HTTP server.
    
    # Default values
    host = "127.0.0.1"
    port = 8080
    max_threads = 10
    
    # Parse command-line arguments
    if len(sys.argv) > 1:
        try:
            port = int(sys.argv[1])
        except ValueError:
            print("Error: Port must be an integer")
            sys.exit(1)
    
    if len(sys.argv) > 2:
        host = sys.argv[2]
    
    if len(sys.argv) > 3:
        try:
            max_threads = int(sys.argv[3])
        except ValueError:
            print("Error: Max threads must be an integer")
            sys.exit(1)
    
    # Create and start server
    server = HTTPServer(host=host, port=port, max_threads=max_threads)
    server.start()



if __name__ == "__main__":
    main()









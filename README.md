# Multi-threaded HTTP Server

A full-featured HTTP/1.1 server implementation in Python with multi-threading, connection persistence, and security features.

## Features

-  **Multi-threaded**: Configurable thread pool with automatic connection queuing
-  **HTTP Methods**: GET (file serving) and POST (JSON processing)
-  **Binary Transfer**: Complete support for images (PNG, JPEG) and text files with integrity preservation
-  **Security**: Path traversal protection and host header validation
-  **Connection Persistence**: HTTP/1.1 keep-alive with 30-second timeout
-  **Comprehensive Logging**: Timestamped logs with thread identification

## Installation

```bash
# No external dependencies required (Python 3.6+)
git clone <your-repo-url>
cd project
```

## Usage

```bash
# Default (127.0.0.1:8080, 10 threads)
python3 server.py

# Custom port
python3 server.py 9000

# Custom host, port, and thread pool size
python3 server.py 8000 0.0.0.0 20
```

## Testing

```bash
# GET HTML file (renders in browser)
curl http://localhost:8080/

# GET binary file (downloads)
curl http://localhost:8080/logo.png -O

# POST JSON data
curl -X POST http://localhost:8080/upload \
  -H "Content-Type: application/json" \
  -d '{"test": "data", "value": 42}'

# Test security (path traversal - should return 403)
curl http://localhost:8080/../etc/passwd

# Test host validation (should return 403)
curl -H "Host: evil.com" http://localhost:8080/
```

## Implementation Details

### Thread Pool Architecture
- Uses `ThreadPoolExecutor` with configurable worker threads
- Automatic connection queuing when pool is saturated
- Thread-safe resource management with locks
- Automatic dequeuing and assignment when threads become available

### Binary File Transfer
- Files read in binary mode (`'rb'`) to preserve integrity
- Content-Type: `application/octet-stream` for downloads
- Content-Disposition header triggers browser download
- Supports: `.png`, `.jpg`, `.jpeg`, `.txt` files

### Security Features
1. **Path Traversal Protection**: Blocks `..`, `//`, and validates paths stay within `resources/` directory
2. **Host Header Validation**: Rejects requests with missing or mismatched Host headers
3. **Content-Type Validation**: Strict JSON validation for POST requests

### Connection Management
- HTTP/1.1 defaults to keep-alive, HTTP/1.0 defaults to close
- 30-second idle timeout per connection
- Maximum 100 requests per persistent connection
- Honors `Connection: keep-alive` and `Connection: close` headers

### Supported HTTP Status Codes
- `200 OK`, `201 Created`, `400 Bad Request`, `403 Forbidden`, `404 Not Found`
- `405 Method Not Allowed`, `415 Unsupported Media Type`, `500 Internal Server Error`

## Project Structure

```
project/
├── server.py               # Main server implementation (600+ lines)
├── README.md               # This file
├── resources/              # Static files directory
│   ├── index.html
│   ├── about.html
|   ├── contact.html
│   ├── *.png, *.jpg, *jpeg
│   └── uploads/             # POST uploads saved here
```

## Known Limitations

- Files loaded entirely into memory (not suitable for files >100MB)
- No HTTPS support (HTTP only)
- No compression support (gzip/deflate)
- Fixed-size thread pool (no dynamic scaling)
- 8192-byte request size limit

## Author

**Razor** - October 2025  
Educational project for Network Programming course

---

**Note**: This server is designed for educational purposes. For production use, consider established frameworks like Flask or FastAPI.

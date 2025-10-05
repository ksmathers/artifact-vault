# Development Guide

This guide covers the architecture, development setup, and contribution guidelines for Artifact Vault.

## Architecture Overview

Artifact Vault follows a modular plugin-based architecture that makes it easy to add new backend sources.

### Core Components

```
artifact-vault/
├── main.py                 # Main application entry point
├── config-sample.yml       # Sample configuration file
├── prepare-cache.sh       # Example cache preparation script
└── artifact_vault/        # Core package
    ├── __init__.py
    ├── cache.py           # Cache management
    ├── backend_http.py    # HTTP backend implementation
    ├── backend_pypi.py    # PyPI backend implementation
    └── backend_dockerhub.py # DockerHub backend implementation
```

### Request Flow Architecture

```
[Client Request] 
    ↓
[HTTP Server] (main.py)
    ↓
[Path Routing] (determine backend by URL prefix)
    ↓
[Backend Selection] (can_handle() method)
    ↓
[Cache Check] (backend checks cache first)
    ↓
[Fetch/Stream] (cache hit → stream from cache, miss → fetch and stream)
    ↓
[Response] (streamed chunks with progress)
```

### Backend Interface

All backends must implement this interface:

```python
class BackendInterface:
    def __init__(self, config, cache):
        """Initialize backend with configuration and cache instance."""
        pass
    
    def can_handle(self, path):
        """Return True if this backend can handle the given path."""
        pass
    
    def fetch(self, path):
        """Generator that yields artifact chunks with progress information.  If a
        non-default content_type is specified then it must be included in the first
        chunk returned by 'fetch'
        
        Yields dictionaries with:
        - total_length: int (total file size, if known)
        - content: bytes (chunk data)
        - bytes_downloaded: int (cumulative bytes downloaded)
        - content_type: application/octet-stream (default, optional)
        - error: str (error message, if any)
        """
        pass
```

## Development Setup

### Prerequisites

- Python 3.7+
- Git
- Virtual environment (recommended)

### Local Setup

```bash
# Clone the repository
git clone <repository-url>
cd artifact-vault

# Create virtual environment
python -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate

# Install dependencies (create requirements.txt if needed)
pip install requests pyyaml

# Copy configuration
cp config-sample.yml config.yml

# Run the server
python main.py --config config.yml --log-level DEBUG
```

### Development Configuration

For development, use this configuration:

```yaml
http_host: localhost
http_port: 8080
cache_dir: /tmp/artifact_cache_dev
log_level: DEBUG

backends:
  - type: http
    config:
      prefix: /test/
      base_url: https://httpbin.org
```

## Adding New Backends

### Step 1: Create Backend Class

Create `artifact_vault/backend_myservice.py`:

```python
import requests

class MyServiceBackend:
    def __init__(self, config, cache):
        self.config = config
        self.cache = cache
        self.prefix = config.get('prefix', '/myservice/')
        self.base_url = config.get('base_url', '')
        
        # Validate required configuration
        if not self.base_url:
            raise ValueError(f"MyServiceBackend {self.prefix} requires 'base_url'")
    
    def can_handle(self, path):
        """Check if this backend handles the path."""
        return path.startswith(self.prefix)
    
    def fetch(self, path):
        """Fetch artifact with streaming support."""
        artifact_path = path[len(self.prefix):]
        
        # Check cache first
        hit = self.cache.has(self.prefix, artifact_path)
        if hit:
            cached_content = self.cache.get(hit)
            yield {
                "total_length": len(cached_content),
                "content": cached_content,
                "bytes_downloaded": len(cached_content)
            }
            return
        
        # Fetch from remote service
        url = f"{self.base_url}/{artifact_path}"
        response = None
        
        try:
            response = requests.get(url, stream=True, timeout=30)
            response.raise_for_status()
            
            # Get content length
            total_length = response.headers.get('content-length')
            if total_length:
                total_length = int(total_length)
            
            # Stream in chunks
            content_buffer = bytearray()
            chunk_size = 8192
            
            for chunk in response.iter_content(chunk_size=chunk_size):
                if chunk:
                    content_buffer.extend(chunk)
                    yield {
                        "total_length": total_length,
                        "content": chunk,
                        "bytes_downloaded": len(content_buffer),
                        "content_type": "application/octet-stream"
                    }
            
            # Cache complete content
            if content_buffer:
                self.cache.set(self.prefix, artifact_path, bytes(content_buffer))
                
        except requests.RequestException as e:
            yield {"error": f"Failed to fetch from MyService: {str(e)}"}
        finally:
            if response:
                response.close()
```

### Step 2: Register Backend

Add to `main.py` in the `initialize_backends()` function:

```python
def initialize_backends(config):
    # ... existing code ...
    
    for backend in config.get('backends', []):
        logging.info(f"Initializing backend: {backend['type']}")
        
        # ... existing backend types ...
        
        elif backend['type'] == 'myservice':
            from artifact_vault.backend_myservice import MyServiceBackend
            backends.append(MyServiceBackend(backend.get('config', {}), cache))
        
        else:
            logging.warning(f"Unknown backend type: {backend['type']}")
    
    return backends
```

### Step 3: Add Configuration Support

Update configuration documentation and sample config:

```yaml
# In config-sample.yml
backends:
  - type: myservice
    config:
      prefix: /myservice/
      base_url: https://api.myservice.com/artifacts
```

### Step 4: Test Your Backend

```bash
# Add to config.yml
python main.py --config config.yml --log-level DEBUG

# Test in another terminal
curl -v http://localhost:8080/myservice/some-artifact
```

## Backend Implementation Patterns

### Authentication Handling

```python
class AuthenticatedBackend:
    def __init__(self, config, cache):
        # ... basic setup ...
        self.username = config.get('username')
        self.password = config.get('password')
        self.token = None
    
    def _get_auth_headers(self):
        """Get authentication headers."""
        if self.username and self.password:
            import base64
            credentials = base64.b64encode(f"{self.username}:{self.password}".encode()).decode()
            return {'Authorization': f'Basic {credentials}'}
        elif self.token:
            return {'Authorization': f'Bearer {self.token}'}
        return {}
    
    def _authenticate(self):
        """Perform authentication and get token."""
        # Implementation specific to your service
        pass
```

### Error Handling

```python
def fetch(self, path):
    try:
        # ... fetch logic ...
        pass
    except requests.Timeout:
        yield {"error": "Request timed out"}
    except requests.ConnectionError:
        yield {"error": "Connection failed"}
    except requests.HTTPError as e:
        if e.response.status_code == 404:
            yield {"error": "Artifact not found"}
        elif e.response.status_code == 401:
            yield {"error": "Authentication required"}
        else:
            yield {"error": f"HTTP {e.response.status_code}: {str(e)}"}
    except Exception as e:
        yield {"error": f"Unexpected error: {str(e)}"}
```

### Custom Path Parsing

```python
def _parse_artifact_path(self, artifact_path):
    """Parse artifact path into components."""
    parts = artifact_path.strip('/').split('/')
    
    if len(parts) < 2:
        return None
        
    return {
        'namespace': parts[0],
        'name': parts[1],
        'version': parts[2] if len(parts) > 2 else 'latest'
    }

def fetch(self, path):
    artifact_path = path[len(self.prefix):]
    parsed = self._parse_artifact_path(artifact_path)
    
    if not parsed:
        yield {"error": f"Invalid artifact path: {artifact_path}"}
        return
    
    # Use parsed components...
```

## Testing

### Manual Testing

```bash
# Start server with debug logging
python main.py --config config.yml --log-level DEBUG

# Test backends individually
curl -v http://localhost:8080/http/test
curl -v http://localhost:8080/pypi/requests/
curl -v http://localhost:8080/dockerhub/library/hello-world/manifests/latest
```

### Integration Testing

Create test scripts to verify functionality:

```bash
#!/bin/bash
# test-backends.sh

set -e

echo "Testing HTTP backend..."
curl -f http://localhost:8080/apache/hadoop/common/hadoop-3.3.6/hadoop-3.3.6.tar.gz.asc > /dev/null
echo "✓ HTTP backend working"

echo "Testing PyPI backend..."
curl -f http://localhost:8080/pypi/requests/ > /dev/null
echo "✓ PyPI backend working"

echo "Testing DockerHub backend..."
curl -f http://localhost:8080/dockerhub/library/hello-world/manifests/latest > /dev/null
echo "✓ DockerHub backend working"

echo "All backends working!"
```

### Cache Testing

```bash
# Test cache functionality
curl http://localhost:8080/test/artifact > /dev/null  # First request (cache miss)
time curl http://localhost:8080/test/artifact > /dev/null  # Second request (cache hit)

# Verify cache files
find /tmp/artifact_cache_dev -type f -ls
```

## Code Style and Standards

### Python Style

Follow PEP 8 with these specifics:

```python
# Import order
import json
import base64
import requests
from urllib.parse import urljoin

# Class naming
class MyServiceBackend:

# Method naming
def can_handle(self, path):
def fetch(self, path):
def _private_method(self):

# Constants
DEFAULT_TIMEOUT = 30
CHUNK_SIZE = 8192

# Documentation
def fetch(self, path):
    """Fetch artifact with streaming support.
    
    Args:
        path: URL path to fetch
        
    Yields:
        Dict with content chunks and progress information
    """
```

### Error Handling Standards

```python
# Always yield error dictionaries, never raise in fetch()
def fetch(self, path):
    try:
        # ... implementation ...
    except Exception as e:
        yield {"error": f"Failed to fetch: {str(e)}"}
        return  # Always return after error

# Log errors for debugging
import logging
logging.error(f"Backend error: {str(e)}")
```

### Configuration Validation

```python
def __init__(self, config, cache):
    # Validate required fields
    required_fields = ['base_url']
    for field in required_fields:
        if not config.get(field):
            raise ValueError(f"Backend requires '{field}' in config")
    
    # Set defaults
    self.timeout = config.get('timeout', 30)
    self.chunk_size = config.get('chunk_size', 8192)
```

## Debugging

### Enable Debug Logging

```bash
python main.py --config config.yml --log-level DEBUG
```

### Debug HTTP Requests

```python
# Add to backend for debugging
import logging
logging.debug(f"Fetching URL: {url}")
logging.debug(f"Headers: {headers}")
```

### Cache Debugging

```python
# Debug cache operations
def fetch(self, path):
    hit = self.cache.has(self.prefix, artifact_path)
    if hit:
        logging.debug(f"Cache hit: {hit}")
    else:
        logging.debug(f"Cache miss for: {artifact_path}")
```

### Network Debugging

```bash
# Monitor network traffic
sudo tcpdump -i any port 8080

# Test with curl verbose
curl -v http://localhost:8080/test/artifact
```

## Performance Optimization

### Streaming Best Practices

```python
# Use appropriate chunk sizes
CHUNK_SIZE = 8192  # 8KB - good balance of memory and efficiency

# Stream immediately, don't buffer
for chunk in response.iter_content(chunk_size=CHUNK_SIZE):
    if chunk:
        yield {"content": chunk, ...}  # Yield immediately
```

### Caching Strategies

```python
# Cache complete files only after successful download
content_buffer = bytearray()
try:
    for chunk in response.iter_content(chunk_size=CHUNK_SIZE):
        content_buffer.extend(chunk)
        yield chunk_data
    
    # Only cache if complete download succeeded
    self.cache.set(self.prefix, artifact_path, bytes(content_buffer))
except Exception:
    # Don't cache partial downloads
    pass
```

### Connection Management

```python
# Use session for connection reuse
import requests

class OptimizedBackend:
    def __init__(self, config, cache):
        self.session = requests.Session()
        # Configure session defaults
        self.session.timeout = 30
    
    def fetch(self, path):
        response = self.session.get(url, stream=True)
```

## Contributing Guidelines

### Before Contributing

1. Check existing issues and pull requests
2. Discuss major changes in an issue first
3. Follow the coding standards above
4. Test your changes thoroughly

### Pull Request Process

1. Fork the repository
2. Create a feature branch: `git checkout -b feature-name`
3. Make your changes with tests
4. Update documentation as needed
5. Submit pull request with clear description

### Commit Message Format

```
type(scope): brief description

Longer description if needed

- Include bullet points for multiple changes
- Reference issues: fixes #123
```

Examples:
- `feat(backend): add MyService backend support`
- `fix(cache): handle permission errors gracefully`
- `docs(readme): update configuration examples`

## Deployment

### Production Checklist

- [ ] Use persistent cache directory
- [ ] Configure appropriate log levels
- [ ] Set up log rotation
- [ ] Monitor disk space
- [ ] Configure firewall rules
- [ ] Use environment variables for secrets
- [ ] Set up monitoring/alerting
- [ ] Plan backup strategy

### Systemd Service

```ini
# /etc/systemd/system/artifact-vault.service
[Unit]
Description=Artifact Vault Cache Server
After=network.target

[Service]
Type=simple
User=artifact-vault
WorkingDirectory=/opt/artifact-vault
ExecStart=/opt/artifact-vault/venv/bin/python main.py --config config.yml
Restart=always
RestartSec=10

[Install]
WantedBy=multi-user.target
```

### Docker Deployment

```dockerfile
FROM python:3.9-slim

WORKDIR /app
COPY requirements.txt .
RUN pip install -r requirements.txt

COPY . .

EXPOSE 8080
CMD ["python", "main.py", "--config", "config.yml"]
```

This development guide provides everything needed to understand, extend, and contribute to Artifact Vault. The modular architecture makes it straightforward to add new backends while maintaining consistency and reliability.
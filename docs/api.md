# API Reference

This document provides detailed API documentation for Artifact Vault's HTTP API and internal backend interfaces.

## HTTP API

Artifact Vault exposes a simple HTTP API for retrieving artifacts through various backends.

### Base URL

```
http://localhost:8080
```

### Request Format

All requests use HTTP GET method with the following URL structure:

```
GET /{backend_prefix}/{artifact_path}
```

Where:
- `{backend_prefix}`: The configured prefix for the backend (e.g., `/dockerhub`, `/pypi`, `/apache`)
- `{artifact_path}`: The path to the specific artifact within that backend

### Response Format

#### Success Response

**Status Code**: `200 OK`

**Headers**:
- `Content-Type`: `application/octet-stream`
- `Content-Length`: Total size in bytes (if known)

**Body**: Binary artifact data streamed in chunks

#### Error Response

**Status Code**: `404 Not Found`, `502 Bad Gateway`, or `500 Internal Server Error`

**Body**: Error message as plain text

### Endpoints by Backend

#### HTTP Backend

**Format**: `GET /{prefix}/{remote_path}`

**Example**:
```bash
curl http://localhost:8080/apache/hadoop/common/hadoop-3.3.6/hadoop-3.3.6.tar.gz
```

Maps to: `{base_url}/{remote_path}`

#### PyPI Backend

**Format**: `GET /{prefix}/{package_name}/`

**Example**:
```bash
curl http://localhost:8080/pypi/requests/
```

Returns PyPI package information or download links.

#### DockerHub Backend

**Format**: `GET /{prefix}/{repository}/{resource_type}/{identifier}`

**Resource Types**:
- `manifests`: Docker image manifests
- `blobs`: Docker image layers and blobs

**Examples**:
```bash
# Get image manifest
curl http://localhost:8080/dockerhub/library/ubuntu/manifests/latest

# Get specific blob/layer
curl http://localhost:8080/dockerhub/library/ubuntu/blobs/sha256:abc123...

# Get user repository manifest
curl http://localhost:8080/dockerhub/nginx/nginx/manifests/alpine
```

### Streaming Behavior

Artifact Vault streams all responses in chunks to minimize memory usage:

- **Chunk Size**: 8KB (8192 bytes)
- **Progress**: Real-time streaming with content-length when available
- **Caching**: Files are cached during streaming for subsequent requests

### Content Types

| Backend | Content-Type | Description |
|---------|--------------|-------------|
| HTTP | `application/octet-stream` | Generic binary content |
| PyPI | `text/html` or `application/octet-stream` | HTML pages or package files |
| DockerHub | `application/vnd.docker.distribution.manifest.v2+json` | Docker manifests |
| DockerHub | `application/octet-stream` | Docker blobs/layers |

## Backend Interface

All backends must implement the following interface:

### Class Interface

```python
class BackendInterface:
    def __init__(self, config: dict, cache: Cache):
        """Initialize backend with configuration and cache instance.
        
        Args:
            config: Backend-specific configuration dictionary
            cache: Cache instance for storing/retrieving artifacts
        """
        pass
    
    def can_handle(self, path: str) -> bool:
        """Determine if this backend can handle the given path.
        
        Args:
            path: URL path from HTTP request
            
        Returns:
            True if this backend should handle the request
        """
        pass
    
    def fetch(self, path: str) -> Iterator[dict]:
        """Fetch artifact and yield chunks with progress information.
        
        Args:
            path: URL path from HTTP request
            
        Yields:
            Dictionary with chunk data and progress information
        """
        pass
```

### Configuration Interface

Each backend receives a configuration dictionary with these common patterns:

```python
{
    "prefix": "/backend/",        # Required: URL prefix to match
    "timeout": 30,               # Optional: Request timeout in seconds
    # Backend-specific options...
}
```

### Fetch Method Response Format

The `fetch` method must yield dictionaries with the following structure:

#### Success Chunk

```python
{
    "total_length": int,         # Total file size in bytes (optional)
    "content": bytes,            # Chunk data
    "bytes_downloaded": int,     # Cumulative bytes downloaded
    "content_type": str,         # Content-Type header, default: 'application/octet-stream' (optional) 
}
```

#### Error Response

```python
{
    "error": str,               # Error message
}
```

### Cache Interface

Backends interact with the cache through these methods:

```python
class Cache:
    def has(self, prefix: str, name: str) -> Optional[str]:
        """Check if artifact exists in cache.
        
        Args:
            prefix: Backend prefix
            name: Artifact name/path
            
        Returns:
            File path if cached, None otherwise
        """
        pass
    
    def get(self, path: str) -> bytes:
        """Get cached artifact content.
        
        Args:
            path: File path from has() method
            
        Returns:
            Artifact content as bytes
        """
        pass
    
    def set(self, prefix: str, name: str, content: bytes, content_type = None) -> None:
        """Store artifact in cache.
        
        Args:
            prefix: Backend prefix
            name: Artifact name/path
            content: Artifact content as bytes
            content_type: HTTP content type (stored separately if specified)
        """
        pass
```

## Implementation Examples

### Basic Backend Implementation

```python
import requests
from typing import Iterator, Dict, Any

class MyBackend:
    def __init__(self, config: dict, cache):
        self.config = config
        self.cache = cache
        self.prefix = config.get('prefix', '/mybackend/')
        self.base_url = config.get('base_url', '')
        self.timeout = config.get('timeout', 30)
        
        if not self.base_url:
            raise ValueError(f"MyBackend {self.prefix} requires 'base_url'")
    
    def can_handle(self, path: str) -> bool:
        return path.startswith(self.prefix)
    
    def fetch(self, path: str) -> Iterator[Dict[str, Any]]:
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
        
        # Fetch from remote
        url = f"{self.base_url}/{artifact_path}"
        response = None
        
        try:
            response = requests.get(url, stream=True, timeout=self.timeout)
            response.raise_for_status()
            
            # Get content length
            total_length = response.headers.get('content-length')
            if total_length:
                total_length = int(total_length)
            
            # Stream and cache
            content_buffer = bytearray()
            chunk_size = 8192
            
            for chunk in response.iter_content(chunk_size=chunk_size):
                if chunk:
                    content_buffer.extend(chunk)
                    yield {
                        "total_length": total_length,
                        "content": chunk,
                        "bytes_downloaded": len(content_buffer)
                    }
            
            # Cache complete content
            if content_buffer:
                self.cache.add(self.prefix, artifact_path, bytes(content_buffer))
                
        except requests.RequestException as e:
            yield {"error": f"Failed to fetch: {str(e)}"}
        finally:
            if response:
                response.close()
```

### Authentication Example

```python
class AuthenticatedBackend:
    def __init__(self, config: dict, cache):
        # ... basic setup ...
        self.username = config.get('username')
        self.password = config.get('password')
        self.token = None
    
    def _get_auth_headers(self) -> dict:
        """Get authentication headers."""
        if self.token:
            return {'Authorization': f'Bearer {self.token}'}
        elif self.username and self.password:
            import base64
            credentials = base64.b64encode(
                f"{self.username}:{self.password}".encode()
            ).decode()
            return {'Authorization': f'Basic {credentials}'}
        return {}
    
    def _authenticate(self) -> None:
        """Perform authentication to get token."""
        auth_response = requests.post(
            f"{self.auth_url}/token",
            data={'username': self.username, 'password': self.password}
        )
        if auth_response.status_code == 200:
            self.token = auth_response.json()['token']
    
    def fetch(self, path: str) -> Iterator[Dict[str, Any]]:
        # ... cache check ...
        
        headers = self._get_auth_headers()
        if not headers and self.username:
            self._authenticate()
            headers = self._get_auth_headers()
        
        response = requests.get(url, headers=headers, stream=True)
        # ... rest of implementation
```

### Custom Path Parsing Example

```python
class StructuredBackend:
    def _parse_path(self, artifact_path: str) -> Optional[dict]:
        """Parse artifact path into structured components."""
        parts = artifact_path.strip('/').split('/')
        
        if len(parts) < 3:
            return None
        
        return {
            'namespace': parts[0],
            'name': parts[1],
            'version': parts[2],
            'extra': '/'.join(parts[3:]) if len(parts) > 3 else None
        }
    
    def fetch(self, path: str) -> Iterator[Dict[str, Any]]:
        artifact_path = path[len(self.prefix):]
        parsed = self._parse_path(artifact_path)
        
        if not parsed:
            yield {"error": f"Invalid path format: {artifact_path}"}
            return
        
        # Use structured components to build request
        url = f"{self.base_url}/{parsed['namespace']}/{parsed['name']}/versions/{parsed['version']}/download"
        # ... rest of implementation
```

## Error Handling Patterns

### Standard Error Responses

```python
# Network errors
yield {"error": "Connection timeout"}
yield {"error": "Connection refused"}
yield {"error": "DNS resolution failed"}

# HTTP errors
yield {"error": f"HTTP {response.status_code}: {response.reason}"}
yield {"error": "Authentication required"}
yield {"error": "Artifact not found"}
yield {"error": "Rate limited"}

# Application errors
yield {"error": "Invalid artifact path"}
yield {"error": "Configuration error"}
yield {"error": "Cache write failed"}
```

### Exception Handling Pattern

```python
def fetch(self, path: str) -> Iterator[Dict[str, Any]]:
    response = None
    try:
        # ... implementation ...
        
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
    finally:
        if response:
            response.close()
```

## Configuration Validation

### Required Field Validation

```python
def __init__(self, config: dict, cache):
    # Validate required fields
    required_fields = ['base_url']
    for field in required_fields:
        if not config.get(field):
            raise ValueError(f"Backend requires '{field}' in config")
    
    # Validate field types
    if 'timeout' in config and not isinstance(config['timeout'], (int, float)):
        raise ValueError("'timeout' must be a number")
    
    # Set defaults
    self.timeout = config.get('timeout', 30)
    self.chunk_size = config.get('chunk_size', 8192)
```

### URL Validation

```python
from urllib.parse import urlparse

def __init__(self, config: dict, cache):
    self.base_url = config.get('base_url', '')
    
    # Validate URL format
    parsed = urlparse(self.base_url)
    if not parsed.scheme or not parsed.netloc:
        raise ValueError(f"Invalid base_url: {self.base_url}")
    
    # Remove trailing slash for consistency
    self.base_url = self.base_url.rstrip('/')
```

## Testing Backends

### Unit Test Example

```python
import unittest
from unittest.mock import Mock, patch
from artifact_vault.backend_myservice import MyServiceBackend

class TestMyServiceBackend(unittest.TestCase):
    def setUp(self):
        self.config = {
            'prefix': '/test/',
            'base_url': 'https://example.com'
        }
        self.cache = Mock()
        self.backend = MyServiceBackend(self.config, self.cache)
    
    def test_can_handle(self):
        self.assertTrue(self.backend.can_handle('/test/artifact'))
        self.assertFalse(self.backend.can_handle('/other/artifact'))
    
    @patch('requests.get')
    def test_fetch_success(self, mock_get):
        # Mock response
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.headers = {'content-length': '100'}
        mock_response.iter_content.return_value = [b'chunk1', b'chunk2']
        mock_get.return_value = mock_response
        
        # Mock cache miss
        self.cache.has.return_value = None
        
        # Test fetch
        chunks = list(self.backend.fetch('/test/artifact'))
        
        self.assertEqual(len(chunks), 2)
        self.assertEqual(chunks[0]['content'], b'chunk1')
        self.assertEqual(chunks[1]['content'], b'chunk2')
        self.cache.add.assert_called_once()
    
    def test_fetch_cache_hit(self):
        # Mock cache hit
        self.cache.has.return_value = '/cache/path'
        self.cache.get.return_value = b'cached_content'
        
        # Test fetch
        chunks = list(self.backend.fetch('/test/artifact'))
        
        self.assertEqual(len(chunks), 1)
        self.assertEqual(chunks[0]['content'], b'cached_content')
```

### Integration Test Example

```python
import requests
import time

def test_backend_integration():
    # Start test server
    server_url = "http://localhost:8080"
    
    # Test artifact fetch
    response = requests.get(f"{server_url}/test/artifact", stream=True)
    assert response.status_code == 200
    
    # Measure first request time
    start_time = time.time()
    content1 = response.content
    first_request_time = time.time() - start_time
    
    # Test cache hit (should be faster)
    start_time = time.time()
    response2 = requests.get(f"{server_url}/test/artifact")
    content2 = response2.content
    second_request_time = time.time() - start_time
    
    # Verify content and performance
    assert content1 == content2
    assert second_request_time < first_request_time
    print(f"Cache improved performance: {first_request_time/second_request_time:.1f}x faster")
```

This API reference provides comprehensive documentation for both using and extending Artifact Vault's functionality.
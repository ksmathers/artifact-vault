# Artifact Vault

A high-performance read-through cache for binary artifacts that supports multiple backend sources including PyPI, DockerHub, Ubuntu/Debian APT, and generic HTTP/HTTPS servers. Artifact Vault provides transparent caching and streaming delivery of artifacts through a unified HTTP API.

## Overview

Artifact Vault acts as a caching proxy that sits between your applications and artifact repositories. When an artifact is requested, it checks the local cache first. If not found, it fetches the artifact from the appropriate backend, caches it locally, and streams it to the client. Subsequent requests for the same artifact are served directly from the cache.

### Key Features

- **Multiple Backend Support**: PyPI, DockerHub, and generic HTTP/HTTPS servers
- **Streaming Downloads**: Real-time progress tracking with efficient 8KB chunk streaming
- **Intelligent Caching**: Local filesystem-based cache with automatic cache management
- **HTTP API**: Simple REST-like interface for artifact retrieval
- **Production Ready**: Proper error handling, logging, and resource management
- **Docker Integration**: Works as a Docker registry mirror for faster image pulls

### Supported Backends

- **HTTP Backend**: Generic HTTP/HTTPS artifact caching with streaming support
- **PyPI Backend**: Python Package Index integration with custom index support
- **DockerHub Backend**: Docker Hub registry with authentication and manifest support
- **APT Backend**: Debian/Ubuntu package repository caching for .deb packages

## Quick Start

### Installation

```bash
git clone <repository-url>
cd artifact-vault
pip install -r requirements.txt  # Install dependencies if needed
```

### Basic Configuration

```bash
cp config-sample.yml config.yml
python main.py --config config.yml
```

The server starts on `localhost:8080` by default.

### Basic Usage

```bash
# Fetch artifacts through the proxy
curl http://localhost:8080/archive.apache.org/hadoop/common/hadoop-3.3.6/hadoop-3.3.6.tar.gz
curl http://localhost:8080/pypi/requests/
curl http://localhost:8080/dockerhub/library/ubuntu/manifests/latest
```

## Documentation

For detailed information, see the documentation in the [`docs/`](docs/) directory:

### 📖 User Guides
- **[Configuration Guide](docs/configuration.md)** - Complete configuration reference and examples
- **[Docker Integration](docs/docker-integration.md)** - Set up Docker to use Artifact Vault as a registry mirror
- **[Python pip Integration](docs/python-pip-integration.md)** - Configure pip to use Artifact Vault as a PyPI mirror
- **[APT Integration](docs/apt-integration.md)** - Configure APT to use Artifact Vault for Debian package caching
- **[Troubleshooting](docs/troubleshooting.md)** - Common issues, performance tuning, and debugging

### 🔧 Developer Resources
- **[Development Guide](docs/development.md)** - Architecture, adding backends, and contributing
- **[API Reference](docs/api.md)** - Backend interface and HTTP API documentation

## Architecture

### Components

- **Main Application** (`main.py`): HTTP server and request routing
- **Cache System** (`artifact_vault/cache.py`): Filesystem-based caching
- **Backend Plugins**: Pluggable system for different artifact sources
  - `backend_http.py`: Generic HTTP/HTTPS support
  - `backend_pypi.py`: Python Package Index integration
  - `backend_dockerhub.py`: Docker Hub registry support
  - `backend_apt.py`: Debian/Ubuntu APT repository support

### Request Flow

1. Client makes HTTP GET request → 2. Backend determined by URL prefix → 3. Check local cache → 4. If cached, stream from cache → 5. If not cached, fetch from remote with streaming → 6. Cache during streaming → 7. Client receives streamed content

## Performance Highlights

- **Streaming**: 8KB chunks minimize memory usage for large artifacts
- **Concurrent**: Handles multiple simultaneous requests efficiently
- **Caching**: Filesystem-based cache provides fast subsequent access
- **Network Optimized**: Connection reuse and proper timeout handling

## Security Considerations

- Validates URL paths before processing
- Configurable cache directory permissions
- Network access to configured backends only
- Consider rate limiting for production deployments

## Quick Links

- [Configuration Examples](docs/configuration.md#examples)
- [Docker Setup](docs/docker-integration.md#docker-daemon-configuration)
- [Python pip Setup](docs/python-pip-integration.md#pip-configuration-methods)
- [APT Setup](docs/apt-integration.md#client-configuration)
- [Adding New Backends](docs/development.md#adding-new-backends)
- [Troubleshooting](docs/troubleshooting.md#common-issues)

## License

[Add your license information here]

## Contributing

See [Development Guide](docs/development.md) for contribution guidelines and development setup instructions.

### Backend Configuration

Each backend is configured in the `backends` array with the following structure:

```yaml
backends:
  - type: <backend_type>
    config:
      prefix: <url_prefix>
      # backend-specific options
```

#### HTTP Backend Options

- `prefix`: URL prefix to match requests (e.g., `/apache/`)
- `base_url`: Base URL of the remote server (required)

#### PyPI Backend Options

- `prefix`: URL prefix to match requests (e.g., `/pypi/`)
- `index_url`: PyPI index URL (default: `https://pypi.org/simple/`)

#### DockerHub Backend Options

- `prefix`: URL prefix to match requests (e.g., `/dockerhub/`)
- `registry_url`: Docker registry URL (default: `https://registry-1.docker.io`)
- `auth_url`: Docker authentication URL (default: `https://auth.docker.io`)
- `username`: DockerHub username for authenticated access (optional)
- `password`: DockerHub password for authenticated access (optional)

## Architecture

### Components

1. **Main Application** (`main.py`): Entry point, configuration loading, and HTTP server setup
2. **Cache System** (`artifact_vault/cache.py`): Filesystem-based caching with automatic directory management
3. **Backend Plugins**: Pluggable backend system for different artifact sources
   - `backend_http.py`: Generic HTTP/HTTPS support with streaming
   - `backend_pypi.py`: Python Package Index integration
   - `backend_dockerhub.py`: Docker Hub registry support

### Request Flow

1. Client makes HTTP GET request to Artifact Vault
2. Server determines appropriate backend based on URL prefix
3. Backend checks local cache first
4. If cached, streams artifact directly from cache
5. If not cached, fetches from remote source with streaming
6. Artifact is cached locally during streaming
7. Client receives streamed content with progress indicators

### Caching Strategy

- **Cache Structure**: Organized by backend prefix and artifact path
- **Cache Location**: Configurable directory (default: `/tmp/artifact_vault_cache`)
- **Cache Validation**: File existence check, no TTL expiration
- **Streaming Cache**: Artifacts are cached during streaming to minimize memory usage

## Development

### Project Structure

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
    └── backend_dockerhub.py # DockerHub backend (if exists)
```

### Adding New Backends

To add a new backend:

1. Create a new backend class in `artifact_vault/backend_<name>.py`
2. Implement the required interface:
   ```python
   class MyBackend:
       def __init__(self, config, cache):
           # Initialize with configuration and cache
           pass
       
       def can_handle(self, path):
           # Return True if this backend handles the path
           pass
       
       def fetch(self, path):
           # Generator that yields artifact chunks
           # Format: {"total_length": int, "content": bytes, "bytes_downloaded": int}
           pass
   ```
3. Register the backend in `main.py` within the `initialize_backends()` function

### Testing

Test the server manually:
```bash
# Start the server
python main.py --config config.yml

# Test with curl in another terminal
curl -v http://localhost:8080/archive.apache.org/hadoop/common/hadoop-3.3.6/hadoop-3.3.6.tar.gz
```

Use the provided `prepare-cache.sh` script to test with real artifacts:
```bash
chmod +x prepare-cache.sh
./prepare-cache.sh
```

## Performance Considerations

- **Streaming**: Large artifacts are streamed in 8KB chunks to minimize memory usage
- **Concurrent Requests**: The HTTP server handles multiple concurrent requests
- **Cache Efficiency**: Filesystem-based cache provides fast access to frequently requested artifacts
- **Network Optimization**: Connection reuse and proper timeout handling for backend requests

## Security Considerations

- **Network Access**: Artifact Vault makes outbound HTTP requests to configured backends
- **File System**: Cache directory should have appropriate permissions
- **Input Validation**: URL paths are validated before processing
- **Resource Limits**: Consider implementing rate limiting for production deployments

## Troubleshooting

### Common Issues

1. **Backend not responding**: Check network connectivity and backend URLs
2. **Cache permission errors**: Ensure cache directory is writable
3. **Large file timeouts**: Adjust timeout settings for large artifacts
4. **Memory usage**: Monitor system resources with large concurrent downloads

### Logging

Enable debug logging for detailed troubleshooting:
```bash
python main.py --config config.yml --log-level DEBUG
```

## License

This software is licensed under the Gnu Public License Version 2.0 (GPLv2).   See the file 'LICENSE' for details.


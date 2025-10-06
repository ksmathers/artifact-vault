# Configuration Guide

This guide covers all configuration options for Artifact Vault, including global settings, backend configurations, and practical examples.

## Configuration File Format

Artifact Vault uses YAML configuration files. The main configuration sections are:

- **Global Settings**: Server binding, cache location, logging
- **Backends**: Array of backend configurations for different artifact sources

## Global Settings

### Basic Settings

```yaml
http_host: localhost           # Host address to bind HTTP server
http_port: 8080               # Port number for HTTP server
cache_dir: /tmp/artifact_cache # Directory for local artifact cache
log_level: INFO               # Logging verbosity level
```

### Global Setting Reference

| Setting | Default | Description |
|---------|---------|-------------|
| `http_host` | `localhost` | Host address to bind the HTTP server. Use `0.0.0.0` for external access |
| `http_port` | `8080` | Port number for the HTTP server |
| `cache_dir` | `/tmp/artifact_vault_cache` | Directory path for local artifact cache |
| `log_level` | `INFO` | Logging verbosity (`DEBUG`, `INFO`, `WARNING`, `ERROR`, `CRITICAL`) |

## Backend Configuration

Each backend is configured in the `backends` array:

```yaml
backends:
  - type: <backend_type>
    config:
      prefix: <url_prefix>
      # backend-specific options
```

### HTTP Backend

Generic HTTP/HTTPS artifact caching with streaming support.

```yaml
- type: http
  config:
    prefix: /apache/                    # URL prefix to match requests
    base_url: https://archive.apache.org # Base URL of remote server (required)
```

#### HTTP Backend Options

| Option | Required | Description |
|--------|----------|-------------|
| `prefix` | Yes | URL prefix to match requests (e.g., `/apache/`) |
| `base_url` | Yes | Base URL of the remote server |

### PyPI Backend

Python Package Index integration with custom index support.

```yaml
- type: pypi
  config:
    prefix: /pypi/                      # URL prefix to match requests
    index_url: https://pypi.org/simple/ # PyPI index URL (optional)
```

#### PyPI Backend Options

| Option | Required | Default | Description |
|--------|----------|---------|-------------|
| `prefix` | Yes | - | URL prefix to match requests (e.g., `/pypi/`) |
| `index_url` | No | `https://pypi.org/simple/` | PyPI index URL for custom PyPI servers |

### DockerHub Backend

Docker Hub registry with authentication and manifest support.

```yaml
- type: dockerhub
  config:
    prefix: /dockerhub/                      # URL prefix to match requests
    registry_url: https://registry-1.docker.io # Docker registry URL (optional)
    auth_url: https://auth.docker.io         # Docker auth URL (optional)
    username: your_username                  # DockerHub username (optional)
    password: your_password                  # DockerHub password (optional)
```

#### DockerHub Backend Options

| Option | Required | Default | Description |
|--------|----------|---------|-------------|
| `prefix` | Yes | - | URL prefix to match requests (e.g., `/dockerhub/`) |
| `registry_url` | No | `https://registry-1.docker.io` | Docker registry URL |
| `auth_url` | No | `https://auth.docker.io` | Docker authentication URL |
| `username` | No | - | DockerHub username for authenticated access |
| `password` | No | - | DockerHub password for authenticated access |

### APT Backend

APT repository backend for caching Debian packages and repository metadata.

```yaml
- type: apt
  config:
    prefix: /apt/                            # URL prefix to match requests
    mirror_url: http://archive.ubuntu.com/ubuntu/ # APT mirror URL (required)
    user_agent: Artifact-Vault APT Backend/1.0    # User agent string (optional)
    timeout: 30                              # Request timeout in seconds (optional)
    username: your_username                  # Username for private repos (optional)
    password: your_password                  # Password for private repos (optional)
```

#### APT Backend Options

| Option | Required | Default | Description |
|--------|----------|---------|-------------|
| `prefix` | Yes | - | URL prefix to match requests (e.g., `/apt/`) |
| `mirror_url` | Yes | - | APT mirror URL (e.g., `http://archive.ubuntu.com/ubuntu/`) |
| `user_agent` | No | `Artifact-Vault APT Backend/1.0` | User agent string for requests |
| `timeout` | No | `30` | Request timeout in seconds |
| `username` | No | - | Username for authenticated access to private repositories |
| `password` | No | - | Password for authenticated access to private repositories |

## Configuration Examples

### Development Configuration

Basic setup for local development:

```yaml
http_host: localhost
http_port: 8080
cache_dir: /tmp/artifact_cache
log_level: DEBUG

backends:
  - type: http
    config:
      prefix: /apache/
      base_url: https://archive.apache.org
  
  - type: pypi
    config:
      prefix: /pypi/
      index_url: https://pypi.org/simple
```

### Production Configuration

Production setup with external access and persistent cache:

```yaml
http_host: 0.0.0.0
http_port: 8080
cache_dir: /var/cache/artifact_vault
log_level: INFO

backends:
  - type: http
    config:
      prefix: /apache/
      base_url: https://archive.apache.org
  
  - type: pypi
    config:
      prefix: /pypi/
      index_url: https://pypi.org/simple
  
  - type: dockerhub
    config:
      prefix: /dockerhub/
      registry_url: https://registry-1.docker.io
      auth_url: https://auth.docker.io
```

### Docker Registry Mirror Configuration

Optimized for Docker registry mirroring:

```yaml
http_host: 0.0.0.0
http_port: 8080
cache_dir: /var/cache/artifact_vault
log_level: INFO

backends:
  - type: dockerhub
    config:
      prefix: /dockerhub/
      registry_url: https://registry-1.docker.io
      auth_url: https://auth.docker.io
      # Add credentials for private repositories
      username: your_dockerhub_username
      password: your_dockerhub_password
```

### Private Registry Configuration

Using with private Docker registries:

```yaml
http_host: 0.0.0.0
http_port: 8080
cache_dir: /var/cache/artifact_vault
log_level: INFO

backends:
  - type: dockerhub
    config:
      prefix: /dockerhub/
      registry_url: https://registry-1.docker.io
      auth_url: https://auth.docker.io
  
  - type: http
    config:
      prefix: /private-registry/
      base_url: https://my-private-registry.company.com
```

### Multi-Source Configuration

Complete setup with all backend types:

```yaml
http_host: 0.0.0.0
http_port: 8080
cache_dir: /var/cache/artifact_vault
log_level: INFO

backends:
  # Apache Archive
  - type: http
    config:
      prefix: /apache/
      base_url: https://archive.apache.org
  
  # Maven Central
  - type: http
    config:
      prefix: /maven/
      base_url: https://repo1.maven.org/maven2
  
  # PyPI
  - type: pypi
    config:
      prefix: /pypi/
      index_url: https://pypi.org/simple
  
  # Private PyPI
  - type: pypi
    config:
      prefix: /private-pypi/
      index_url: https://pypi.company.com/simple
  
  # Docker Hub
  - type: dockerhub
    config:
      prefix: /dockerhub/
      registry_url: https://registry-1.docker.io
      auth_url: https://auth.docker.io
      username: company_user
      password: secure_password
```

## Environment Variables

You can use environment variables in configuration files:

```yaml
http_host: ${HOST:-localhost}
http_port: ${PORT:-8080}
cache_dir: ${CACHE_DIR:-/tmp/artifact_cache}

backends:
  - type: dockerhub
    config:
      prefix: /dockerhub/
      username: ${DOCKER_USERNAME}
      password: ${DOCKER_PASSWORD}
```

## Configuration Validation

Artifact Vault validates configuration on startup:

- **Required fields**: Missing required backend options will cause startup failure
- **URL validation**: Backend URLs are checked for proper format
- **Directory permissions**: Cache directory must be writable
- **Port availability**: HTTP port must be available for binding

## Security Best Practices

### Credentials Management

```yaml
# DO NOT store credentials in plain text in production
# Use environment variables or secret management systems
backends:
  - type: dockerhub
    config:
      prefix: /dockerhub/
      username: ${DOCKER_USERNAME}
      password: ${DOCKER_PASSWORD}
```

### Network Security

```yaml
# Bind to specific interface in production
http_host: 10.0.1.100  # Internal network only

# Use HTTPS backends when possible
backends:
  - type: http
    config:
      prefix: /secure/
      base_url: https://secure-artifacts.company.com
```

### File Permissions

```bash
# Set appropriate cache directory permissions
sudo mkdir -p /var/cache/artifact_vault
sudo chown artifact-vault:artifact-vault /var/cache/artifact_vault
sudo chmod 755 /var/cache/artifact_vault
```

## Configuration Testing

Test your configuration before deployment:

```bash
# Validate configuration syntax
python main.py --config config.yml --log-level DEBUG

# Test backend connectivity
curl -v http://localhost:8080/apache/hadoop/common/hadoop-3.3.6/hadoop-3.3.6.tar.gz.asc
curl -v http://localhost:8080/pypi/requests/
curl -v http://localhost:8080/dockerhub/library/hello-world/manifests/latest
```

## Common Configuration Issues

### Backend Not Responding

```yaml
# Incorrect: Missing required base_url
- type: http
  config:
    prefix: /test/

# Correct: Include required base_url
- type: http
  config:
    prefix: /test/
    base_url: https://example.com
```

### Path Conflicts

```yaml
# Problematic: Overlapping prefixes
backends:
  - type: http
    config:
      prefix: /test/
      base_url: https://example1.com
  - type: http
    config:
      prefix: /test/sub/  # This will never be reached
      base_url: https://example2.com

# Better: Use distinct prefixes
backends:
  - type: http
    config:
      prefix: /example1/
      base_url: https://example1.com
  - type: http
    config:
      prefix: /example2/
      base_url: https://example2.com
```

### Permission Issues

```bash
# Check cache directory permissions
ls -la /var/cache/artifact_vault
# Should be writable by the user running Artifact Vault

# Fix permissions if needed
sudo chown -R $(whoami) /var/cache/artifact_vault
```
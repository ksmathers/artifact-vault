# Docker Multi-Registry Configuration

## Overview

The DockerHub backend now supports multiple Docker registries, allowing you to configure fallback behavior and prioritize private registries over public ones. When fetching an artifact, the backend will try each configured registry in order until the artifact is found.

## Features

- **Multiple Registry Support**: Configure multiple Docker registries (private and public)
- **Priority-based Fallback**: Registries are queried in the order they are defined
- **Name Conflict Resolution**: First registry with the artifact wins
- **Backward Compatible**: Single registry configuration still works as before

## Configuration

### Single Registry (Backward Compatible)

```yaml
backends:
  - type: dockerhub
    name: docker-hub
    config:
      prefix: /dockerhub/
      registry_url: https://registry-1.docker.io
      auth_url: https://auth.docker.io
      username: optional_username  # Optional
      password: optional_password  # Optional
```

### Multiple Registries

```yaml
backends:
  - type: dockerhub
    name: docker-multi
    config:
      prefix: /dockerhub/
      repositories:
        # Private registry (checked first)
        - registry_url: https://my-private-registry.company.com
          auth_url: https://my-private-registry.company.com/auth
          username: myuser
          password: mypassword
        
        # Corporate mirror (checked second)
        - registry_url: https://docker-mirror.company.com
          auth_url: https://docker-mirror.company.com/auth
        
        # Public Docker Hub (checked last)
        - registry_url: https://registry-1.docker.io
          auth_url: https://auth.docker.io
```

## Use Cases

### 1. Private Registry with Public Fallback

Configure your private registry first, with Docker Hub as a fallback:

```yaml
repositories:
  - registry_url: https://registry.mycompany.com
    auth_url: https://registry.mycompany.com/auth
    username: ${DOCKER_USER}
    password: ${DOCKER_PASS}
  - registry_url: https://registry-1.docker.io
    auth_url: https://auth.docker.io
```

This allows you to:
- Override public images with your own versions
- Automatically fall back to public images when not available privately
- Maintain a single URL prefix for all Docker images

### 2. Multiple Private Registries

Configure multiple private registries with different purposes:

```yaml
repositories:
  - registry_url: https://prod-registry.company.com
    auth_url: https://prod-registry.company.com/auth
    username: prod-user
    password: prod-pass
  - registry_url: https://dev-registry.company.com
    auth_url: https://dev-registry.company.com/auth
    username: dev-user
    password: dev-pass
  - registry_url: https://registry-1.docker.io
    auth_url: https://auth.docker.io
```

### 3. Geographic Mirrors

Configure geographic mirrors for better performance:

```yaml
repositories:
  - registry_url: https://asia-mirror.docker.io
    auth_url: https://auth.docker.io
  - registry_url: https://us-mirror.docker.io
    auth_url: https://auth.docker.io
  - registry_url: https://registry-1.docker.io
    auth_url: https://auth.docker.io
```

## How It Works

### Priority Resolution

When fetching an image like `/dockerhub/library/ubuntu/manifests/latest`:

1. The backend checks the cache first
2. If not cached, it tries the first configured repository
3. If the artifact is not found or authentication fails, it tries the next repository
4. This continues until the artifact is found or all repositories are exhausted
5. The artifact is cached using a single cache key, regardless of which repository provided it

### Authentication

Each repository can have its own authentication credentials:
- Anonymous access (no username/password)
- Basic authentication (username/password)
- Token-based authentication is handled automatically by the Docker Registry API

### Error Handling

- **404 errors**: The backend silently tries the next repository
- **401 errors**: Authentication failure, tries the next repository
- **Network errors**: Tries the next repository
- **Other errors**: Logged and the next repository is tried

If all repositories fail, the last error is returned to the client.

## Architecture

The refactored implementation consists of two classes:

### DockerRepository

Handles operations for a single Docker registry:
- Authentication token management
- Artifact fetching (manifests and blobs)
- Error handling

### DockerHubBackend

Manages multiple DockerRepository instances:
- Path parsing and validation
- Cache management
- Multi-repository fallback logic
- Priority-based conflict resolution

## Example: Dockerfile Configuration

```dockerfile
FROM ubuntu:20.04

# Configure docker daemon to use the artifact vault
# All docker pull operations will be proxied through the cache
ARG DOCKER_MIRROR=http://artifact-vault:8080/dockerhub/

# The cache will try:
# 1. Private registry (if configured)
# 2. Corporate mirror (if configured)
# 3. Public Docker Hub (fallback)
```

## Testing

Test your multi-registry configuration:

```bash
# Start the artifact vault
python main.py --config config.yml

# Test fetching a manifest
curl -v http://localhost:8080/dockerhub/library/ubuntu/manifests/latest

# Test fetching a blob
curl -v http://localhost:8080/dockerhub/library/ubuntu/blobs/sha256:abc123...
```

Check the logs to see which registry was used:
```
INFO: Fetching from https://my-private-registry.company.com
INFO: Not found, trying next registry
INFO: Fetching from https://registry-1.docker.io
INFO: Success, caching artifact
```

## Migration Guide

### Existing Single Registry Configuration

Your existing configuration continues to work without changes:

```yaml
# This still works!
backends:
  - type: dockerhub
    config:
      prefix: /dockerhub/
      registry_url: https://registry-1.docker.io
```

### Migrating to Multiple Registries

To add more registries, convert your configuration:

**Before:**
```yaml
backends:
  - type: dockerhub
    config:
      prefix: /dockerhub/
      registry_url: https://registry-1.docker.io
      auth_url: https://auth.docker.io
```

**After:**
```yaml
backends:
  - type: dockerhub
    config:
      prefix: /dockerhub/
      repositories:
        - registry_url: https://my-private-registry.com
          auth_url: https://my-private-registry.com/auth
          username: myuser
          password: mypassword
        - registry_url: https://registry-1.docker.io
          auth_url: https://auth.docker.io
```

## Performance Considerations

- **Caching**: Once an artifact is cached, no registry lookup is needed
- **Failover**: Failed registries add latency; prioritize reliable registries first
- **Authentication**: Token caching reduces authentication overhead
- **Network**: Consider network proximity when ordering registries

## Security Considerations

- Store credentials securely (use environment variables or secret management)
- Use HTTPS for all registry URLs
- Consider network policies to restrict registry access
- Audit logs to track which registries are being used

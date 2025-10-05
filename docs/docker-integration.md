# Docker Integration Guide

Artifact Vault can act as a pull-through cache for Docker images, significantly speeding up repeated pulls and reducing bandwidth usage. This guide covers how to configure Docker to use Artifact Vault as a registry mirror.

## Overview

When configured as a Docker registry mirror, Artifact Vault:
- Caches Docker images and layers locally
- Serves subsequent requests from cache (much faster)
- Reduces bandwidth usage and Docker Hub rate limiting
- Provides offline access to previously cached images

## Docker Configuration Methods

### Method 1: Docker Daemon Configuration (Recommended)

Configure Docker daemon to use Artifact Vault as a registry mirror by editing `/etc/docker/daemon.json`:

```json
{
  "registry-mirrors": ["http://localhost:8080/dockerhub"]
}
```

**Location of daemon.json by platform:**
- **Linux**: `/etc/docker/daemon.json`
- **macOS**: `~/.docker/daemon.json` (or via Docker Desktop Settings)
- **Windows**: `%programdata%\docker\config\daemon.json` (or via Docker Desktop Settings)

After updating the configuration, restart Docker:

```bash
# Linux
sudo systemctl restart docker

# macOS/Windows with Docker Desktop
# Restart Docker Desktop application
```

### Method 2: Docker Desktop GUI Configuration

**For Docker Desktop users (macOS/Windows):**

1. Open Docker Desktop
2. Go to Settings/Preferences
3. Navigate to "Docker Engine"
4. Add the registry mirror to the JSON configuration:
   ```json
   {
     "registry-mirrors": ["http://localhost:8080/dockerhub"]
   }
   ```
5. Click "Apply & Restart"

### Method 3: Manual Registry Specification

For advanced use cases, you can configure individual registries (requires more complex setup):

```bash
# This method requires additional registry configuration
# and is typically used for private registries
```

## Artifact Vault Configuration for Docker

Ensure your `config.yml` includes the DockerHub backend:

```yaml
http_host: 0.0.0.0  # Allow external connections (important!)
http_port: 8080
cache_dir: /var/cache/artifact_vault  # Use persistent storage
log_level: INFO

backends:
  - type: dockerhub
    config:
      prefix: /dockerhub
      registry_url: https://registry-1.docker.io
      auth_url: https://auth.docker.io
      # Optional: Add credentials for private repositories or higher rate limits
      # username: your_dockerhub_username
      # password: your_dockerhub_password
```

**Important Configuration Notes:**
- Use `http_host: 0.0.0.0` to allow Docker daemon to connect
- Consider using a persistent cache directory like `/var/cache/artifact_vault`
- Add credentials to avoid Docker Hub rate limiting

## Docker Compose Integration

For Docker Compose projects, the daemon configuration automatically applies to all services. No additional configuration needed in your `docker-compose.yml` files.

```yaml
# Your existing docker-compose.yml works unchanged
version: '3.8'
services:
  web:
    image: nginx:latest  # Will use the configured mirror
    ports:
      - "80:80"
  
  app:
    image: python:3.9    # Will also use the mirror
    volumes:
      - .:/app
```

## Verification and Testing

### Step 1: Start Artifact Vault

```bash
python main.py --config config.yml --log-level INFO
```

### Step 2: Test the Backend Directly

```bash
# Test that the DockerHub backend is working
curl -v http://localhost:8080/dockerhub/library/hello-world/manifests/latest
```

### Step 3: Test Docker Integration

```bash
# Clear local images first (optional)
docker image prune -a

# Pull an image - should show caching activity in Artifact Vault logs
docker pull ubuntu:latest

# Pull the same image again - should be much faster from cache
docker pull ubuntu:latest
```

### Step 4: Verify Mirror Usage

Check that Docker is using the mirror:

```bash
# Check Docker daemon configuration
docker system info | grep -A 10 "Registry Mirrors"

# Should show something like:
# Registry Mirrors:
#  http://localhost:8080/dockerhub
```

## Performance Benefits

### Before and After Comparison

**Without Artifact Vault:**
```bash
$ time docker pull ubuntu:latest
# First pull: ~30 seconds (depending on connection)
# Second pull: ~10 seconds (Docker's local cache)
```

**With Artifact Vault:**
```bash
$ time docker pull ubuntu:latest
# First pull: ~30 seconds (cached by Artifact Vault)
# Second pull: ~2 seconds (served from Artifact Vault cache)
# Subsequent pulls on other machines: ~5 seconds (from network cache)
```

### Benefits Summary

- **Faster Builds**: Cached base images speed up Docker builds significantly
- **Reduced Bandwidth**: Images downloaded once and reused across the network
- **Offline Development**: Previously cached images remain available without internet
- **Cost Savings**: Reduced data transfer costs in cloud environments
- **Reliability**: Less dependency on Docker Hub availability and rate limits
- **Team Efficiency**: Shared cache across development team

## Advanced Configuration

### Authentication for Private Repositories

```yaml
backends:
  - type: dockerhub
    config:
      prefix: /dockerhub
      registry_url: https://registry-1.docker.io
      auth_url: https://auth.docker.io
      username: ${DOCKER_USERNAME}  # Use environment variables
      password: ${DOCKER_PASSWORD}
```

### Multiple Registry Support

```yaml
backends:
  # Docker Hub (official)
  - type: dockerhub
    config:
      prefix: /dockerhub
      registry_url: https://registry-1.docker.io
      auth_url: https://auth.docker.io
  
  # Private registry via HTTP backend
  - type: http
    config:
      prefix: /private-registry
      base_url: https://registry.company.com
```

### Network Configuration

For multi-host setups:

```yaml
# Artifact Vault configuration
http_host: 0.0.0.0
http_port: 8080

# Docker daemon.json on client machines
{
  "registry-mirrors": ["http://artifact-vault-server:8080/dockerhub"]
}
```

## Troubleshooting

### Common Issues

#### 1. Docker not using the mirror

**Symptoms:**
- Docker pulls are still slow
- No activity in Artifact Vault logs during pulls

**Solutions:**
```bash
# Verify daemon.json syntax
cat /etc/docker/daemon.json
python -m json.tool /etc/docker/daemon.json

# Ensure Docker was restarted
sudo systemctl restart docker

# Check Docker daemon logs
sudo journalctl -u docker.service -f
```

#### 2. Connection refused errors

**Symptoms:**
```
Error response from daemon: Get http://localhost:8080/dockerhub/...
```

**Solutions:**
```bash
# Ensure Artifact Vault is bound to 0.0.0.0, not localhost
# In config.yml:
http_host: 0.0.0.0

# Check if service is running
curl http://localhost:8080/dockerhub/library/hello-world/manifests/latest

# Check firewall settings
sudo ufw status
sudo iptables -L
```

#### 3. Authentication errors

**Symptoms:**
```
Error response from daemon: pull access denied for private/repo
```

**Solutions:**
```bash
# Add credentials to Artifact Vault config
# Test credentials work directly
docker login

# Verify credentials in Artifact Vault
curl -H "Authorization: Bearer $(docker-credential-desktop get <<< 'https://index.docker.io/v1/')" \
  http://localhost:8080/dockerhub/private/repo/manifests/latest
```

#### 4. Cache not working

**Symptoms:**
- Pulls are still slow on repeated attempts
- Cache directory empty

**Solutions:**
```bash
# Check cache directory permissions
ls -la /var/cache/artifact_vault
sudo chown -R $(whoami) /var/cache/artifact_vault

# Monitor disk space
df -h /var/cache/artifact_vault

# Verify backend prefix matches mirror URL
# Mirror URL: http://localhost:8080/dockerhub
# Backend prefix: /dockerhub  (must match!)
```

### Debug Commands

#### Test Artifact Vault Backend

```bash
# Test manifest retrieval
curl -v http://localhost:8080/dockerhub/library/ubuntu/manifests/latest

# Test blob retrieval (use digest from manifest)
curl -v http://localhost:8080/dockerhub/library/ubuntu/blobs/sha256:abc123...
```

#### Check Docker Configuration

```bash
# View current Docker daemon configuration
docker system info | grep -A 10 "Registry Mirrors"

# Check daemon.json
cat /etc/docker/daemon.json

# Test Docker pull with verbose output
docker pull --progress=plain ubuntu:latest
```

#### Monitor Cache Activity

```bash
# Watch cache directory for new files
watch -n 1 'find /var/cache/artifact_vault -type f | wc -l'

# Monitor cache size
watch -n 1 'du -sh /var/cache/artifact_vault'

# Watch Artifact Vault logs
python main.py --config config.yml --log-level DEBUG
```

## Production Deployment

### System Requirements

- **Storage**: Plan for 10-100GB+ cache storage depending on usage
- **Memory**: 1-4GB RAM for typical workloads
- **Network**: Gigabit networking recommended for optimal performance
- **CPU**: 2+ cores for handling concurrent requests

### Deployment Considerations

```yaml
# Production configuration example
http_host: 0.0.0.0
http_port: 8080
cache_dir: /var/cache/artifact_vault
log_level: INFO

backends:
  - type: dockerhub
    config:
      prefix: /dockerhub
      registry_url: https://registry-1.docker.io
      auth_url: https://auth.docker.io
      username: ${DOCKER_USERNAME}
      password: ${DOCKER_PASSWORD}
```

### Monitoring

```bash
# Set up cache size monitoring
du -sh /var/cache/artifact_vault

# Monitor hit rates in logs
grep "cache hit" /var/log/artifact-vault.log

# Set up disk space alerts
df -h /var/cache/artifact_vault
```

### Backup Strategy

```bash
# Backup frequently used images
tar -czf docker-cache-backup.tar.gz /var/cache/artifact_vault/dockerhub/

# Scheduled cleanup of old cache entries
find /var/cache/artifact_vault -type f -atime +30 -delete
```

### Security

```bash
# Use HTTPS in production (requires reverse proxy)
# nginx example:
server {
    listen 443 ssl;
    server_name artifact-vault.company.com;
    
    location / {
        proxy_pass http://localhost:8080;
        proxy_set_header Host $host;
    }
}

# Update Docker daemon configuration
{
  "registry-mirrors": ["https://artifact-vault.company.com/dockerhub"]
}
```
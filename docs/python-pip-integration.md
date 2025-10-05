# Python pip Integration Guide

Artifact Vault can act as a caching proxy for Python packages from PyPI (Python Package Index), significantly speeding up package installations and reducing bandwidth usage. This guide covers how to configure pip and other Python tools to use Artifact Vault as a package index mirror.

## Overview

When configured as a PyPI mirror, Artifact Vault:
- Caches Python packages (.whl files, tarballs) locally
- Serves subsequent installations from cache (much faster)
- Reduces bandwidth usage and dependency on PyPI availability
- Provides offline access to previously cached packages
- Works with pip, poetry, pipenv, and other Python package managers

## pip Configuration Methods

### Method 1: pip Configuration File (Recommended)

Create or edit pip's configuration file to use Artifact Vault as the default index:

**Location of pip.conf/pip.ini by platform:**
- **Linux/macOS**: `~/.pip/pip.conf` or `~/.config/pip/pip.conf`
- **Windows**: `%APPDATA%\pip\pip.ini` or `%USERPROFILE%\pip\pip.ini`

**Configuration content:**
```ini
[global]
index-url = http://localhost:8080/pypi/simple
```

**For system-wide configuration:**
- **Linux**: `/etc/pip.conf`
- **macOS**: `/Library/Application Support/pip/pip.conf`
- **Windows**: `C:\ProgramData\pip\pip.ini`

### Method 2: Environment Variables

Set environment variables to configure pip globally:

```bash
# Linux/macOS
export PIP_INDEX_URL=http://localhost:8080/pypi/simple
export PIP_TRUSTED_HOST=localhost
export PIP_EXTRA_INDEX_URL=https://pypi.org/simple

# Windows (Command Prompt)
set PIP_INDEX_URL=http://localhost:8080/pypi/simple
set PIP_TRUSTED_HOST=localhost
set PIP_EXTRA_INDEX_URL=https://pypi.org/simple

# Windows (PowerShell)
$env:PIP_INDEX_URL="http://localhost:8080/pypi/simple"
$env:PIP_TRUSTED_HOST="localhost"
$env:PIP_EXTRA_INDEX_URL="https://pypi.org/simple"
```

### Method 3: Command Line Options

Use pip with explicit index options for individual commands:

```bash
# Install a package using Artifact Vault
pip install --index-url http://localhost:8080/pypi/simple requests

# Install with fallback to PyPI
pip install --index-url http://localhost:8080/pypi/simple \
            --extra-index-url https://pypi.org/simple \
            requests numpy pandas
```

### Method 4: requirements.txt Configuration

Add index configuration directly to your requirements.txt:

```txt
--index-url http://localhost:8080/pypi/simple
--extra-index-url https://pypi.org/simple

requests>=2.25.0
numpy>=1.21.0
pandas>=1.3.0
flask>=2.0.0
```

## Artifact Vault Configuration for PyPI

Ensure your `config.yml` includes the PyPI backend:

```yaml
http_host: 0.0.0.0  # Allow external connections 
http_port: 8080
cache_dir: /var/cache/artifact_vault  # Use persistent storage
log_level: INFO

backends:
  - type: pypi
    config:
      prefix: /pypi/
      index_url: https://pypi.org/simple
      # Optional: For private PyPI servers
      # username: your_pypi_username
      # password: your_pypi_password
```

**Configuration Notes:**
- Use `http_host: 0.0.0.0` to allow external connections
- Consider using persistent cache directory
- The `prefix: /pypi` must match the URL used in pip configuration
- `index_url` should point to the upstream PyPI simple index

## Python Tool Integration

### Poetry Integration

Configure Poetry to use Artifact Vault:

```bash
# Configure Poetry to use Artifact Vault as primary source
poetry source add --priority=primary artifact-vault http://localhost:8080/pypi/simple

# Or modify pyproject.toml directly
```

**pyproject.toml configuration:**
```toml
[[tool.poetry.source]]
name = "artifact-vault"
url = "http://localhost:8080/pypi/simple"
priority = "primary"

[[tool.poetry.source]]
name = "pypi"
url = "https://pypi.org/simple"
priority = "supplemental"
```

### pipenv Integration

Configure pipenv through environment variables or Pipfile:

```bash
# Environment variable method
export PIPENV_PYPI_MIRROR=http://localhost:8080/pypi/simple
pipenv install requests
```

**Pipfile configuration:**
```toml
[[source]]
url = "http://localhost:8080/pypi/simple"
verify_ssl = false
name = "artifact-vault"

[[source]]
url = "https://pypi.org/simple"
verify_ssl = true
name = "pypi"

[packages]
requests = "*"
numpy = "*"
```

### conda Integration

For conda environments, you can still use pip with Artifact Vault:

```bash
# Activate conda environment
conda activate myenv

# Configure pip within the environment
pip config set global.index-url http://localhost:8080/pypi/simple
pip config set global.trusted-host localhost
pip config set global.extra-index-url https://pypi.org/simple

# Install packages
pip install requests pandas
```

### Virtual Environment Integration

Works seamlessly with virtual environments:

```bash
# Create and activate virtual environment
python -m venv myenv
source myenv/bin/activate  # Linux/macOS
# myenv\Scripts\activate     # Windows

# Configure pip for this environment
pip config set global.index-url http://localhost:8080/pypi/simple
pip config set global.trusted-host localhost

# Install packages
pip install -r requirements.txt
```

## Verification and Testing

### Step 1: Start Artifact Vault

```bash
python main.py --config config.yml --log-level INFO
```

### Step 2: Test PyPI Backend Directly

```bash
# Test that PyPI backend is working
curl -v http://localhost:8080/pypi/simple/
curl -v http://localhost:8080/pypi/simple/requests/
```

### Step 3: Test pip Integration

```bash
# Clear pip cache first (optional)
pip cache purge

# Install a package - should show caching activity in Artifact Vault logs
pip install --index-url http://localhost:8080/pypi/simple --trusted-host localhost requests

# Install the same package again - should be faster from cache
pip uninstall requests -y
pip install --index-url http://localhost:8080/pypi/simple --trusted-host localhost requests
```

### Step 4: Verify Configuration

```bash
# Check pip configuration
pip config list

# Show pip cache location
pip cache dir

# Test with verbose output
pip install --index-url http://localhost:8080/pypi/simple --trusted-host localhost --verbose requests
```

## Performance Benefits

### Before and After Comparison

**Without Artifact Vault:**
```bash
$ time pip install pandas numpy matplotlib
# First install: ~60 seconds (downloading from PyPI)
```

**With Artifact Vault:**
```bash
$ time pip install pandas numpy matplotlib
# First install: ~60 seconds (cached by Artifact Vault)
# Subsequent installs: ~5 seconds (served from local cache)
# Team members: ~10 seconds (from network cache)
```

### Benefits Summary

- **Faster Installations**: Cached packages install in seconds instead of minutes
- **Reduced Bandwidth**: Packages downloaded once and reused across projects
- **Offline Development**: Previously cached packages available without internet
- **Build Reliability**: Less dependency on PyPI availability during CI/CD
- **Cost Savings**: Reduced data transfer costs in cloud environments
- **Team Efficiency**: Shared cache across development team

## Advanced Configuration

### Private PyPI Server Support

```yaml
backends:
  # Public PyPI (cached)
  - type: pypi
    config:
      prefix: /pypi
      index_url: https://pypi.org/simple
  
  # Private company PyPI
  - type: pypi
    config:
      prefix: /private-pypi
      index_url: https://pypi.company.com/simple
      username: ${PRIVATE_PYPI_USERNAME}
      password: ${PRIVATE_PYPI_PASSWORD}
```

**pip configuration for multiple sources:**
```ini
[global]
index-url = http://localhost:8080/pypi/simple
extra-index-url = http://localhost:8080/private-pypi/simple
                  https://pypi.org/simple
trusted-host = localhost
```

### Development vs Production Configuration

**Development (pip.conf):**
```ini
[global]
index-url = http://localhost:8080/pypi/simple
trusted-host = localhost
extra-index-url = https://pypi.org/simple
timeout = 60
```

**Production/CI (environment variables):**
```bash
export PIP_INDEX_URL=http://artifact-vault.company.com/pypi/simple
export PIP_TRUSTED_HOST=artifact-vault.company.com
export PIP_EXTRA_INDEX_URL=https://pypi.org/simple
export PIP_TIMEOUT=120
```

### Docker Integration for Python Projects

**Dockerfile with Artifact Vault:**
```dockerfile
FROM python:3.9-slim

# Configure pip to use Artifact Vault
ENV PIP_INDEX_URL=http://artifact-vault:8080/pypi/simple
ENV PIP_TRUSTED_HOST=artifact-vault
ENV PIP_EXTRA_INDEX_URL=https://pypi.org/simple

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .
CMD ["python", "app.py"]
```

**docker-compose.yml:**
```yaml
version: '3.8'
services:
  artifact-vault:
    build: .
    ports:
      - "8080:8080"
    volumes:
      - ./cache:/var/cache/artifact_vault
  
  python-app:
    build: ./app
    depends_on:
      - artifact-vault
    environment:
      - PIP_INDEX_URL=http://artifact-vault:8080/pypi/simple
      - PIP_TRUSTED_HOST=artifact-vault
```

## Troubleshooting

### Common Issues

#### 1. pip not using the configured index

**Symptoms:**
- pip still downloads from PyPI directly
- No activity in Artifact Vault logs during pip install

**Solutions:**
```bash
# Verify pip configuration
pip config list

# Check environment variables
echo $PIP_INDEX_URL

# Test with explicit options
pip install --index-url http://localhost:8080/pypi/simple --trusted-host localhost --verbose requests
```

#### 2. SSL/TLS verification errors

**Symptoms:**
```
WARNING: The repository located at http://localhost:8080 is not a trusted host
SSL: CERTIFICATE_VERIFY_FAILED
```

**Solutions:**
```bash
# Add to pip configuration
pip config set global.trusted-host localhost

# Or use command line option
pip install --trusted-host localhost --index-url http://localhost:8080/pypi/simple requests
```

#### 3. Package not found errors

**Symptoms:**
```
ERROR: Could not find a version that satisfies the requirement somepackage
```

**Solutions:**
```bash
# Check if package exists on PyPI
curl -v http://localhost:8080/pypi/simple/somepackage/

# Add fallback to PyPI
pip config set global.extra-index-url https://pypi.org/simple

# Test with PyPI fallback
pip install --index-url http://localhost:8080/pypi/simple \
           --extra-index-url https://pypi.org/simple \
           --trusted-host localhost \
           somepackage
```

#### 4. Cache not working

**Symptoms:**
- Repeated installations still slow
- Cache directory empty

**Solutions:**
```bash
# Check Artifact Vault configuration
grep -A 5 "type: pypi" config.yml

# Verify cache directory permissions
ls -la /var/cache/artifact_vault/pypi/

# Check for cache writes in logs
tail -f /var/log/artifact-vault.log | grep "cache"
```

### Debug Commands

#### Test Artifact Vault PyPI Backend

```bash
# Test simple index
curl -v http://localhost:8080/pypi/simple/

# Test specific package
curl -v http://localhost:8080/pypi/simple/requests/

# Test package download
curl -v http://localhost:8080/pypi/packages/source/r/requests/requests-2.28.1.tar.gz
```

#### Debug pip Configuration

```bash
# Show all pip configuration
pip config list

# Show pip cache information
pip cache info

# Debug package installation
pip install --index-url http://localhost:8080/pypi/simple --trusted-host localhost --verbose --dry-run requests
```

#### Monitor Cache Activity

```bash
# Watch cache directory for new files
watch -n 1 'find /var/cache/artifact_vault/pypi -type f | wc -l'

# Monitor cache size
watch -n 1 'du -sh /var/cache/artifact_vault/pypi'

# Watch Artifact Vault logs
tail -f /var/log/artifact-vault.log | grep pypi
```

## Production Deployment

### System Requirements

- **Storage**: Plan for 1-10GB+ cache storage for Python packages
- **Memory**: 512MB-2GB RAM for typical workloads
- **Network**: Good connectivity to PyPI for initial downloads
- **CPU**: 1-2 cores sufficient for most use cases

### Production Configuration

```yaml
# Production Artifact Vault configuration
http_host: 0.0.0.0
http_port: 8080
cache_dir: /var/cache/artifact_vault
log_level: INFO

backends:
  - type: pypi
    config:
      prefix: /pypi
      index_url: https://pypi.org/simple
      timeout: 120  # Longer timeout for large packages
```

### Monitoring Python Package Cache

```bash
# Monitor cache hit rates
grep -c "cache hit" /var/log/artifact-vault.log | tail -1
grep -c "cache miss" /var/log/artifact-vault.log | tail -1

# Find most popular packages
find /var/cache/artifact_vault/pypi -name "*.whl" -o -name "*.tar.gz" | \
  xargs ls -la | sort -k 8 | tail -10

# Cache size by package
du -sh /var/cache/artifact_vault/pypi/*/ | sort -hr | head -10
```

### Backup Strategy

```bash
# Backup popular packages
find /var/cache/artifact_vault/pypi -name "*.whl" -size +1M -exec cp {} /backup/python-packages/ \;

# Backup requirements files
tar -czf python-requirements-$(date +%Y%m%d).tar.gz \
    $(find . -name requirements.txt -o -name pyproject.toml -o -name Pipfile)
```

### Security Considerations

```bash
# Use HTTPS in production (nginx reverse proxy)
server {
    listen 443 ssl;
    server_name pypi-cache.company.com;
    
    location /pypi {
        proxy_pass http://localhost:8080/pypi;
        proxy_set_header Host $host;
    }
}

# Update pip configuration for HTTPS
pip config set global.index-url https://pypi-cache.company.com/pypi/simple
```

## CI/CD Integration

### GitHub Actions

```yaml
name: Python CI
on: [push, pull_request]

jobs:
  test:
    runs-on: ubuntu-latest
    steps:
    - uses: actions/checkout@v3
    - uses: actions/setup-python@v4
      with:
        python-version: '3.9'
    
    - name: Configure pip
      run: |
        pip config set global.index-url http://artifact-vault.company.com/pypi/simple
        pip config set global.trusted-host artifact-vault.company.com
        pip config set global.extra-index-url https://pypi.org/simple
    
    - name: Install dependencies
      run: pip install -r requirements.txt
    
    - name: Run tests
      run: python -m pytest
```

### Jenkins Pipeline

```groovy
pipeline {
    agent any
    environment {
        PIP_INDEX_URL = 'http://artifact-vault:8080/pypi/simple'
        PIP_TRUSTED_HOST = 'artifact-vault'
        PIP_EXTRA_INDEX_URL = 'https://pypi.org/simple'
    }
    stages {
        stage('Install Dependencies') {
            steps {
                sh 'pip install -r requirements.txt'
            }
        }
        stage('Test') {
            steps {
                sh 'python -m pytest'
            }
        }
    }
}
```

This comprehensive guide provides everything needed to integrate Python pip with Artifact Vault, from basic setup to production deployment and troubleshooting.
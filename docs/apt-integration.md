# APT Integration Guide

This guide shows how to configure APT (Advanced Package Tool) to use the Artifact Vault as a proxy for Debian package repositories.

## Overview

The APT backend allows you to cache Debian packages (.deb files), repository metadata (Release files, Packages.gz), and indices through the Artifact Vault. This provides several benefits:

- **Faster package installs**: Frequently used packages are cached locally
- **Bandwidth savings**: Reduce internet bandwidth usage in your organization
- **Offline capability**: Continue installing cached packages during network outages
- **Multiple Ubuntu/Debian mirror support**: Proxy multiple repositories through a single cache

## APT Backend Configuration

First, configure the APT backend in your `config.yml`:

```yaml
backends:
  - type: apt
    config:
      prefix: /ubuntu/
      mirror_url: http://archive.ubuntu.com/ubuntu/
      timeout: 30
  
  - type: apt
    config:
      prefix: /ubuntu-security/
      mirror_url: http://security.ubuntu.com/ubuntu/
      timeout: 30
```

or for the Debian ARM port the following `config.yml` could be used:

```yaml
backends:
  - type: apt
    name: ubuntu
    config:
       prefix: /ubuntu/
       mirror_url: http://ports.ubuntu.com/ubuntu-ports/
```

This configuration creates two APT backends:
- `/apt/ubuntu/` - Proxies the main Ubuntu repository
- `/apt/security/` - Proxies the Ubuntu security repository

## Client Configuration

### Method 1: Using APT Configuration Directory (Recommended)

Create a configuration file to tell APT to use your cache:

```bash
# Create the APT configuration directory if it doesn't exist
sudo mkdir -p /etc/apt/apt.conf.d/

# Create the proxy configuration
sudo tee /etc/apt/apt.conf.d/01-artifact-vault > /dev/null << 'EOF'
# Artifact Vault APT Proxy Configuration
Acquire::http::proxy::archive.ubuntu.com "http://localhost:8080/apt/ubuntu/";
Acquire::http::proxy::security.ubuntu.com "http://localhost:8080/apt/security/";
EOF
```

### Method 2: Modifying sources.list (Alternative)

You can also modify your sources.list to point directly to the cache (replace 'localhost' with the host
that is running your artifact-vault):

```bash
# Backup original sources.list
sudo cp /etc/apt/sources.list /etc/apt/sources.list.backup

# Create new sources.list with cache URLs
sudo tee /etc/apt/sources.list > /dev/null << 'EOF'
# Ubuntu repositories via Artifact Vault cache
deb http://localhost:8080/ubuntu/ jammy main restricted universe multiverse
deb http://localhost:8080/ubuntu/ jammy-updates main restricted universe multiverse
deb http://localhost:8080/ubuntu/ jammy-backports main restricted universe multiverse
deb http://localhost:8080/ubuntu-security/ jammy-security main restricted universe multiverse
EOF
```

Or for ARM systems:

```bash
sudo tee /etc/apt/sources.list > /dev/null << 'EOF'
# Ubuntu repositories via Artifact Vault cache
deb http://localhost:8080/ubuntu/ jammy main restricted universe multiverse
deb http://localhost:8080/ubuntu/ jammy-updates main restricted universe multiverse
deb http://localhost:8080/ubuntu/ jammy-backports main restricted universe multiverse
deb http://localhost:8080/ubuntu/ jammy-security main restricted universe multiverse
EOF
```

### Method 3: Environment Variables (Temporary)

For temporary use or testing:

```bash
export http_proxy=http://localhost:8080/apt/ubuntu/
export https_proxy=http://localhost:8080/apt/ubuntu/
sudo -E apt update
sudo -E apt install package-name
```

## Testing the Configuration

1. **Update package lists**:
   ```bash
   sudo apt update
   ```

2. **Check if cache is working**:
   Look for requests in the Artifact Vault logs. You should see entries like:
   ```
   GET /apt/ubuntu/dists/jammy/Release
   GET /apt/ubuntu/dists/jammy/main/binary-amd64/Packages.gz
   ```

3. **Install a package to test caching**:
   ```bash
   sudo apt install curl
   ```

4. **Verify caching by installing the same package again**:
   ```bash
   sudo apt remove curl
   sudo apt install curl
   ```
   The second install should be much faster as the .deb file is cached.

## URL Structure

The APT backend handles these types of requests:

- **Repository metadata**: 
  - `dists/SUITE/Release` - Release files
  - `dists/SUITE/Release.gpg` - GPG signatures
  - `dists/SUITE/COMPONENT/binary-ARCH/Packages.gz` - Package indices

- **Package files**:
  - `pool/COMPONENT/p/package/package_version_arch.deb` - Debian packages

- **Source packages**:
  - `pool/COMPONENT/p/package/package_version.dsc` - Source package descriptions
  - `pool/COMPONENT/p/package/package_version.tar.gz` - Source archives

## Multiple Repositories

You can configure multiple APT repositories:

```yaml
backends:
  # Main Ubuntu repository
  - type: apt
    config:
      prefix: /apt/ubuntu/
      mirror_url: http://archive.ubuntu.com/ubuntu/
  
  # Ubuntu security updates
  - type: apt
    config:
      prefix: /apt/security/
      mirror_url: http://security.ubuntu.com/ubuntu/
  
  # Third-party repository (e.g., Docker)
  - type: apt
    config:
      prefix: /apt/docker/
      mirror_url: https://download.docker.com/linux/ubuntu/
      username: your_username  # if authentication required
      password: your_password
```

Then configure APT to use all repositories:

```bash
sudo tee /etc/apt/apt.conf.d/01-artifact-vault > /dev/null << 'EOF'
Acquire::http::proxy::archive.ubuntu.com "http://localhost:8080/apt/ubuntu/";
Acquire::http::proxy::security.ubuntu.com "http://localhost:8080/apt/security/";
Acquire::http::proxy::download.docker.com "http://localhost:8080/apt/docker/";
EOF
```

## Private Repository Authentication

For private APT repositories that require authentication:

```yaml
backends:
  - type: apt
    config:
      prefix: /apt/private/
      mirror_url: https://private-repo.example.com/ubuntu/
      username: your_username
      password: your_password
      timeout: 30
```

## Docker Container Configuration

If you're using APT inside Docker containers, you can configure the proxy:

```dockerfile
# In your Dockerfile
ENV http_proxy=http://host.docker.internal:8080/apt/ubuntu/
ENV https_proxy=http://host.docker.internal:8080/apt/ubuntu/

# Or configure APT directly
RUN echo 'Acquire::http::proxy::archive.ubuntu.com "http://host.docker.internal:8080/apt/ubuntu/";' > /etc/apt/apt.conf.d/01-proxy
```

## Monitoring and Troubleshooting

### Check Cache Status

Monitor the Artifact Vault logs to see APT requests:

```bash
# If running with systemd
journalctl -u artifact-vault -f

# If running manually
tail -f /var/log/artifact-vault.log
```

### Common Issues

1. **GPG signature verification failures**:
   - Ensure GPG keys are properly installed: `sudo apt-key update`
   - The cache passes through GPG signatures unchanged

2. **Connection refused**:
   - Verify Artifact Vault is running: `curl http://localhost:8080/health`
   - Check firewall settings

3. **Slow initial downloads**:
   - First download of packages will be slower as they're cached
   - Subsequent downloads will be much faster

### APT Proxy Removal

To remove the proxy configuration:

```bash
# Remove proxy configuration
sudo rm /etc/apt/apt.conf.d/01-artifact-vault

# Or restore original sources.list
sudo cp /etc/apt/sources.list.backup /etc/apt/sources.list

# Update package lists
sudo apt update
```

## Performance Tuning

### Cache Location

Configure cache storage location in your main config:

```yaml
cache:
  type: filesystem
  config:
    cache_dir: /var/cache/artifact-vault
    max_size_gb: 100  # Allocate sufficient space for .deb files
```

### APT Client Optimization

Configure APT for better performance with the cache:

```bash
sudo tee -a /etc/apt/apt.conf.d/01-artifact-vault << 'EOF'
# Performance optimizations for cached repositories
Acquire::Queue-Mode "host";
Acquire::Max-Default-Age "86400";
Acquire::Languages "none";
EOF
```

## Security Considerations

- **GPG verification**: The cache passes through GPG signatures for package verification
- **HTTPS support**: Configure backends with HTTPS mirror URLs when available
- **Network policies**: Ensure your firewall allows access to the cache server
- **Authentication**: Use authentication for private repositories

This configuration provides efficient APT package caching while maintaining all security features of the APT package management system.
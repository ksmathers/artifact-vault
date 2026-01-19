# Documentation Index

This directory contains comprehensive documentation for Artifact Vault. Start with the main [README.md](../README.md) for an overview, then dive into specific topics below.

## 📚 Documentation Structure

### Getting Started
- **[Main README](../README.md)** - Project overview, quick start, and links to detailed docs
- **[Configuration Guide](configuration.md)** - Complete configuration reference with examples

### User Guides
- **[Docker Integration](docker-integration.md)** - Set up Docker to use Artifact Vault as a registry mirror
- **[Python pip Integration](python-pip-integration.md)** - Configure pip to use Artifact Vault as a PyPI mirror
- **[APT Integration](apt-integration.md)** - Configure APT to use Artifact Vault for Debian package caching
- **[Hugging Face Integration](huggingface-integration.md)** - Use Artifact Vault for caching Hugging Face models and datasets
- **[Troubleshooting](troubleshooting.md)** - Common issues, debugging, and production monitoring

### Developer Resources
- **[Development Guide](development.md)** - Architecture, adding backends, and contributing
- **[API Reference](api.md)** - HTTP API and backend interface documentation

## 🚀 Quick Navigation

### I want to...

**Get started quickly**
→ [Main README](../README.md) → [Configuration Guide](configuration.md)

**Set up Docker caching**
→ [Docker Integration Guide](docker-integration.md)

**Set up Python pip caching**
→ [Python pip Integration Guide](python-pip-integration.md)

**Set up Hugging Face model caching**
→ [Hugging Face Integration Guide](huggingface-integration.md)

**Set up APT package caching**
→ [APT Integration Guide](apt-integration.md)

**Add a new backend**
→ [Development Guide](development.md#adding-new-backends)

**Troubleshoot issues**
→ [Troubleshooting Guide](troubleshooting.md#common-issues)

**Understand the API**
→ [API Reference](api.md)

**Deploy to production**
→ [Configuration Guide](configuration.md#production-configuration) → [Troubleshooting Guide](troubleshooting.md#production-monitoring)

## 📋 Document Summaries

### [Configuration Guide](configuration.md)
Complete reference for all configuration options including:
- Global settings (host, port, cache directory)
- Backend configurations (HTTP, PyPI, DockerHub)
- Production examples and security best practices
- Environment variable usage

### [Docker Integration](docker-integration.md)
Comprehensive guide for using Artifact Vault as a Docker registry mirror:
- Docker daemon configuration methods
- Verification and testing procedures
- Performance benefits and troubleshooting
- Production deployment considerations

### [Python pip Integration](python-pip-integration.md)
Complete guide for using Artifact Vault as a PyPI package cache:
- pip configuration methods (config file, environment variables, command line)
- Integration with Poetry, pipenv, and conda
- CI/CD pipeline configuration
- Performance benefits and troubleshooting

### [APT Integration](apt-integration.md)
Complete guide for using Artifact Vault as an APT package cache:
- APT configuration for Debian/Ubuntu systems
- Integration with system package management
- Performance benefits and troubleshooting
- Production deployment considerations

### [Hugging Face Integration](huggingface-integration.md)
Comprehensive guide for using Artifact Vault to cache Hugging Face models and datasets:
- Configuration with huggingface-hub library
- Handling 301/302 redirects to CDN
- Integration with transformers and other ML frameworks
- Private model support with authentication tokens
- Performance optimization for large models

### [Development Guide](development.md)
Technical documentation for developers:
- Architecture overview and request flow
- Backend interface specification
- Step-by-step guide for adding new backends
- Code style standards and testing approaches

### [API Reference](api.md)
Detailed API documentation:
- HTTP API endpoints and response formats
- Backend interface requirements
- Implementation examples and patterns
- Error handling and testing strategies

### [Troubleshooting Guide](troubleshooting.md)
Operations and debugging guide:
- Common issues and solutions
- Performance optimization techniques
- Production monitoring and alerting
- Security considerations and backup strategies

## 🔧 Configuration Quick Reference

```yaml
# Basic configuration template
http_host: localhost
http_port: 8080
cache_dir: /tmp/artifact_cache
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

## 🆘 Common Issues Quick Links

| Issue | Solution |
|-------|----------|
| Docker not using mirror | [Docker Integration → Troubleshooting](docker-integration.md#troubleshooting-docker-integration) |
| pip not using mirror | [Python pip Integration → Troubleshooting](python-pip-integration.md#troubleshooting) |
| Cache permission errors | [Troubleshooting → Cache Permission Errors](troubleshooting.md#2-cache-permission-errors) |
| Backend timeouts | [Troubleshooting → Large File Timeouts](troubleshooting.md#3-large-file-timeouts) |
| High memory usage | [Troubleshooting → Memory Usage Issues](troubleshooting.md#4-memory-usage-issues) |
| Configuration errors | [Configuration → Common Issues](configuration.md#common-configuration-issues) |

## 📈 Performance Quick Tips

- Use `http_host: 0.0.0.0` for external access
- Set persistent cache directory: `/var/cache/artifact_vault`
- Monitor cache hit rates in logs
- Use appropriate chunk sizes for your network
- Enable connection pooling for custom backends

## 🔒 Security Checklist

- [ ] Use HTTPS in production (reverse proxy)
- [ ] Set restrictive cache directory permissions
- [ ] Use environment variables for credentials
- [ ] Configure firewall rules appropriately
- [ ] Enable access logging for audit trails
- [ ] Regular backup of cache and configuration

## 🤝 Contributing

See the [Development Guide](development.md) for:
- Development environment setup
- Code style standards
- Testing procedures
- Pull request process

## 📞 Support

1. Check the [Troubleshooting Guide](troubleshooting.md) first
2. Search existing issues in the project repository
3. Create a new issue with detailed information
4. Include configuration, logs, and steps to reproduce

---

*Last updated: $(date)*
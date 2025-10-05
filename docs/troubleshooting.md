# Troubleshooting Guide

This guide covers common issues, performance optimization, debugging techniques, and production considerations for Artifact Vault.

## Common Issues

### 1. Backend Not Responding

**Symptoms:**
- 502 Bad Gateway errors
- Timeouts on requests
- "Backend not responding" messages

**Diagnosis:**
```bash
# Test backend connectivity directly
curl -v http://localhost:8080/apache/test-file
curl -v https://archive.apache.org/test-file  # Test upstream directly

# Check network connectivity
ping archive.apache.org
nslookup archive.apache.org
```

**Solutions:**
- Verify backend URLs in configuration
- Check network connectivity and DNS resolution
- Verify firewall rules allow outbound connections
- Check if upstream service is available
- Increase timeout values in backend configuration

### 2. Cache Permission Errors

**Symptoms:**
- "Permission denied" errors in logs
- Cache directory not created
- Files not being cached

**Diagnosis:**
```bash
# Check cache directory permissions
ls -la /tmp/artifact_cache
ls -la /var/cache/artifact_vault

# Check user running the service
whoami
ps aux | grep artifact-vault
```

**Solutions:**
```bash
# Fix cache directory permissions
sudo mkdir -p /var/cache/artifact_vault
sudo chown -R $(whoami) /var/cache/artifact_vault
sudo chmod 755 /var/cache/artifact_vault

# For systemd service
sudo chown -R artifact-vault:artifact-vault /var/cache/artifact_vault
```

### 3. Large File Timeouts

**Symptoms:**
- Downloads fail for large files (>100MB)
- Timeout errors after 30 seconds
- Partial file downloads

**Diagnosis:**
```bash
# Test with a large file
time curl http://localhost:8080/apache/hadoop/common/hadoop-3.3.6/hadoop-3.3.6.tar.gz

# Check timeout settings
grep -i timeout config.yml
```

**Solutions:**
```python
# Increase timeout in backend implementation
response = requests.get(url, stream=True, timeout=300)  # 5 minutes
```

```yaml
# Add timeout configuration option
backends:
  - type: http
    config:
      prefix: /apache/
      base_url: https://archive.apache.org
      timeout: 300  # 5 minutes
```

### 4. Memory Usage Issues

**Symptoms:**
- High memory usage during downloads
- Out of memory errors
- System slowdown during large transfers

**Diagnosis:**
```bash
# Monitor memory usage
top -p $(pgrep -f "python main.py")
htop

# Check for memory leaks
ps aux | grep python | awk '{print $6}' | head -1  # RSS memory
```

**Solutions:**
- Verify streaming is working correctly (8KB chunks)
- Check for memory leaks in custom backends
- Monitor concurrent request limits
- Consider reducing chunk size for memory-constrained systems

### 5. Docker Integration Issues

**Symptoms:**
- Docker not using the mirror
- "connection refused" errors from Docker
- Slow Docker pulls despite cache

**See [Docker Integration Guide](docker-integration.md#troubleshooting-docker-integration) for detailed troubleshooting.**

## Performance Optimization

### Streaming Performance

**Current Implementation:**
```python
# Default 8KB chunks
chunk_size = 8192
for chunk in response.iter_content(chunk_size=chunk_size):
    yield {"content": chunk, ...}
```

**Optimization Options:**
```python
# Larger chunks for faster networks (16KB-64KB)
chunk_size = 16384  # 16KB
chunk_size = 65536  # 64KB

# Smaller chunks for memory-constrained systems
chunk_size = 4096   # 4KB
```

### Concurrent Request Handling

**Monitor Concurrent Requests:**
```bash
# Check active connections
netstat -an | grep :8080 | grep ESTABLISHED | wc -l

# Monitor with ss
ss -tuln | grep :8080
```

**HTTP Server Tuning:**
```python
# In main.py, consider using ThreadingHTTPServer for better concurrency
from http.server import ThreadingHTTPServer

# Replace HTTPServer with ThreadingHTTPServer
httpd = ThreadingHTTPServer(server_address, ArtifactRequestHandler)
```

### Cache Performance

**Cache Hit Rate Monitoring:**
```bash
# Add logging to track cache hits/misses
grep "cache hit" /var/log/artifact-vault.log | wc -l
grep "cache miss" /var/log/artifact-vault.log | wc -l
```

**Cache Optimization:**
```bash
# Pre-populate cache with frequently used artifacts
./prepare-cache.sh

# Monitor cache size and usage
du -sh /var/cache/artifact_vault
find /var/cache/artifact_vault -type f -atime -7 | wc -l  # Files accessed in last 7 days
```

### Network Optimization

**Connection Reuse:**
```python
# Use sessions for connection pooling
import requests

class OptimizedBackend:
    def __init__(self, config, cache):
        self.session = requests.Session()
        # Configure connection pooling
        adapter = requests.adapters.HTTPAdapter(
            pool_connections=10,
            pool_maxsize=20,
            max_retries=3
        )
        self.session.mount('http://', adapter)
        self.session.mount('https://', adapter)
```

**DNS Caching:**
```bash
# Install and configure DNS caching
sudo apt-get install dnsmasq
# Configure /etc/dnsmasq.conf for caching
```

## Debugging Techniques

### Enable Debug Logging

**Comprehensive Debug Mode:**
```bash
python main.py --config config.yml --log-level DEBUG
```

**Custom Debug Configuration:**
```python
# Add to main.py for more detailed logging
import logging
logging.basicConfig(
    level=logging.DEBUG,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('/var/log/artifact-vault.log'),
        logging.StreamHandler()
    ]
)
```

### HTTP Request Debugging

**Enable requests library debugging:**
```python
import logging
import http.client as http_client

http_client.HTTPConnection.debuglevel = 1
logging.getLogger("requests.packages.urllib3").setLevel(logging.DEBUG)
logging.getLogger("requests.packages.urllib3").propagate = True
```

**Traffic Analysis:**
```bash
# Monitor HTTP traffic
sudo tcpdump -i any port 8080 -A

# Monitor outbound traffic
sudo tcpdump -i any host archive.apache.org -A

# Use wireshark for detailed analysis
sudo wireshark
```

### Cache Debugging

**Cache Operation Logging:**
```python
# Add to cache.py
import logging

def get(self, path):
    logging.debug(f"Cache get: {path}")
    with open(path, 'rb') as f:
        content = f.read()
    logging.debug(f"Cache hit: {len(content)} bytes")
    return content

def set(self, prefix, name, content):
    path = os.path.join(self.cache_dir, prefix.strip('/'), name)
    logging.debug(f"Cache set: {path} ({len(content)} bytes)")
    # ... existing implementation
```

**Cache Analysis:**
```bash
# Analyze cache usage patterns
find /var/cache/artifact_vault -type f -printf "%T@ %s %p\n" | sort -n | tail -20

# Find largest cached files
find /var/cache/artifact_vault -type f -exec ls -lh {} + | sort -k 5 -hr | head -10

# Cache age analysis
find /var/cache/artifact_vault -type f -mtime +30  # Files older than 30 days
```

### Performance Profiling

**Python Profiling:**
```python
import cProfile
import pstats

# Profile the fetch method
profiler = cProfile.Profile()
profiler.enable()
# ... run fetch operation
profiler.disable()

stats = pstats.Stats(profiler)
stats.sort_stats('cumulative')
stats.print_stats(10)
```

**Memory Profiling:**
```bash
# Install memory profiler
pip install memory-profiler psutil

# Profile memory usage
python -m memory_profiler main.py --config config.yml
```

## Production Monitoring

### System Metrics

**Essential Metrics to Monitor:**
```bash
# Disk space (cache directory)
df -h /var/cache/artifact_vault

# Memory usage
free -h
ps aux | grep artifact-vault | awk '{print $6}'

# CPU usage
top -p $(pgrep -f "python main.py")

# Network I/O
iftop -i eth0

# File descriptor usage
lsof -p $(pgrep -f "python main.py") | wc -l
```

**Automated Monitoring Script:**
```bash
#!/bin/bash
# monitor-artifact-vault.sh

LOG_FILE="/var/log/artifact-vault-monitoring.log"
PID=$(pgrep -f "python main.py")

if [ -z "$PID" ]; then
    echo "$(date): Artifact Vault not running!" >> $LOG_FILE
    exit 1
fi

# Disk space
CACHE_USAGE=$(df /var/cache/artifact_vault | tail -1 | awk '{print $5}' | sed 's/%//')
if [ "$CACHE_USAGE" -gt 90 ]; then
    echo "$(date): Cache disk usage high: $CACHE_USAGE%" >> $LOG_FILE
fi

# Memory usage
MEM_USAGE=$(ps -p $PID -o %mem --no-headers | sed 's/ //')
echo "$(date): Memory usage: $MEM_USAGE%" >> $LOG_FILE

# Request count (from logs)
REQUESTS_LAST_HOUR=$(grep "$(date -d '1 hour ago' '+%Y-%m-%d %H')" /var/log/artifact-vault.log | wc -l)
echo "$(date): Requests last hour: $REQUESTS_LAST_HOUR" >> $LOG_FILE
```

### Application Metrics

**Add Metrics to Application:**
```python
# Add to main.py
import time
from collections import defaultdict

class MetricsCollector:
    def __init__(self):
        self.request_count = defaultdict(int)
        self.cache_hits = 0
        self.cache_misses = 0
        self.total_bytes_served = 0
        self.start_time = time.time()
    
    def record_request(self, backend_type):
        self.request_count[backend_type] += 1
    
    def record_cache_hit(self):
        self.cache_hits += 1
    
    def record_cache_miss(self):
        self.cache_misses += 1
    
    def record_bytes_served(self, bytes_count):
        self.total_bytes_served += bytes_count
    
    def get_stats(self):
        uptime = time.time() - self.start_time
        return {
            'uptime': uptime,
            'requests': dict(self.request_count),
            'cache_hit_rate': self.cache_hits / (self.cache_hits + self.cache_misses) if (self.cache_hits + self.cache_misses) > 0 else 0,
            'total_bytes_served': self.total_bytes_served
        }

# Global metrics instance
metrics = MetricsCollector()
```

**Metrics Endpoint:**
```python
# Add metrics endpoint to request handler
def do_GET(self):
    if self.path == '/metrics':
        self.send_response(200)
        self.send_header('Content-Type', 'application/json')
        self.end_headers()
        import json
        self.wfile.write(json.dumps(metrics.get_stats()).encode())
        return
    
    # ... existing request handling
```

### Log Analysis

**Useful Log Patterns:**
```bash
# Error analysis
grep ERROR /var/log/artifact-vault.log | tail -20

# Cache hit rate
grep -c "cache hit" /var/log/artifact-vault.log
grep -c "cache miss" /var/log/artifact-vault.log

# Request patterns
grep "GET /" /var/log/artifact-vault.log | awk '{print $7}' | sort | uniq -c | sort -nr

# Performance analysis
grep "Transfer.*complete" /var/log/artifact-vault.log | tail -10
```

**Log Aggregation with ELK Stack:**
```yaml
# logstash configuration for artifact-vault logs
input {
  file {
    path => "/var/log/artifact-vault.log"
    start_position => "beginning"
  }
}

filter {
  grok {
    match => { "message" => "%{TIMESTAMP_ISO8601:timestamp} - %{WORD:logger} - %{LOGLEVEL:level} - %{GREEDYDATA:message}" }
  }
}

output {
  elasticsearch {
    hosts => ["localhost:9200"]
    index => "artifact-vault-%{+YYYY.MM.dd}"
  }
}
```

## Security Considerations

### Network Security

**Firewall Configuration:**
```bash
# Allow inbound traffic on artifact vault port
sudo ufw allow 8080/tcp

# Restrict to specific networks
sudo ufw allow from 192.168.1.0/24 to any port 8080

# Block unnecessary outbound traffic
sudo ufw deny out 80,443  # Only allow specific backends
sudo ufw allow out to archive.apache.org port 443
```

**TLS/SSL Configuration:**
```bash
# Use reverse proxy for TLS termination
# nginx configuration
server {
    listen 443 ssl;
    server_name artifact-vault.company.com;
    
    ssl_certificate /path/to/cert.pem;
    ssl_certificate_key /path/to/key.pem;
    
    location / {
        proxy_pass http://localhost:8080;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
    }
}
```

### Access Control

**Basic Authentication (nginx):**
```bash
# Create password file
sudo htpasswd -c /etc/nginx/.htpasswd username

# nginx configuration
location / {
    auth_basic "Artifact Vault";
    auth_basic_user_file /etc/nginx/.htpasswd;
    proxy_pass http://localhost:8080;
}
```

**IP-based Restrictions:**
```bash
# nginx allow specific IPs
location / {
    allow 192.168.1.0/24;
    allow 10.0.0.0/8;
    deny all;
    proxy_pass http://localhost:8080;
}
```

### File System Security

**Cache Directory Security:**
```bash
# Set restrictive permissions
sudo chmod 750 /var/cache/artifact_vault
sudo chown artifact-vault:artifact-vault /var/cache/artifact_vault

# Prevent execution of cached files
sudo mount -o noexec /var/cache/artifact_vault
```

**Configuration Security:**
```bash
# Protect configuration files
sudo chmod 600 config.yml
sudo chown artifact-vault:artifact-vault config.yml

# Use environment variables for secrets
export DOCKER_PASSWORD="secret"
# Reference in config: password: ${DOCKER_PASSWORD}
```

## Backup and Recovery

### Cache Backup Strategy

**Backup Script:**
```bash
#!/bin/bash
# backup-cache.sh

CACHE_DIR="/var/cache/artifact_vault"
BACKUP_DIR="/backup/artifact-vault"
DATE=$(date +%Y%m%d)

# Create incremental backup
rsync -av --link-dest="$BACKUP_DIR/latest" \
      "$CACHE_DIR/" "$BACKUP_DIR/$DATE/"

# Update latest symlink
ln -nfs "$BACKUP_DIR/$DATE" "$BACKUP_DIR/latest"

# Clean old backups (keep 7 days)
find "$BACKUP_DIR" -maxdepth 1 -type d -mtime +7 -exec rm -rf {} \;
```

**Selective Backup:**
```bash
# Backup only frequently accessed files
find /var/cache/artifact_vault -type f -atime -7 -exec cp --parents {} /backup/hot-cache/ \;

# Backup by size (large files first)
find /var/cache/artifact_vault -type f -size +100M -exec cp --parents {} /backup/large-cache/ \;
```

### Configuration Backup

```bash
# Backup configuration and scripts
tar -czf artifact-vault-config-$(date +%Y%m%d).tar.gz \
    config.yml \
    config-sample.yml \
    main.py \
    artifact_vault/ \
    docs/
```

### Disaster Recovery

**Recovery Steps:**
1. Restore application files
2. Restore configuration
3. Restore cache (optional - will rebuild automatically)
4. Restart service
5. Verify functionality

```bash
# Recovery script
#!/bin/bash
# Restore application
tar -xzf artifact-vault-backup.tar.gz -C /opt/

# Restore cache (optional)
rsync -av /backup/artifact-vault/latest/ /var/cache/artifact_vault/

# Set permissions
sudo chown -R artifact-vault:artifact-vault /opt/artifact-vault
sudo chown -R artifact-vault:artifact-vault /var/cache/artifact_vault

# Restart service
sudo systemctl start artifact-vault
sudo systemctl status artifact-vault
```

This troubleshooting guide provides comprehensive coverage of common issues, debugging techniques, and production best practices for maintaining a robust Artifact Vault deployment.
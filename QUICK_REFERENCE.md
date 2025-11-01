# Quick Reference: DockerHub Multi-Registry Backend

## Class Structure

### DockerRepository
Single registry operations (lines 9-181)
```python
DockerRepository(
    registry_url='https://registry-1.docker.io',
    auth_url='https://auth.docker.io',
    username='optional',
    password='optional'
)
```

**Methods:**
- `fetch_artifact(repository, resource_type, identifier)` - Download artifacts

### DockerHubBackend  
Multi-registry manager (lines 181-385)
```python
DockerHubBackend(config, cache)
```

**Methods:**
- `can_handle(path)` - Check if path matches prefix
- `fetch(path)` - Download with multi-registry fallback
- `get_manifest(repository, tag)` - Convenience for manifests
- `get_blob(repository, digest)` - Convenience for blobs

## Configuration Examples

### Single Registry (Backward Compatible)
```yaml
backends:
  - type: dockerhub
    config:
      prefix: /dockerhub/
      registry_url: https://registry-1.docker.io
      auth_url: https://auth.docker.io
```

### Multiple Registries
```yaml
backends:
  - type: dockerhub
    config:
      prefix: /dockerhub/
      repositories:
        - registry_url: https://private.company.com
          username: user
          password: pass
        - registry_url: https://registry-1.docker.io
```

## How It Works

```
Request: /dockerhub/library/ubuntu/manifests/latest
    ↓
[1] Check cache
    ↓ (miss)
[2] Parse path → (library/ubuntu, manifests, latest)
    ↓
[3] Try Repository #1 (private)
    ↓ (404 - not found)
[4] Try Repository #2 (mirror)
    ↓ (404 - not found)
[5] Try Repository #3 (Docker Hub)
    ↓ (200 - success!)
[6] Cache artifact
    ↓
[7] Return to client
```

## Priority Resolution

**Order matters!** First successful fetch wins:

```yaml
repositories:
  - # Priority 1 (checked first)
  - # Priority 2 (checked if #1 fails)
  - # Priority 3 (checked if #1 and #2 fail)
```

**Name conflict example:**
- Private registry has `library/ubuntu:custom`
- Docker Hub has `library/ubuntu:latest`
- Request for `library/ubuntu` → Private registry version used first

## Key Features

✅ **Multiple registries** - Configure any number of Docker registries  
✅ **Priority-based** - Registries tried in order  
✅ **Automatic fallback** - If one fails, try the next  
✅ **Name conflict resolution** - First registry wins  
✅ **Backward compatible** - Old configs still work  
✅ **Per-registry auth** - Each registry can have own credentials  
✅ **Token caching** - Reduce authentication overhead  
✅ **Error handling** - Graceful fallback on failures  

## Testing

```bash
# Run test script
python test_docker_refactoring.py

# Check for errors
python -m py_compile artifact_vault/backend_dockerhub.py
```

## Files Modified/Created

**Modified:**
- `artifact_vault/backend_dockerhub.py` (384 lines)

**Created:**
- `docs/docker-multi-registry.md` (comprehensive docs)
- `config-multi-docker.yml` (example config)
- `test_docker_refactoring.py` (test script)
- `REFACTORING_SUMMARY.md` (detailed summary)

## Common Patterns

### Private Registry Override
```yaml
repositories:
  - registry_url: https://private.company.com  # Check first
    username: user
    password: pass
  - registry_url: https://registry-1.docker.io  # Fallback
```

### Geographic Optimization
```yaml
repositories:
  - registry_url: https://local-mirror.company.com  # Fast, local
  - registry_url: https://registry-1.docker.io       # Slower, remote
```

### Multi-Tenant
```yaml
repositories:
  - registry_url: https://tenant-a-registry.com
  - registry_url: https://tenant-b-registry.com
  - registry_url: https://shared-registry.com
```

## API Compatibility

All existing API methods preserved:
- `can_handle(path)` ✅
- `fetch(path)` ✅  
- `get_manifest(repository, tag)` ✅
- `get_blob(repository, digest)` ✅

New internal structure (transparent to callers):
- Multiple `DockerRepository` instances
- Priority-based iteration
- Enhanced error handling

## Performance

**Cache Hit:** Instant (no registry lookup)  
**Cache Miss:**  
- Single registry: ~1-5 seconds
- Multiple registries: ~1-5 seconds per registry attempt
- Recommendation: Put reliable registries first

**Token Caching:** Reduces auth overhead from ~1s to ~0ms per request

## Security

🔐 Store credentials securely (environment variables)  
🔐 Use HTTPS for all registry URLs  
🔐 Each registry can have different credentials  
🔐 Anonymous access supported (no username/password)  

## Troubleshooting

**Problem:** Artifact not found  
**Solution:** Check that registries are ordered correctly

**Problem:** Slow fetching  
**Solution:** Reorder registries (fastest/most reliable first)

**Problem:** Authentication failing  
**Solution:** Verify credentials for each registry

**Problem:** Old config not working  
**Solution:** Old configs should work! Check logs for errors

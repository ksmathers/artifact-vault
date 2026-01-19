# Hugging Face Backend - Implementation Summary

## Overview

A new backend has been added to Artifact Vault to support transparent caching of Hugging Face models and datasets. This backend handles the specific requirements of the Hugging Face ecosystem, including redirect handling to CDN servers.

## Files Added

### 1. Backend Implementation
**File:** `artifact_vault/backend_huggingface.py` (320 lines)

Core features:
- Handles model and dataset downloads from huggingface.co
- Automatic redirect following (301/302) to CDN servers
- Manual redirect handling to track and log redirect chains
- Removes authentication headers when redirecting to CDN
- Streaming downloads with progress tracking
- Configurable timeouts and redirect limits
- Support for private repositories with bearer token authentication

Key methods:
- `can_handle(path)` - Path matching for `/huggingface/` prefix
- `fetch(path)` - Main fetch method with cache checking
- `_parse_path(artifact_path)` - Parses model/dataset paths
- `_fetch_with_redirect(url, artifact_path)` - Handles redirect chain
- `get_model_file(org, model, revision, filename)` - Convenience method
- `get_dataset_file(org, dataset, revision, filename)` - Convenience method

### 2. Documentation
**File:** `docs/huggingface-integration.md` (450+ lines)

Comprehensive guide including:
- Configuration examples
- URL path format reference
- Integration with huggingface-hub and transformers libraries
- Redirect handling explanation
- Complete usage examples
- Troubleshooting guide
- Security considerations
- Docker and Kubernetes deployment examples

### 3. Test Script
**File:** `test_huggingface.py` (200+ lines)

Automated testing script featuring:
- Cache hit/miss verification
- Redirect handling tests
- Error handling tests
- Performance comparison (first vs. cached requests)
- Command-line interface

### 4. Example Code
**File:** `examples/huggingface_example.py` (200+ lines)

Practical examples demonstrating:
- Simple file downloads with huggingface-hub
- Integration with transformers library
- Direct HTTP requests
- Dataset downloads
- Environment variable configuration

### 5. Configuration Examples
**File:** `config-huggingface.yml`

Complete configuration file with:
- Hugging Face backend enabled
- Other backends (PyPI, DockerHub, HTTP) for comparison
- Commented authentication options
- Sensible defaults

## Files Modified

### 1. Main Application
**File:** `main.py`

Added backend registration:
```python
elif backend['type'] == 'huggingface':
    from artifact_vault.backend_huggingface import HuggingFaceBackend
    backends.append(HuggingFaceBackend(backend.get('config', {}), cache))
```

### 2. Sample Configuration
**File:** `config-sample.yml`

Added example Hugging Face backend configuration with comments.

### 3. README Updates
**File:** `README.md`

- Added Hugging Face to supported backends list
- Added link to huggingface-integration.md documentation

### 4. Documentation Index
**File:** `docs/README.md`

- Added Hugging Face integration to user guides
- Added quick navigation entry
- Added document summary

## Configuration

### Basic Configuration
```yaml
backends:
  - type: huggingface
    config:
      prefix: /huggingface/
      base_url: https://huggingface.co
```

### Advanced Configuration
```yaml
backends:
  - type: huggingface
    name: huggingface-private
    config:
      prefix: /huggingface/
      base_url: https://huggingface.co
      token: hf_xxxxxxxxxxxxxxxxxxxxxxxxxxxxx
      timeout: 120
      max_redirects: 5
```

## URL Patterns

### Models
```
/huggingface/{org}/{model}/resolve/{revision}/{filename}
```

Example:
```
http://localhost:8080/huggingface/meta-llama/Llama-2-7b-hf/resolve/main/config.json
```

### Datasets
```
/huggingface/datasets/{org}/{dataset}/resolve/{revision}/{filename}
```

Example:
```
http://localhost:8080/huggingface/datasets/squad/squad/resolve/main/train.json
```

## How It Works

### Request Flow

1. **Client Request** → Artifact Vault receives request for Hugging Face file
2. **Cache Check** → Checks if file already cached locally
3. **Cache Hit** → Serves directly from cache (instant)
4. **Cache Miss** → Proceeds to fetch from Hugging Face:
   - Makes initial request to huggingface.co
   - Receives 301/302 redirect to CDN
   - Follows redirect to cdn-lfs.huggingface.co or cdn.huggingface.co
   - Removes auth header when redirecting to CDN (security)
   - Streams content while caching
   - Returns content to client
5. **Subsequent Requests** → Served from cache

### Redirect Handling

The backend manually handles redirects to:
- Log the complete redirect chain
- Remove authentication tokens before sending to CDN
- Track redirect count to prevent loops
- Support both relative and absolute redirect URLs

Example redirect chain:
```
https://huggingface.co/bert-base-uncased/resolve/main/pytorch_model.bin
  ↓ 302 Found
https://cdn-lfs.huggingface.co/repos/96/48/.../pytorch_model.bin?response-content-disposition=...
  ↓ 200 OK
[Binary content]
```

## Integration with huggingface-hub

### Environment Variable Method
```python
import os
os.environ['HF_ENDPOINT'] = 'http://localhost:8080/huggingface'

from huggingface_hub import hf_hub_download
path = hf_hub_download(repo_id="bert-base-uncased", filename="config.json")
```

### Direct URL Method
```python
import requests
url = "http://localhost:8080/huggingface/bert-base-uncased/resolve/main/config.json"
response = requests.get(url)
```

## Testing

### Run Automated Tests
```bash
# Start Artifact Vault
python main.py --config config-huggingface.yml

# In another terminal, run tests
python test_huggingface.py
```

### Run Examples
```bash
# Requires: pip install huggingface-hub transformers
python examples/huggingface_example.py
```

### Manual Testing
```bash
# Test basic download
curl http://localhost:8080/huggingface/bert-base-uncased/resolve/main/config.json

# Test caching (should be instant on second request)
curl http://localhost:8080/huggingface/bert-base-uncased/resolve/main/config.json
```

## Key Features

### 1. Redirect Following
- Handles 301, 302, 303, 307, 308 status codes
- Configurable max redirects (default: 5)
- Logs each step in redirect chain

### 2. Security
- Strips authentication headers when redirecting to CDN
- Support for Bearer token authentication
- Private repository access

### 3. Performance
- 32KB chunks for large model files
- Streaming downloads
- Configurable timeouts (default: 60s)

### 4. Error Handling
- 404: Resource not found
- 401: Authentication required
- 403: Access forbidden
- Timeout errors
- Network errors

### 5. Caching
- Stores complete files only after successful download
- Preserves content-type metadata
- Cache key based on org/model/revision/filename path

## Limitations

1. **Read-only**: Only supports downloads, not uploads
2. **No Git operations**: Doesn't support git clone/pull
3. **No Spaces**: Doesn't proxy Hugging Face Spaces
4. **No Inference API**: Only file downloads, not inference endpoints
5. **File-level caching**: Caches complete files, not partial downloads

## Production Considerations

### Storage Requirements
- Large models can be multiple GB each
- Plan cache storage accordingly
- Consider cache cleanup policies

### Network
- First download for each file requires internet access to Hugging Face
- CDN bandwidth consumption on cache misses
- Consider rate limits for free tier

### Security
- Store tokens in environment variables or secrets management
- Use HTTPS reverse proxy in production
- Restrict network access appropriately

### Monitoring
- Log redirect chains for debugging
- Monitor cache hit rates
- Track download durations
- Alert on error rates

## Future Enhancements

Potential improvements:
1. Partial/resumable downloads
2. Parallel chunk downloading
3. Cache warming utilities
4. Statistics dashboard
5. Cache eviction policies (LRU, size-based)
6. Integration with Hugging Face Datasets library
7. Support for Hugging Face Spaces artifacts

## Related Documentation

- [Hugging Face Integration Guide](docs/huggingface-integration.md) - Complete user guide
- [Configuration Guide](docs/configuration.md) - General configuration reference
- [Development Guide](docs/development.md) - Backend development guide
- [API Reference](docs/api.md) - Backend interface specification

## Dependencies

No new dependencies required. Uses existing:
- `requests` - HTTP client
- `PyYAML` - Configuration parsing
- Standard library modules

## Compatibility

- Python 3.6+
- Works with huggingface-hub 0.10.0+
- Works with transformers 4.0.0+
- Compatible with all Artifact Vault cache backends

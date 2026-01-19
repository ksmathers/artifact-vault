# Quick Reference: Hugging Face Backend

## Configuration Template

```yaml
backends:
  - type: huggingface
    config:
      prefix: /huggingface/           # URL prefix
      base_url: https://huggingface.co
      token: hf_xxxxx                  # Optional: for private repos
      timeout: 120                     # Optional: seconds (default: 60)
      max_redirects: 5                 # Optional: default: 5
```

## URL Patterns

### Models
```
/huggingface/{org}/{model}/resolve/{revision}/{filename}
```

### Datasets
```
/huggingface/datasets/{org}/{dataset}/resolve/{revision}/{filename}
```

## Quick Examples

### With huggingface-hub
```python
import os
os.environ['HF_ENDPOINT'] = 'http://localhost:8080/huggingface'

from huggingface_hub import hf_hub_download
path = hf_hub_download("bert-base-uncased", "config.json")
```

### With transformers
```python
import os
os.environ['HF_ENDPOINT'] = 'http://localhost:8080/huggingface'

from transformers import AutoConfig
config = AutoConfig.from_pretrained("bert-base-uncased")
```

### Direct HTTP
```bash
curl http://localhost:8080/huggingface/bert-base-uncased/resolve/main/config.json
```

## How Redirects Work

```
Request: /huggingface/bert-base-uncased/resolve/main/file.bin
    ↓
[1] Check cache → MISS
    ↓
[2] Request to huggingface.co
    ↓ 302 Redirect
[3] Follow to cdn-lfs.huggingface.co (auth header removed)
    ↓ 200 OK
[4] Stream + Cache
    ↓
[5] Return to client

Second Request → [1] Check cache → HIT → Instant response
```

## Common Tasks

### Test basic functionality
```bash
python test_huggingface.py
```

### Download a specific file
```python
import requests
url = "http://localhost:8080/huggingface/bert-base-uncased/resolve/main/config.json"
response = requests.get(url)
```

### Check cache contents
```bash
ls -lh /tmp/artifact_cache/huggingface/
```

### View redirect logs
```bash
python main.py --config config-huggingface.yml --log-level DEBUG
```

## Private Models

### 1. Get token from HuggingFace
```
https://huggingface.co/settings/tokens
```

### 2. Add to config
```yaml
backends:
  - type: huggingface
    config:
      token: hf_xxxxxxxxxxxxxxxxxxxxxxxxxxxxx
```

### 3. Use normally
```python
# Token automatically used for private repos
hf_hub_download("org/private-model", "config.json")
```

## Troubleshooting

| Issue | Solution |
|-------|----------|
| 401 Unauthorized | Add token to config |
| 403 Forbidden | Check token permissions |
| Too many redirects | Increase max_redirects |
| Timeout | Increase timeout setting |
| Cache not working | Check cache_dir permissions |

## Performance Tips

- Use larger timeout for big models: `timeout: 300`
- Cache directory on fast storage (SSD)
- Monitor cache hit rates in logs
- First download is slow (fetches from HF CDN)
- Subsequent downloads are instant (from cache)

## File Sizes

| Model Type | Typical Size | First Download Time |
|------------|--------------|---------------------|
| Config/Tokenizer | < 1 MB | < 5 seconds |
| Small models | 100-500 MB | 1-5 minutes |
| Large models (BERT) | 400 MB - 1 GB | 2-10 minutes |
| Very large (LLMs) | 5-50+ GB | 30+ minutes |

## Security Checklist

- [ ] Use environment variable for token (not in config file)
- [ ] Backend strips auth before CDN redirect (automatic)
- [ ] Use HTTPS reverse proxy in production
- [ ] Restrict cache directory permissions
- [ ] Monitor access logs

## Docker Deployment

```yaml
version: '3.8'
services:
  artifact-vault:
    image: artifact-vault:latest
    environment:
      - HF_TOKEN=${HF_TOKEN}
    volumes:
      - ./config.yml:/app/config.yml
      - cache:/cache
    ports:
      - "8080:8080"
volumes:
  cache:
```

## Integration Patterns

### CI/CD Pipeline
```yaml
# .github/workflows/test.yml
env:
  HF_ENDPOINT: http://artifact-vault:8080/huggingface

steps:
  - name: Download model
    run: |
      python -c "from transformers import AutoModel; AutoModel.from_pretrained('bert-base-uncased')"
```

### Development Environment
```bash
# .env
export HF_ENDPOINT=http://localhost:8080/huggingface

# .bashrc or .zshrc
export HF_ENDPOINT=http://localhost:8080/huggingface
```

### Python Application
```python
# config.py
import os

HF_ENDPOINT = os.getenv('HF_ENDPOINT', 'http://localhost:8080/huggingface')
os.environ['HF_ENDPOINT'] = HF_ENDPOINT
```

## Monitoring

### Check logs for redirect chains
```
INFO: Following redirect from https://huggingface.co/... to https://cdn-lfs.huggingface.co/...
```

### Check cache hits
```
DEBUG: Cache hit for bert-base-uncased/resolve/main/config.json
DEBUG: Cache miss for bert-base-uncased/resolve/main/pytorch_model.bin
```

### Check performance
```
INFO: Caching 437012842 bytes for bert-base-uncased/resolve/main/pytorch_model.bin
```

## API Methods (Python)

```python
# Direct backend usage (advanced)
from artifact_vault.backend_huggingface import HuggingFaceBackend
from artifact_vault.cache import Cache

cache = Cache({'cache_dir': '/tmp/cache'})
backend = HuggingFaceBackend({
    'prefix': '/huggingface/',
    'token': 'hf_xxxxx'
}, cache)

# Download model file
for chunk in backend.get_model_file('bert-base-uncased', 'bert-base-uncased', 'main', 'config.json'):
    if 'error' in chunk:
        print(f"Error: {chunk['error']}")
    else:
        print(f"Downloaded: {chunk['bytes_downloaded']} bytes")

# Download dataset file
for chunk in backend.get_dataset_file('squad', 'squad', 'main', 'README.md'):
    # Process chunk
    pass
```

## Related Files

- Implementation: `artifact_vault/backend_huggingface.py`
- Documentation: `docs/huggingface-integration.md`
- Test: `test_huggingface.py`
- Example: `examples/huggingface_example.py`
- Config: `config-huggingface.yml`

# Hugging Face Integration Guide

This guide explains how to use Artifact Vault as a transparent caching proxy for Hugging Face model and dataset downloads.

## Overview

The Hugging Face backend provides transparent caching for:
- Model files (weights, configs, tokenizers, etc.)
- Dataset files
- Any content downloaded through huggingface.co

The backend automatically handles 301/302 redirects to Hugging Face's CDN and caches the final content, making subsequent downloads instant.

## Configuration

Add the Hugging Face backend to your `config.yml`:

```yaml
backends:
  - type: huggingface
    config:
      prefix: /huggingface/
      base_url: https://huggingface.co
      # Optional: For private models/datasets
      token: hf_xxxxxxxxxxxxxxxxxxxxxxxxxxxxx
      # Optional: Timeout in seconds (default: 60)
      timeout: 120
```

### Configuration Options

- **prefix**: URL prefix for the backend (default: `/huggingface/`)
- **base_url**: Hugging Face base URL (default: `https://huggingface.co`)
- **token**: (Optional) Hugging Face authentication token for private repositories
- **timeout**: (Optional) Request timeout in seconds (default: 60)
- **max_redirects**: (Optional) Maximum number of redirects to follow (default: 5)

## Getting a Hugging Face Token

For private models or to increase rate limits:

1. Go to https://huggingface.co/settings/tokens
2. Create a new token with "Read" permissions
3. Add the token to your configuration

## Using with Python

### Option 1: Configure huggingface-hub Environment Variables

Set the `HF_ENDPOINT` environment variable to point to your Artifact Vault instance:

```bash
export HF_ENDPOINT=http://localhost:8080/huggingface
```

Then use `huggingface-hub` normally:

```python
from huggingface_hub import hf_hub_download

# Download a model file - will be cached by Artifact Vault
model_path = hf_hub_download(
    repo_id="meta-llama/Llama-2-7b-hf",
    filename="pytorch_model.bin",
    revision="main"
)
```

### Option 2: Direct URL Construction

Construct URLs manually pointing to Artifact Vault:

```python
import requests

# Download through Artifact Vault
url = "http://localhost:8080/huggingface/meta-llama/Llama-2-7b-hf/resolve/main/pytorch_model.bin"
response = requests.get(url, stream=True)

with open("pytorch_model.bin", "wb") as f:
    for chunk in response.iter_content(chunk_size=8192):
        f.write(chunk)
```

### Option 3: Using transformers with Custom Cache

Configure transformers to use a custom cache directory that you manage with Artifact Vault:

```python
from transformers import AutoModel, AutoTokenizer
import os

# Set cache directory
os.environ['TRANSFORMERS_CACHE'] = '/path/to/cache'
os.environ['HF_ENDPOINT'] = 'http://localhost:8080/huggingface'

# Load model - will download through Artifact Vault
model = AutoModel.from_pretrained("bert-base-uncased")
tokenizer = AutoTokenizer.from_pretrained("bert-base-uncased")
```

## URL Path Format

The backend supports the following URL patterns:

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

### Path Components

- **org**: Organization or user name (e.g., `meta-llama`, `openai`)
- **model/dataset**: Repository name
- **resolve**: Action type (typically `resolve` for downloads, `blob` for viewing)
- **revision**: Git revision - can be:
  - Branch name (e.g., `main`)
  - Tag (e.g., `v1.0`)
  - Commit hash (e.g., `abc123...`)
- **filename**: Path to the file within the repository (can include subdirectories)

## How It Works

1. **Request**: Client requests a file through Artifact Vault
2. **Cache Check**: Artifact Vault checks if the file is already cached
3. **Cache Hit**: If cached, serves the file immediately
4. **Cache Miss**: If not cached:
   - Makes request to huggingface.co
   - Follows 301/302 redirects to CDN (cdn.huggingface.co or cdn-lfs.huggingface.co)
   - Streams the content while caching
   - Serves cached content on subsequent requests

### Redirect Handling

Hugging Face uses redirects to serve files from their CDN:

```
huggingface.co/org/model/resolve/main/file.bin
  ↓ 302 Redirect
cdn-lfs.huggingface.co/...hash.../file.bin
  ↓ 200 OK
[file content]
```

The backend automatically follows these redirects and caches the final content.

## Example: Downloading a Model

Here's a complete example of downloading a model through Artifact Vault:

```python
from huggingface_hub import hf_hub_download
import os

# Configure huggingface-hub to use Artifact Vault
os.environ['HF_ENDPOINT'] = 'http://localhost:8080/huggingface'

# Download model files
files = [
    'config.json',
    'pytorch_model.bin',
    'tokenizer.json',
    'tokenizer_config.json'
]

for filename in files:
    print(f"Downloading {filename}...")
    path = hf_hub_download(
        repo_id="bert-base-uncased",
        filename=filename,
        revision="main"
    )
    print(f"Cached at: {path}")

# First download fetches from Hugging Face and caches
# Subsequent downloads serve from cache instantly
```

## Example: Using with Transformers

```python
from transformers import AutoModel, AutoTokenizer
import os

# Point to Artifact Vault
os.environ['HF_ENDPOINT'] = 'http://localhost:8080/huggingface'

# Load model - downloads through Artifact Vault
model = AutoModel.from_pretrained("distilbert-base-uncased")
tokenizer = AutoTokenizer.from_pretrained("distilbert-base-uncased")

# Use model
inputs = tokenizer("Hello, world!", return_tensors="pt")
outputs = model(**inputs)
```

## Troubleshooting

### Authentication Issues

If you get 401 or 403 errors:

1. Verify your Hugging Face token is correct
2. Check that the token has appropriate permissions
3. Ensure the token is properly set in config.yml

```bash
# Test your token directly
curl -H "Authorization: Bearer hf_xxxxx" https://huggingface.co/api/whoami-v2
```

### Redirect Loop

If you encounter too many redirects:

1. Check the `max_redirects` configuration (default: 5)
2. Verify the base_url is correct
3. Check Artifact Vault logs for redirect chain details

### Slow Initial Downloads

First-time downloads must fetch from Hugging Face's CDN:

- Model files can be several GB (especially LLMs)
- Use larger `timeout` values for large models (e.g., 300 seconds)
- Monitor progress in Artifact Vault logs

### Cache Not Working

Verify cache configuration:

```yaml
cache_dir: /path/to/cache  # Ensure this directory is writable
```

Check cache contents:

```bash
ls -lh /path/to/cache/huggingface/
```

## Performance Considerations

### Large Models

For large language models (multi-GB files):

1. Ensure sufficient disk space in cache_dir
2. Increase timeout: `timeout: 300`
3. Use larger chunk_size for faster streaming (configured in backend)

### Multiple Workers

If running multiple Artifact Vault instances:

- Use a shared cache_dir (NFS, shared volume)
- Or use a distributed cache backend
- Consider file locking for concurrent writes

## Security

### Private Models

When using private models:

1. Store token in environment variable instead of config file
2. Use file permissions to protect config.yml
3. Consider using a secrets management system

```yaml
backends:
  - type: huggingface
    config:
      token: ${HF_TOKEN}  # Read from environment
```

### Network Security

- Artifact Vault acts as a proxy to huggingface.co
- Ensure appropriate firewall rules
- Consider running behind HTTPS reverse proxy

## Monitoring

Check Artifact Vault logs for:

```
INFO: Following redirect from https://huggingface.co/... to https://cdn-lfs.huggingface.co/...
INFO: Caching 524288000 bytes for meta-llama/Llama-2-7b-hf/resolve/main/pytorch_model.bin
DEBUG: Cache hit for meta-llama/Llama-2-7b-hf/resolve/main/config.json
```

## Integration Examples

### Docker Compose

```yaml
version: '3.8'
services:
  artifact-vault:
    image: artifact-vault:latest
    ports:
      - "8080:8080"
    volumes:
      - ./config.yml:/app/config.yml
      - ./cache:/cache
    environment:
      - HF_TOKEN=${HF_TOKEN}
  
  ml-service:
    image: my-ml-service:latest
    environment:
      - HF_ENDPOINT=http://artifact-vault:8080/huggingface
    depends_on:
      - artifact-vault
```

### Kubernetes

```yaml
apiVersion: v1
kind: ConfigMap
metadata:
  name: artifact-vault-config
data:
  config.yml: |
    backends:
      - type: huggingface
        config:
          prefix: /huggingface/
          token: ${HF_TOKEN}
---
apiVersion: apps/v1
kind: Deployment
metadata:
  name: artifact-vault
spec:
  template:
    spec:
      containers:
      - name: artifact-vault
        env:
        - name: HF_TOKEN
          valueFrom:
            secretKeyRef:
              name: huggingface-token
              key: token
```

## Limitations

1. **Write operations**: Only supports read/download operations
2. **Git operations**: Does not support git clone/push
3. **Spaces/Inference**: Does not proxy Hugging Face Spaces or Inference API
4. **Model cards**: Only caches files, not HTML model cards

## Further Reading

- [Hugging Face Hub Documentation](https://huggingface.co/docs/hub/)
- [huggingface_hub Library](https://huggingface.co/docs/huggingface_hub/)
- [Artifact Vault Configuration](configuration.md)
- [Artifact Vault API](api.md)

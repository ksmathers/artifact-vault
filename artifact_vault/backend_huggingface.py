import re
import requests
import logging
from urllib.parse import urlparse, unquote
from .cache import Cache


class HuggingFaceBackend:
    """
    Hugging Face Backend for Artifact Vault
    
    Provides transparent caching for Hugging Face model and dataset downloads.
    Works with the 'huggingface-hub' Python helper application by intercepting
    and caching CDN downloads that are reached via 301/302 redirects.
    
    Path format examples:
    - /huggingface/{org}/{model}/resolve/{revision}/{filename}
    - /huggingface/{org}/{model}/blob/{revision}/{filename}
    - /huggingface/datasets/{org}/{dataset}/resolve/{revision}/{filename}
    
    The backend handles:
    - Initial requests to huggingface.co
    - Following 301/302 redirects to CDN (cdn.huggingface.co, cdn-lfs.huggingface.co)
    - Caching the final downloaded content
    - Serving cached content directly on subsequent requests
    """
    
    def __init__(self, config, cache: Cache):
        self.config = config
        self.cache = cache
        self.prefix = config.get('prefix', '/huggingface/')
        self.base_url = config.get('base_url', 'https://huggingface.co')
        
        # Remove trailing slash for consistent URL building
        if self.base_url.endswith('/'):
            self.base_url = self.base_url[:-1]
            
        # Optional authentication for private models/datasets
        self.token = config.get('token')
        
        # Timeout configuration
        self.timeout = config.get('timeout', 60)  # Longer timeout for large models
        
        # Track redirect chains for logging
        self.max_redirects = config.get('max_redirects', 5)

    def can_handle(self, path):
        """Check if this backend can handle the given path."""
        return path.startswith(self.prefix)

    def _get_auth_headers(self):
        """Get authentication headers if token is configured."""
        headers = {}
        if self.token:
            headers['Authorization'] = f'Bearer {self.token}'
        return headers

    def _parse_path(self, artifact_path):
        """
        Parse artifact path to determine the resource type and location.
        
        Returns:
            dict with parsed information
        """
        path_parts = artifact_path.strip('/').split('/')
        
        if not path_parts or path_parts == ['']:
            return {'type': 'root'}
        
        # Handle datasets: datasets/{org}/{dataset}/resolve/{revision}/{filename}
        if len(path_parts) >= 5 and path_parts[0] == 'datasets':
            return {
                'type': 'dataset',
                'org': path_parts[1],
                'dataset': path_parts[2],
                'action': path_parts[3],  # 'resolve' or 'blob'
                'revision': path_parts[4],
                'filename': '/'.join(path_parts[5:]) if len(path_parts) > 5 else ''
            }
        
        # Handle models: {org}/{model}/resolve/{revision}/{filename}
        if len(path_parts) >= 4:
            return {
                'type': 'model',
                'org': path_parts[0],
                'model': path_parts[1],
                'action': path_parts[2],  # 'resolve' or 'blob'
                'revision': path_parts[3],
                'filename': '/'.join(path_parts[4:]) if len(path_parts) > 4 else ''
            }
        
        # Fallback - treat as direct path
        return {
            'type': 'direct',
            'path': artifact_path
        }

    def fetch(self, path):
        """
        Fetch Hugging Face content with redirect handling and streaming support.
        
        Handles:
        - Model files
        - Dataset files
        - Following redirects to CDN
        - Caching final content
        """
        logging.debug(f"Fetching Hugging Face path: {path}")
        artifact_path = path[len(self.prefix):]
        
        # Check cache first
        hit = self.cache.has(self.prefix, artifact_path)
        if hit:
            logging.debug(f"Cache hit for {artifact_path}")
            cached_content = hit.binary
            content_type = hit.content_type
            yield {
                "total_length": len(cached_content),
                "content": cached_content,
                "bytes_downloaded": len(cached_content),
                "content_type": content_type
            }
            return
        
        # Parse the request path
        parsed = self._parse_path(artifact_path)
        
        if parsed['type'] in ['model', 'dataset']:
            # Construct the Hugging Face URL
            if parsed['type'] == 'dataset':
                url = f"{self.base_url}/datasets/{parsed['org']}/{parsed['dataset']}/{parsed['action']}/{parsed['revision']}"
                if parsed['filename']:
                    url = f"{url}/{parsed['filename']}"
            else:  # model
                url = f"{self.base_url}/{parsed['org']}/{parsed['model']}/{parsed['action']}/{parsed['revision']}"
                if parsed['filename']:
                    url = f"{url}/{parsed['filename']}"
            
            yield from self._fetch_with_redirect(url, artifact_path)
            
        elif parsed['type'] == 'direct':
            # Direct path (fallback)
            url = f"{self.base_url}/{parsed['path']}"
            yield from self._fetch_with_redirect(url, artifact_path)
            
        else:
            yield {"error": f"Invalid Hugging Face path: {artifact_path}"}

    def _fetch_with_redirect(self, url, artifact_path):
        """
        Fetch content following redirects and cache the final result.
        
        Hugging Face typically returns 301/302 redirects to their CDN.
        We follow these redirects and cache the final content.
        """
        response = None
        redirect_count = 0
        current_url = url
        
        try:
            headers = self._get_auth_headers()
            
            # Make initial request without following redirects automatically
            # This allows us to log the redirect chain
            while redirect_count < self.max_redirects:
                logging.debug(f"Requesting: {current_url} (redirect {redirect_count})")
                
                response = requests.get(
                    current_url,
                    headers=headers,
                    allow_redirects=False,  # Handle redirects manually
                    timeout=self.timeout
                )
                
                # Check if we got a redirect (301, 302, 303, 307, 308)
                if response.status_code in (301, 302, 303, 307, 308):
                    redirect_url = response.headers.get('Location')
                    if not redirect_url:
                        yield {"error": f"Redirect response without Location header from {current_url}"}
                        return
                    
                    logging.info(f"Following redirect from {current_url} to {redirect_url}")
                    
                    # Update URL for next iteration
                    current_url = redirect_url
                    redirect_count += 1
                    
                    # Update headers - don't send auth token to CDN
                    if 'cdn' in redirect_url.lower():
                        headers = {}  # CDN doesn't need auth token
                    
                    response.close()
                    continue
                    
                # If we got a 200, break and start streaming
                if response.status_code == 200:
                    break
                    
                # If we got an error status, handle it
                response.raise_for_status()
            
            if redirect_count >= self.max_redirects:
                yield {"error": f"Too many redirects (>{self.max_redirects}) for {url}"}
                return
            
            # Now stream the final content
            logging.debug(f"Starting download from final URL: {current_url}")
            
            # Get content length if available
            content_length = response.headers.get('content-length')
            if content_length:
                content_length = int(content_length)
            
            content_type = response.headers.get('content-type', 'application/octet-stream')
            
            # Buffer for caching
            content_buffer = bytearray()
            chunk_size = 1048576  # 1MB chunks for large model files
            
            # Stream data in chunks
            try:
                # Create a new streaming request to the final URL if we had redirects
                if redirect_count > 0:
                    response.close()
                    response = requests.get(
                        current_url,
                        headers=headers,
                        stream=True,
                        timeout=self.timeout
                    )
                    response.raise_for_status()
                    
                    # Update content info from final response
                    content_length = response.headers.get('content-length')
                    if content_length:
                        content_length = int(content_length)
                    content_type = response.headers.get('content-type', 'application/octet-stream')
                
                # Stream the content
                for chunk in response.iter_content(chunk_size=chunk_size, decode_unicode=False):
                    if chunk:
                        content_buffer.extend(chunk)
                        yield {
                            "total_length": content_length,
                            "content": chunk,
                            "bytes_downloaded": len(content_buffer),
                            "content_type": content_type
                        }
                
                # Cache the complete content
                if content_buffer:
                    logging.info(f"Caching {len(content_buffer)} bytes for {artifact_path}")
                    self.cache.add(self.prefix, artifact_path, bytes(content_buffer), content_type=content_type)
                    
            except Exception as e:
                yield {"error": f"Error during streaming download: {str(e)}"}
                return
                
        except requests.RequestException as e:
            if hasattr(e, 'response') and e.response is not None:
                if e.response.status_code == 404:
                    yield {"error": f"Resource not found: {url}"}
                elif e.response.status_code == 401:
                    yield {"error": f"Authentication required for: {url}. Please configure a Hugging Face token."}
                elif e.response.status_code == 403:
                    yield {"error": f"Access forbidden: {url}. Check your permissions and token."}
                else:
                    yield {"error": f"Hugging Face API error {e.response.status_code}: {str(e)}"}
            else:
                yield {"error": f"Failed to fetch from Hugging Face: {str(e)}"}
        finally:
            if response is not None:
                response.close()

    def get_model_file(self, org, model, revision, filename):
        """
        Convenience method to download a specific model file.
        
        Args:
            org: Organization name (e.g., 'meta-llama')
            model: Model name (e.g., 'Llama-2-7b')
            revision: Revision/commit hash or branch name (e.g., 'main')
            filename: File to download (e.g., 'pytorch_model.bin')
            
        Returns:
            Generator yielding file content chunks
        """
        path = f"{self.prefix}{org}/{model}/resolve/{revision}/{filename}"
        return self.fetch(path)

    def get_dataset_file(self, org, dataset, revision, filename):
        """
        Convenience method to download a specific dataset file.
        
        Args:
            org: Organization name
            dataset: Dataset name
            revision: Revision/commit hash or branch name
            filename: File to download
            
        Returns:
            Generator yielding file content chunks
        """
        path = f"{self.prefix}datasets/{org}/{dataset}/resolve/{revision}/{filename}"
        return self.fetch(path)

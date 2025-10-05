import json
import base64
import requests
from urllib.parse import urljoin


class DockerHubBackend:
    """
    Docker Hub Registry Backend for Artifact Vault
    
    Supports Docker Registry HTTP API V2 for downloading Docker images,
    manifests, and individual layers/blobs from Docker Hub and compatible registries.
    
    Path format examples:
    - /dockerhub/library/ubuntu/manifests/latest
    - /dockerhub/library/ubuntu/blobs/sha256:abc123...
    - /dockerhub/myuser/myimage/manifests/v1.0
    """
    
    def __init__(self, config, cache):
        self.config = config
        self.cache = cache
        self.prefix = config.get('prefix', '/dockerhub/')
        self.registry_url = config.get('registry_url', 'https://registry-1.docker.io')
        self.auth_url = config.get('auth_url', 'https://auth.docker.io')
        
        # Remove trailing slash for consistent URL building
        if self.registry_url.endswith('/'):
            self.registry_url = self.registry_url[:-1]
        if self.auth_url.endswith('/'):
            self.auth_url = self.auth_url[:-1]
            
        # Optional authentication credentials
        self.username = config.get('username')
        self.password = config.get('password')
        
        # Token cache to avoid re-authentication for each request
        self._auth_token = None
        self._auth_token_scope = None

    def can_handle(self, path):
        """Check if this backend can handle the given path."""
        return path.startswith(self.prefix)

    def _get_auth_token(self, repository, actions=['pull']):
        """
        Get Docker Hub authentication token for the given repository and actions.
        
        Args:
            repository: Repository name (e.g., 'library/ubuntu')
            actions: List of actions (default: ['pull'])
        
        Returns:
            Authentication token string or None if authentication fails
        """
        scope = f"repository:{repository}:{''.join(actions)}"
        
        # Return cached token if it matches the scope
        if self._auth_token and self._auth_token_scope == scope:
            return self._auth_token
            
        try:
            # Build authentication request
            auth_params = {
                'service': 'registry.docker.io',
                'scope': scope
            }
            
            headers = {}
            if self.username and self.password:
                # Use basic authentication if credentials provided
                credentials = base64.b64encode(f"{self.username}:{self.password}".encode()).decode()
                headers['Authorization'] = f'Basic {credentials}'
            
            response = requests.get(
                f"{self.auth_url}/token",
                params=auth_params,
                headers=headers,
                timeout=30
            )
            
            if response.status_code == 200:
                token_data = response.json()
                self._auth_token = token_data.get('token')
                self._auth_token_scope = scope
                return self._auth_token
            else:
                # Fallback to anonymous access
                return None
                
        except Exception as e:
            # Log error but continue with anonymous access
            print(f"Authentication failed: {e}")
            return None

    def _parse_repository_path(self, artifact_path):
        """
        Parse artifact path to extract repository, resource type, and identifier.
        
        Examples:
        - 'library/ubuntu/manifests/latest' -> ('library/ubuntu', 'manifests', 'latest')
        - 'myuser/myimage/blobs/sha256:abc123' -> ('myuser/myimage', 'blobs', 'sha256:abc123')
        
        Returns:
            Tuple of (repository, resource_type, identifier) or None if invalid
        """
        parts = artifact_path.strip('/').split('/')
        
        if len(parts) < 4:
            return None
            
        # Handle official images (library namespace)
        if len(parts) == 4 and parts[0] != 'library':
            # Non-official image: user/image/type/id
            repository = f"{parts[0]}/{parts[1]}"
            resource_type = parts[2]
            identifier = parts[3]
        else:
            # Official image or explicit library: library/image/type/id
            if parts[0] == 'library':
                repository = '/'.join(parts[:2])
                resource_type = parts[2]
                identifier = parts[3]
            else:
                # Assume first part is username for non-library images
                repository = f"{parts[0]}/{parts[1]}"
                resource_type = parts[2]
                identifier = parts[3]
        
        if resource_type not in ['manifests', 'blobs']:
            return None
            
        return repository, resource_type, identifier

    def fetch(self, path):
        """
        Fetch Docker artifact (manifest or blob) from Docker Hub registry.
        
        Yields chunks of the artifact content with progress information.
        """
        artifact_path = path[len(self.prefix):]
        
        # Check cache first
        hit = self.cache.has(self.prefix, artifact_path)
        if hit:
            cached_content = self.cache.get(hit)
            yield {
                "total_length": len(cached_content),
                "content": cached_content,
                "bytes_downloaded": len(cached_content)
            }
            return
        
        # Parse the path
        parsed = self._parse_repository_path(artifact_path)
        if not parsed:
            yield {"error": f"Invalid Docker artifact path: {artifact_path}"}
            return
            
        repository, resource_type, identifier = parsed
        
        # Get authentication token
        auth_token = self._get_auth_token(repository)
        
        # Build request headers
        headers = {
            'Accept': 'application/vnd.docker.distribution.manifest.v2+json, '
                     'application/vnd.docker.distribution.manifest.list.v2+json, '
                     'application/vnd.docker.distribution.manifest.v1+prettyjws'
        }
        
        if auth_token:
            headers['Authorization'] = f'Bearer {auth_token}'
        
        # Build API URL
        if resource_type == 'manifests':
            url = f"{self.registry_url}/v2/{repository}/manifests/{identifier}"
        elif resource_type == 'blobs':
            url = f"{self.registry_url}/v2/{repository}/blobs/{identifier}"
        else:
            yield {"error": f"Unsupported resource type: {resource_type}"}
            return

        response = None
        try:
            response = requests.get(url, headers=headers, stream=True, timeout=30)
            response.raise_for_status()
            
            # Get content length if available
            total_length = response.headers.get('content-length')
            if total_length:
                total_length = int(total_length)
            
            # Buffer for caching
            content_buffer = bytearray()
            
            # Stream data in chunks
            chunk_size = 8192  # 8KB chunks
            try:
                for chunk in response.iter_content(chunk_size=chunk_size):
                    if chunk:  # filter out keep-alive chunks
                        content_buffer.extend(chunk)
                        yield {
                            "total_length": total_length,
                            "content": chunk,
                            "bytes_downloaded": len(content_buffer)
                        }
                
                # Cache the complete content only if download was successful
                if content_buffer:
                    self.cache.set(self.prefix, artifact_path, bytes(content_buffer))
                    
            except Exception as e:
                yield {"error": f"Error during streaming download: {str(e)}"}
                return
                
        except requests.RequestException as e:
            if hasattr(e.response, 'status_code'):
                if e.response.status_code == 401:
                    yield {"error": f"Authentication failed for {repository}. Check credentials."}
                elif e.response.status_code == 404:
                    yield {"error": f"Docker artifact not found: {repository}/{resource_type}/{identifier}"}
                elif e.response.status_code == 429:
                    yield {"error": f"Rate limited by Docker Hub. Please try again later."}
                else:
                    yield {"error": f"Docker Hub API error {e.response.status_code}: {str(e)}"}
            else:
                yield {"error": f"Failed to download from Docker Hub: {str(e)}"}
            return
        finally:
            # Ensure response is properly closed
            if response is not None:
                response.close()

    def get_manifest(self, repository, tag_or_digest):
        """
        Convenience method to get a Docker image manifest.
        
        Args:
            repository: Repository name (e.g., 'library/ubuntu')
            tag_or_digest: Tag name (e.g., 'latest') or digest (e.g., 'sha256:...')
            
        Returns:
            Generator yielding manifest content chunks
        """
        path = f"{self.prefix}{repository}/manifests/{tag_or_digest}"
        return self.fetch(path)

    def get_blob(self, repository, digest):
        """
        Convenience method to get a Docker blob/layer.
        
        Args:
            repository: Repository name (e.g., 'library/ubuntu')
            digest: Blob digest (e.g., 'sha256:...')
            
        Returns:
            Generator yielding blob content chunks
        """
        path = f"{self.prefix}{repository}/blobs/{digest}"
        return self.fetch(path)
import json
import base64
import requests
from urllib.parse import urljoin
from .cache import Cache
from typing import Dict, List, Optional, Tuple, Any


class DockerRepository:
    """
    Represents a single Docker registry repository.
    
    Handles authentication, manifest, and blob fetching for a specific registry.
    Multiple DockerRepository instances can be combined to support multi-registry
    scenarios with fallback behavior.
    """
    
    def __init__(self, registry_url: str, auth_url: str, 
                 username: Optional[str] = None, password: Optional[str] = None):
        """
        Initialize a Docker repository connection.
        
        Args:
            registry_url: Base URL of the Docker registry (e.g., 'https://registry-1.docker.io')
            auth_url: Authentication URL for token acquisition (e.g., 'https://auth.docker.io')
            username: Optional username for authenticated access
            password: Optional password for authenticated access
        """
        self.registry_url = registry_url.rstrip('/')
        self.auth_url = auth_url.rstrip('/')
        self.username = username
        self.password = password
        
        # Token cache to avoid re-authentication for each request
        self._auth_token = None
        self._auth_token_scope = None
    
    def _get_auth_token(self, repository: str, actions: Optional[List[str]] = None) -> Optional[str]:
        """
        Get Docker Hub authentication token for the given repository and actions.
        
        Args:
            repository: Repository name (e.g., 'library/ubuntu')
            actions: List of actions (default: ['pull'])
        
        Returns:
            Authentication token string or None if authentication fails
        """
        if actions is None:
            actions = ['pull']
        
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
            print(f"Authentication failed for {self.registry_url}: {e}")
            return None
    
    def fetch_artifact(self, repository: str, resource_type: str, identifier: str):
        """
        Fetch a Docker artifact (manifest or blob) from this registry.
        
        Args:
            repository: Repository name (e.g., 'library/ubuntu')
            resource_type: Either 'manifests' or 'blobs'
            identifier: Tag name, digest, or blob identifier
            
        Yields:
            Chunks with progress information or error information
        """
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
                
                # Return complete content buffer for caching
                if content_buffer:
                    yield {
                        "complete": True,
                        "content_buffer": bytes(content_buffer)
                    }
                    
            except Exception as e:
                yield {"error": f"Error during streaming download: {str(e)}"}
                return
                
        except requests.RequestException as e:
            if hasattr(e, 'response') and e.response is not None:
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


class DockerHubBackend:
    """
    Docker Hub Registry Backend for Artifact Vault
    
    Supports Docker Registry HTTP API V2 for downloading Docker images,
    manifests, and individual layers/blobs from Docker Hub and compatible registries.
    
    This backend can manage multiple Docker registries, attempting each in order
    until an artifact is found. Name conflicts are resolved by prioritizing
    repositories in the order they are defined.
    
    Path format examples:
    - /dockerhub/library/ubuntu/manifests/latest
    - /dockerhub/library/ubuntu/blobs/sha256:abc123...
    - /dockerhub/myuser/myimage/manifests/v1.0
    """
    
    def __init__(self, config: Dict[str, Any], cache: Cache):
        """
        Initialize DockerHub backend with support for multiple repositories.
        
        Config can specify either a single repository or multiple repositories:
        
        Single repository (backward compatible):
        {
            'prefix': '/dockerhub/',
            'registry_url': 'https://registry-1.docker.io',
            'auth_url': 'https://auth.docker.io',
            'username': 'optional_username',
            'password': 'optional_password'
        }
        
        Multiple repositories:
        {
            'prefix': '/dockerhub/',
            'repositories': [
                {
                    'registry_url': 'https://my-private-registry.com',
                    'auth_url': 'https://my-private-registry.com/auth',
                    'username': 'user1',
                    'password': 'pass1'
                },
                {
                    'registry_url': 'https://registry-1.docker.io',
                    'auth_url': 'https://auth.docker.io'
                }
            ]
        }
        """
        self.config = config
        self.cache = cache
        self.prefix = config.get('prefix', '/dockerhub/')
        
        # Initialize repositories
        self.repositories: List[DockerRepository] = []
        
        # Check if multiple repositories are configured
        if 'repositories' in config:
            for repo_config in config['repositories']:
                repository = DockerRepository(
                    registry_url=repo_config.get('registry_url', 'https://registry-1.docker.io'),
                    auth_url=repo_config.get('auth_url', 'https://auth.docker.io'),
                    username=repo_config.get('username'),
                    password=repo_config.get('password')
                )
                self.repositories.append(repository)
        else:
            # Single repository configuration (backward compatible)
            repository = DockerRepository(
                registry_url=config.get('registry_url', 'https://registry-1.docker.io'),
                auth_url=config.get('auth_url', 'https://auth.docker.io'),
                username=config.get('username'),
                password=config.get('password')
            )
            self.repositories.append(repository)

    def can_handle(self, path):
        """Check if this backend can handle the given path."""
        return path.startswith(self.prefix)

    def _parse_repository_path(self, artifact_path: str) -> Optional[Tuple[str, str, str]]:
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
        
        Attempts to fetch from each configured repository in order until successful.
        Yields chunks of the artifact content with progress information.
        """
        artifact_path = path[len(self.prefix):]
        
        # Check cache first
        hit = self.cache.has(self.prefix, artifact_path)
        if hit:
            cached_content = hit.binary
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
        
        # Try each repository in order until we find the artifact
        last_error = []
        for repo in self.repositories:
            # Track if we got actual content from this repository
            content_buffer = None
            has_error = False
            
            for chunk in repo.fetch_artifact(repository, resource_type, identifier):
                if "error" in chunk:
                    # This repository doesn't have the artifact or had an error
                    last_error.append(chunk["error"])
                    has_error = True
                    break
                elif "complete" in chunk and chunk["complete"]:
                    # Repository successfully fetched the complete artifact
                    content_buffer = chunk["content_buffer"]
                else:
                    # Normal progress chunk
                    yield chunk
            
            # If we successfully downloaded from this repository, cache and return
            if content_buffer is not None and not has_error:
                self.cache.add(self.prefix, artifact_path, content_buffer)
                return
        
        # If we get here, none of the repositories had the artifact
        if last_error:
            yield {"error": f"Artifact not found in any configured registry. Errors: {last_error}"}
        else:
            yield {"error": f"Artifact not found in any configured registry: {artifact_path}"}

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
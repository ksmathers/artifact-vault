import gzip
import re
import requests
from urllib.parse import urljoin, urlparse
from email.utils import parsedate_to_datetime

from .cache import Cache


class APTBackend:
    """
    APT Backend for Artifact Vault
    
    Supports APT repository structure for caching Debian packages (.deb files)
    and repository metadata (Packages, Release files, etc.).
    
    Path format examples:
    - /apt/ubuntu/dists/jammy/Release
    - /apt/ubuntu/dists/jammy/main/binary-amd64/Packages.gz
    - /apt/ubuntu/pool/main/c/curl/curl_7.81.0-1ubuntu1.4_amd64.deb
    - /apt/debian/dists/bullseye/main/binary-amd64/Packages
    """
    
    def __init__(self, config, cache : Cache):
        self.config = config
        self.cache = cache
        self.prefix = config.get('prefix', '/apt/')
        self.mirror_url = config.get('mirror_url', 'http://archive.ubuntu.com/ubuntu/')
        
        # Remove trailing slash for consistent URL building
        if self.mirror_url.endswith('/'):
            self.mirror_url = self.mirror_url[:-1]
            
        # Optional authentication for private repositories
        self.username = config.get('username')
        self.password = config.get('password')
        
        # Timeout configuration
        self.timeout = config.get('timeout', 30)
        
        # APT-specific settings
        self.user_agent = config.get('user_agent', 'Artifact-Vault APT Backend/1.0')

    def can_handle(self, path):
        """Check if this backend can handle the given path."""
        return path.startswith(self.prefix)

    def _get_auth_headers(self):
        """Get authentication headers if credentials are configured."""
        headers = {'User-Agent': self.user_agent}
        
        if self.username and self.password:
            import base64
            credentials = base64.b64encode(f"{self.username}:{self.password}".encode()).decode()
            headers['Authorization'] = f'Basic {credentials}'
        
        return headers

    def _parse_path(self, artifact_path):
        """
        Parse artifact path to determine request type.
        
        Returns:
            dict with 'type' and relevant metadata
        """
        path_parts = artifact_path.strip('/').split('/')
        
        if not path_parts or path_parts == ['']:
            return {'type': 'root'}
        
        # Handle different APT path patterns
        if len(path_parts) >= 2:
            if path_parts[0] == 'dists':
                # Distribution metadata: /dists/jammy/Release, /dists/jammy/main/binary-amd64/Packages
                if len(path_parts) == 3 and path_parts[2] in ['Release', 'Release.gpg', 'InRelease']:
                    return {
                        'type': 'release',
                        'distribution': path_parts[1],
                        'file': path_parts[2]
                    }
                elif len(path_parts) >= 5 and path_parts[3].startswith('binary-'):
                    return {
                        'type': 'packages',
                        'distribution': path_parts[1],
                        'component': path_parts[2],
                        'architecture': path_parts[3],
                        'file': '/'.join(path_parts[4:])
                    }
                else:
                    return {
                        'type': 'dist_other',
                        'path': artifact_path
                    }
            elif path_parts[0] == 'pool':
                # Package files: /pool/main/c/curl/curl_7.81.0-1ubuntu1.4_amd64.deb
                return {
                    'type': 'package_file',
                    'component': path_parts[1] if len(path_parts) > 1 else '',
                    'first_letter': path_parts[2] if len(path_parts) > 2 else '',
                    'package_name': path_parts[3] if len(path_parts) > 3 else '',
                    'filename': '/'.join(path_parts[4:]) if len(path_parts) > 4 else '',
                    'full_path': artifact_path
                }
        
        # Fallback for other paths
        return {
            'type': 'generic',
            'path': artifact_path
        }

    def _get_content_type(self, path, response_headers=None):
        """Determine appropriate content type based on file extension."""
        if path.endswith('.deb'):
            return 'application/vnd.debian.binary-package'
        elif path.endswith('.gz'):
            return 'application/gzip'
        elif path.endswith('.xz'):
            return 'application/x-xz'
        elif path.endswith('.bz2'):
            return 'application/x-bzip2'
        elif path.endswith(('.gpg', '.sig')):
            return 'application/pgp-signature'
        elif 'Packages' in path:
            return 'text/plain'
        elif 'Release' in path:
            return 'text/plain'
        elif response_headers:
            return response_headers.get('content-type', 'application/octet-stream')
        else:
            return 'application/octet-stream'

    def fetch(self, path):
        """
        Fetch APT content with streaming support.
        
        Handles different types of APT requests:
        - Release files and signatures
        - Package index files (Packages, Packages.gz)
        - Debian package files (.deb)
        """
        artifact_path = path[len(self.prefix):]
        
        # Check cache first
        hit = self.cache.has(self.prefix, artifact_path)
        if hit:
            cached_content = hit.binary
            content_type = self._get_content_type(artifact_path)
            yield {
                "total_length": len(cached_content),
                "content": cached_content,
                "bytes_downloaded": len(cached_content),
                "content_type": content_type
            }
            return
        
        # Parse the request path
        parsed = self._parse_path(artifact_path)
        
        # Build URL based on path type
        url = f"{self.mirror_url}/{artifact_path}"
        
        # Handle different content types appropriately
        if parsed['type'] in ['release', 'packages', 'dist_other']:
            yield from self._fetch_metadata_file(url, artifact_path, parsed)
        elif parsed['type'] == 'package_file':
            yield from self._fetch_package_file(url, artifact_path, parsed)
        else:
            yield from self._fetch_generic_file(url, artifact_path)

    def _fetch_metadata_file(self, url, artifact_path, parsed):
        """Fetch APT metadata files (Release, Packages, etc.)."""
        response = None
        try:
            headers = self._get_auth_headers()
            response = requests.get(url, headers=headers, timeout=self.timeout, stream=True)
            response.raise_for_status()
            
            # Handle compressed content
            content_encoding = response.headers.get('content-encoding', '').lower()
            total_length = response.headers.get('content-length')
            if total_length:
                total_length = int(total_length)
            
            content_buffer = bytearray()
            
            if content_encoding == 'gzip' or artifact_path.endswith('.gz'):
                # Handle gzipped content - keep compressed for streaming, decompress for cache
                raw_buffer = bytearray()
                chunk_size = 8192
                
                for chunk in response.iter_content(chunk_size=chunk_size, decode_unicode=False):
                    if chunk:
                        raw_buffer.extend(chunk)
                        # Decompress for content buffer (cache)
                        try:
                            decompressed = gzip.decompress(raw_buffer)
                            content_buffer = bytearray(decompressed)
                        except gzip.BadGzipFile:
                            # Partial data, continue collecting
                            pass
                        
                        # Yield compressed chunk for streaming
                        yield {
                            "total_length": total_length,
                            "content": chunk,
                            "bytes_downloaded": len(raw_buffer),
                            "content_type": self._get_content_type(artifact_path, response.headers)
                        }
                
                # Cache decompressed content if we have it
                if content_buffer:
                    self.cache.add(self.prefix, artifact_path, bytes(content_buffer))
                else:
                    # If decompression failed, cache raw content
                    self.cache.add(self.prefix, artifact_path, bytes(raw_buffer))
            else:
                # Handle uncompressed content
                chunk_size = 8192
                for chunk in response.iter_content(chunk_size=chunk_size):
                    if chunk:
                        content_buffer.extend(chunk)
                        yield {
                            "total_length": total_length,
                            "content": chunk,
                            "bytes_downloaded": len(content_buffer),
                            "content_type": self._get_content_type(artifact_path, response.headers)
                        }
                
                # Cache the content
                if content_buffer:
                    self.cache.add(self.prefix, artifact_path, bytes(content_buffer))
                    
        except requests.RequestException as e:
            if hasattr(e, 'response') and e.response is not None:
                if e.response.status_code == 404:
                    yield {"error": f"APT resource not found: {url}"}
                else:
                    yield {"error": f"APT repository error {e.response.status_code}: {str(e)}"}
            else:
                yield {"error": f"Failed to fetch from APT repository: {str(e)}"}
        finally:
            if response is not None:
                response.close()

    def _fetch_package_file(self, url, artifact_path, parsed):
        """Fetch .deb package files with streaming."""
        response = None
        try:
            headers = self._get_auth_headers()
            response = requests.get(url, headers=headers, stream=True, timeout=self.timeout)
            response.raise_for_status()
            
            # Get content length
            total_length = response.headers.get('content-length')
            if total_length:
                total_length = int(total_length)
            
            # Stream .deb files directly (they're not typically compressed by HTTP)
            content_buffer = bytearray()
            chunk_size = 8192
            
            for chunk in response.iter_content(chunk_size=chunk_size):
                if chunk:
                    content_buffer.extend(chunk)
                    yield {
                        "total_length": total_length,
                        "content": chunk,
                        "bytes_downloaded": len(content_buffer),
                        "content_type": self._get_content_type(artifact_path, response.headers)
                    }
            
            # Cache the complete package
            if content_buffer:
                self.cache.add(self.prefix, artifact_path, bytes(content_buffer))
                    
        except requests.RequestException as e:
            if hasattr(e, 'response') and e.response is not None:
                if e.response.status_code == 404:
                    yield {"error": f"Package not found: {url}"}
                else:
                    yield {"error": f"APT download error {e.response.status_code}: {str(e)}"}
            else:
                yield {"error": f"Failed to download package: {str(e)}"}
        finally:
            if response is not None:
                response.close()

    def _fetch_generic_file(self, url, artifact_path):
        """Fetch other APT-related files."""
        response = None
        try:
            headers = self._get_auth_headers()
            response = requests.get(url, headers=headers, stream=True, timeout=self.timeout)
            response.raise_for_status()
            
            total_length = response.headers.get('content-length')
            if total_length:
                total_length = int(total_length)
            
            content_buffer = bytearray()
            chunk_size = 8192
            
            for chunk in response.iter_content(chunk_size=chunk_size):
                if chunk:
                    content_buffer.extend(chunk)
                    yield {
                        "total_length": total_length,
                        "content": chunk,
                        "bytes_downloaded": len(content_buffer),
                        "content_type": self._get_content_type(artifact_path, response.headers)
                    }
            
            if content_buffer:
                self.cache.add(self.prefix, artifact_path, bytes(content_buffer))
                    
        except requests.RequestException as e:
            if hasattr(e, 'response') and e.response is not None:
                if e.response.status_code == 404:
                    yield {"error": f"File not found: {url}"}
                else:
                    yield {"error": f"Download error {e.response.status_code}: {str(e)}"}
            else:
                yield {"error": f"Failed to download: {str(e)}"}
        finally:
            if response is not None:
                response.close()

    def get_release_file(self, distribution):
        """
        Convenience method to get a distribution's Release file.
        
        Args:
            distribution: Distribution name (e.g., 'jammy', 'bullseye')
            
        Returns:
            Generator yielding Release file content
        """
        path = f"{self.prefix}dists/{distribution}/Release"
        return self.fetch(path)

    def get_packages_file(self, distribution, component, architecture, compressed=True):
        """
        Convenience method to get a Packages file.
        
        Args:
            distribution: Distribution name (e.g., 'jammy')
            component: Component name (e.g., 'main', 'universe')
            architecture: Architecture (e.g., 'amd64', 'arm64')
            compressed: Whether to fetch compressed version
            
        Returns:
            Generator yielding Packages file content
        """
        filename = "Packages.gz" if compressed else "Packages"
        path = f"{self.prefix}dists/{distribution}/{component}/binary-{architecture}/{filename}"
        return self.fetch(path)

    def get_package(self, package_path):
        """
        Convenience method to download a specific .deb package.
        
        Args:
            package_path: Full path to package (e.g., 'pool/main/c/curl/curl_7.81.0-1ubuntu1.4_amd64.deb')
            
        Returns:
            Generator yielding package content chunks
        """
        path = f"{self.prefix}{package_path}"
        return self.fetch(path)
import re
import requests
import gzip
import io
from urllib.parse import urljoin, urlparse, unquote
from html.parser import HTMLParser
import logging


class PyPILinkExtractor(HTMLParser):
    """Extract download links from PyPI simple API HTML pages.
    

    """
    
    def __init__(self):
        super().__init__()
        self.links = []
        self.base_url = None
    
    def handle_starttag(self, tag, attrs):
        if tag == 'a':
            href = None
            for attr_name, attr_value in attrs:
                if attr_name == 'href':
                    href = attr_value
                    break
            if href:
                # Convert relative URLs to absolute URLs
                if self.base_url and not href.startswith(('http://', 'https://')):
                    href = urljoin(self.base_url, href)
                self.links.append(href)


class PyPIBackend:
    """
    PyPI Backend for Artifact Vault
    
    Supports the PyPI Simple API that pip uses for package discovery and downloads.
    Handles both simple index pages and direct package file downloads with streaming.
    
    Path format examples:
    - /pypi/simple/ - Package index
    - /pypi/simple/requests/ - Package page with download links
    - /pypi/packages/source/r/requests/requests-2.28.1.tar.gz - Direct package download

    To handle all of these with a single prefix, we use /pypi/ as the base path, and have the
    pip client configured to use /pypi/simple/ as the index URL.  The packages URLs are
    rewritten in the HTML to point to our cache.
    """
    
    def __init__(self, config, cache):
        self.config = config
        self.cache = cache
        self.prefix = config.get('prefix', '/pypi/')
        self.index_url = config.get('index_url', 'https://pypi.org/simple/')
        self.packages_url = config.get('packages_url', 'https://files.pythonhosted.org/packages/')
        
        # Remove trailing slashes for consistent URL building
        if self.index_url.endswith('/'):
            self.index_url = self.index_url[:-1]
        if self.packages_url.endswith('/'):
            self.packages_url = self.packages_url[:-1]
            
        # Optional authentication for private PyPI servers
        self.username = config.get('username')
        self.password = config.get('password')
        
        # Timeout configuration
        self.timeout = config.get('timeout', 30)

    def can_handle(self, path):
        """Check if this backend can handle the given path."""
        return path.startswith(self.prefix)

    def _get_auth_headers(self):
        """Get authentication headers if credentials are configured."""
        if self.username and self.password:
            import base64
            credentials = base64.b64encode(f"{self.username}:{self.password}".encode()).decode()
            return {'Authorization': f'Basic {credentials}'}
        return {}

    def _parse_path(self, artifact_path):
        """
        Parse artifact path to determine request type and target.
        
        Returns:
            dict with 'type', 'package_name', 'filename', etc.
        """
        path_parts = artifact_path.strip('/').split('/')
        
        if not path_parts or path_parts == ['']:
            return {'type': 'root'}
        
        if path_parts[0] == 'simple':
            if len(path_parts) == 1:
                # /simple/ - package index
                return {'type': 'simple_index'}
            elif len(path_parts) == 2:
                # /simple/package-name/ - package page
                return {
                    'type': 'simple_package',
                    'package_name': path_parts[1].rstrip('/')
                }
        elif path_parts[0] == 'packages':
            # Direct package download
            # /packages/source/r/requests/requests-2.28.1.tar.gz
            # /packages/py2.py3/r/requests/requests-2.28.1-py2.py3-none-any.whl
            if len(path_parts) >= 5:
                return {
                    'type': 'package_file',
                    'path_type': path_parts[1],  # 'source' or python version
                    'package_letter': path_parts[2],
                    'package_name': path_parts[3],
                    'filename': '/'.join(path_parts[4:])
                }
        
        # Fallback - treat as direct file download
        return {
            'type': 'direct_file',
            'path': artifact_path
        }

    def _rewrite_package_links(self, html_content, base_url):
        """
        Rewrite package download links in PyPI HTML to point to our cache.
        
        This converts links like:
        https://files.pythonhosted.org/packages/.../requests-2.28.1.tar.gz
        to:
        /pypi/packages/.../requests-2.28.1.tar.gz
        """
        # Extract all links from the HTML
        parser = PyPILinkExtractor()
        parser.base_url = base_url
        parser.feed(html_content.decode('utf-8', errors='ignore'))
        
        # Rewrite the HTML to point package downloads to our cache
        modified_html = html_content.decode('utf-8', errors='ignore')
        
        for link in parser.links:
            # Check if this is a package file link
            if 'files.pythonhosted.org/packages/' in link:
                # Extract the package path after /packages/
                package_path = link.split('/packages/', 1)[1]
                # Rewrite to point to our backend
                new_link = f"{self.prefix.rstrip('/')}/packages/{package_path}"
                modified_html = modified_html.replace(link, new_link)
            elif self.packages_url in link:
                # Handle custom packages URL
                package_path = link.replace(self.packages_url + '/', '')
                new_link = f"{self.prefix.rstrip('/')}/packages/{package_path}"
                modified_html = modified_html.replace(link, new_link)
        
        return modified_html.encode('utf-8')

    def fetch(self, path):
        """
        Fetch PyPI content with streaming support.
        
        Handles different types of PyPI requests:
        - Simple API index pages
        - Package-specific pages
        - Direct package file downloads
        """
        logging.debug(f"Fetching path: {path}")
        artifact_path = path[len(self.prefix):]
        
        # Check cache first
        hit = self.cache.has(self.prefix, artifact_path)
        if hit:
            logging.debug(f"Cache hit for {artifact_path}")
            cached_content = self.cache.get(hit)
            content_type = self.cache.get_content_type(hit)
            yield {
                "total_length": len(cached_content),
                "content": cached_content,
                "bytes_downloaded": len(cached_content),
                "content_type": content_type
            }
            return
        
        # Parse the request path
        parsed = self._parse_path(artifact_path)
        
        if parsed['type'] == 'simple_index':
            # Request for /simple/ - package index
            url = self.index_url
            yield from self._fetch_html_page(url, artifact_path)
            
        elif parsed['type'] == 'simple_package':
            # Request for /simple/package-name/ - package page with download links
            package_name = parsed['package_name']
            url = f"{self.index_url}/{package_name}/"
            yield from self._fetch_package_page(url, artifact_path)
            
        elif parsed['type'] == 'package_file':
            # Direct package file download
            # Reconstruct the file URL
            path_parts = [
                parsed['path_type'],
                parsed['package_letter'], 
                parsed['package_name'],
                parsed['filename']
            ]
            url = f"{self.packages_url}/{'/'.join(path_parts)}"
            yield from self._fetch_package_file(url, artifact_path)
            
        elif parsed['type'] == 'direct_file':
            # Direct file download (fallback)
            url = f"{self.packages_url}/{parsed['path']}"
            yield from self._fetch_package_file(url, artifact_path)
            
        else:
            yield {"error": f"Invalid PyPI path: {artifact_path}"}

    def _fetch_html_page(self, url, artifact_path):
        """Fetch and cache HTML pages (simple index, package pages)."""
        
        response = None
        try:
            headers = self._get_auth_headers()
            response = requests.get(url, headers=headers, timeout=self.timeout)
            response.raise_for_status()
            
            # For HTML pages, we get the full content first
            content = response.content
            
            # Cache the content
            self.cache.set(self.prefix, artifact_path, content)
            
            # Yield the content
            yield {
                "total_length": len(content),
                "content": content,
                "bytes_downloaded": len(content),
                "content_type": response.headers.get('content-type', 'text/html')
            }
            
        except requests.RequestException as e:
            if hasattr(e, 'response') and e.response is not None:
                if e.response.status_code == 404:
                    yield {"error": f"Package not found: {url}"}
                else:
                    yield {"error": f"PyPI API error {e.response.status_code}: {str(e)}"}
            else:
                yield {"error": f"Failed to fetch from PyPI: {str(e)}"}
        finally:
            if response is not None:
                response.close()

    def _fetch_package_page(self, url, artifact_path):
        """Fetch package page and rewrite download links to point to our cache."""
        response = None
        try:
            headers = self._get_auth_headers()
            response = requests.get(url, headers=headers, timeout=self.timeout)
            response.raise_for_status()
            
            # Get the HTML content
            html_content = response.content
            
            # Rewrite package download links to point to our cache
            modified_content = self._rewrite_package_links(html_content, url)
            content_type = response.headers.get('content-type', 'text/html')
            
            # Cache the modified content
            self.cache.set(self.prefix, artifact_path, modified_content, content_type=content_type)
            
            # Yield the modified content
            yield {
                "total_length": len(modified_content),
                "content": modified_content,
                "bytes_downloaded": len(modified_content),
                "content_type": content_type
            }
            
        except requests.RequestException as e:
            if hasattr(e, 'response') and e.response is not None:
                if e.response.status_code == 404:
                    yield {"error": f"Package not found: {url}"}
                else:
                    yield {"error": f"PyPI API error {e.response.status_code}: {str(e)}"}
            else:
                yield {"error": f"Failed to fetch from PyPI: {str(e)}"}
        finally:
            if response is not None:
                response.close()

    def _fetch_package_file(self, url, artifact_path):
        """Fetch package files (wheels, tarballs) with streaming."""
        response = None
        try:
            headers = self._get_auth_headers()
            headers['Accept-Encoding'] = 'identity'  # Request uncompressed content
            response = requests.get(url, headers=headers, stream=True, timeout=self.timeout)
            response.raise_for_status()
            
            # Get content length
            content_length = response.headers.get('content-length')
            if content_length:
                content_length = int(content_length)
            
            logging.debug(f"Starting download of {url}, raw content-length: {content_length}")
            
            # Buffer for caching (uncompressed data)
            content_buffer = bytearray()
            chunk_size = 8192  # 8KB chunks
            
            # Read streaming data; assumes uncompressed due to Accept-Encoding: identity
            try:
                for chunk in response.iter_content(chunk_size=chunk_size, decode_unicode=False):
                    if chunk:
                        content_buffer.extend(chunk)
                        yield {
                            "total_length": content_length,
                            "content": chunk,
                            "bytes_downloaded": len(content_buffer),
                            "content_type": response.headers.get('content-type', 'application/octet-stream')
                        }
                        
            except Exception as e:
                yield {"error": f"Error during streaming download: {str(e)}"}
                return
            
            # Cache the content
            logging.debug(f"Completed download of {url}, bytes: {len(content_buffer)}")
            
            if content_buffer:
                content_type = response.headers.get('content-type', 'application/octet-stream')
                self.cache.set(self.prefix, artifact_path, bytes(content_buffer), content_type=content_type)
                
        except requests.RequestException as e:
            if hasattr(e, 'response') and e.response is not None:
                if e.response.status_code == 404:
                    yield {"error": f"Package file not found: {url}"}
                else:
                    yield {"error": f"PyPI download error {e.response.status_code}: {str(e)}"}
            else:
                yield {"error": f"Failed to download from PyPI: {str(e)}"}
        finally:
            if response is not None:
                response.close()

    def get_package_info(self, package_name):
        """
        Convenience method to get package information.
        
        Args:
            package_name: Name of the package (e.g., 'requests')
            
        Returns:
            Generator yielding package page content
        """
        path = f"{self.prefix}simple/{package_name}/"
        return self.fetch(path)

    def get_package_file(self, package_name, filename):
        """
        Convenience method to download a specific package file.
        
        Args:
            package_name: Name of the package (e.g., 'requests')
            filename: Full filename (e.g., 'requests-2.28.1.tar.gz')
            
        Returns:
            Generator yielding package file content chunks
        """
        # Try to determine the package path structure
        # This is a simplified approach - in practice, you'd parse the package page first
        first_letter = package_name[0].lower()
        path = f"{self.prefix}packages/source/{first_letter}/{package_name}/{filename}"
        return self.fetch(path)
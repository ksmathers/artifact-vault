# Artifact Vault main application

# Artifact Vault is an read-through cache for binary artifacts.  Backends
# exist for PyPI, DockerHub, and generic HTTP(S) servers.  Artifacts are
# cached in a local directory, and are served via a built-in HTTP server.

import argparse
import logging

def initialize_backends(config):
    from artifact_vault.cache import Cache
    cache = Cache(config)
    backends = []
    for backend in config.get('backends', []):
        logging.info(f"Initializing {backend['type']} backend: {backend.get('name', '*unnamed*')}")
        if backend['type'] == 'pypi':
            from artifact_vault.backend_pypi import PyPIBackend
            backends.append(PyPIBackend(backend.get('config', {}), cache))
        elif backend['type'] == 'dockerhub':
            from artifact_vault.backend_dockerhub import DockerHubBackend
            backends.append(DockerHubBackend(backend.get('config', {}), cache))
        elif backend['type'] == 'http':
            from artifact_vault.backend_http import HTTPBackend
            backends.append(HTTPBackend(backend.get('config', {}), cache))
        elif backend['type'] == 'apt':
            from artifact_vault.backend_apt import APTBackend
            backends.append(APTBackend(backend.get('config', {}), cache))
        elif backend['type'] == 'huggingface':
            from artifact_vault.backend_huggingface import HuggingFaceBackend
            backends.append(HuggingFaceBackend(backend.get('config', {}), cache))
        else:
            logging.warning(f"Unknown backend type: {backend['type']}")
    return backends 

def load_config(config_path):
    import yaml
    try:
        with open(config_path, 'r') as f:
            config = yaml.safe_load(f)
        logging.info(f"Configuration loaded from {config_path}")
        return config
    except Exception as e:
        logging.error(f"Error loading configuration: {e}")
        return None
    
def start_http_server(config, backends):
    from http.server import HTTPServer, SimpleHTTPRequestHandler
    #import threading

    class ArtifactRequestHandler(SimpleHTTPRequestHandler):
        def do_HEAD(self):
            """Handle HEAD requests by checking cache or proxying to upstream."""
            import requests
            for backend in backends:
                if backend.can_handle(self.path):
                    # Check if we have it cached
                    artifact_path = self.path[len(backend.prefix):]
                    hit = backend.cache.has(backend.prefix, artifact_path)
                    if hit:
                        # We have it cached - return headers
                        self.send_response(200)
                        self.send_header("Content-Type", hit.content_type)
                        self.send_header("Content-Length", str(len(hit.binary)))
                        self.end_headers()
                        return
                    
                    # Not cached - make a HEAD request upstream to get real headers
                    # This is important for huggingface_hub validation
                    try:
                        # Construct upstream URL (specific to HuggingFace backend for now)
                        if hasattr(backend, 'base_url'):
                            upstream_url = f"{backend.base_url}/{artifact_path}"
                            headers = {}
                            if hasattr(backend, '_get_auth_headers'):
                                headers = backend._get_auth_headers()
                            
                            # Make HEAD request, following redirects
                            response = requests.head(upstream_url, headers=headers, allow_redirects=True, timeout=30)
                            
                            # Proxy the response
                            self.send_response(response.status_code)
                            # Copy important headers
                            for header in ['Content-Type', 'Content-Length', 'ETag', 'Last-Modified', 'Accept-Ranges']:
                                if header in response.headers:
                                    self.send_header(header, response.headers[header])
                            self.end_headers()
                            return
                    except Exception as e:
                        logging.warning(f"HEAD request to upstream failed: {e}")
                        # Fallback to basic response
                        self.send_response(200)
                        self.send_header("Content-Type", "application/octet-stream")
                        self.end_headers()
                        return
            # No backend can handle this path
            self.send_response(404)
            self.end_headers()
        
        def do_GET(self):
            loglevel = logging.getLogger().level
            #print("headers", self.headers)
            sent_headers = False
            for backend in backends:
                if backend.can_handle(self.path):
                    # Stream the artifact in chunks
                    for artifact in backend.fetch(self.path):
                        if artifact:
                            if "error" in artifact:
                                logging.error(f"Error fetching artifact: {artifact['error']}")
                                self.send_response(502)
                                self.end_headers()
                                self.wfile.write(artifact['error'].encode())
                            else:
                                if artifact["total_length"] and artifact["bytes_downloaded"]:
                                    percent_complete = (artifact["bytes_downloaded"] / artifact["total_length"]) * 100
                                if loglevel <= logging.DEBUG:
                                    print(f"Transfer {percent_complete:.2f}% complete", end='\r')
                                if not sent_headers:
                                    self.send_response(200)
                                    # Use content-type from backend if provided, otherwise default
                                    content_type = artifact.get("content_type", "application/octet-stream")
                                    self.send_header("Content-Type", content_type)
                                    if "total_length" in artifact and artifact["total_length"] is not None:
                                        self.send_header("Content-Length", str(artifact["total_length"]))
                                    # if "content_encoding" in artifact:
                                    #     logging.debug(f"Setting Content-Encoding: {artifact['content_encoding']}")
                                    #     self.send_header("Content-Encoding", artifact["content_encoding"])
                                    self.end_headers()
                                    sent_headers = True
                                
                                # Write content in chunks to avoid socket write size limits
                                content = artifact["content"]
                                chunk_size = 65536  # 64KB chunks for writing to socket
                                offset = 0
                                while offset < len(content):
                                    chunk = content[offset:offset + chunk_size]
                                    self.wfile.write(chunk)
                                    offset += len(chunk)
                    # EOF
                    return
            logging.warning(f"GET request for unknown backend: {self.path}")
            self.send_response(404)
            self.end_headers()
            self.wfile.write(b'Artifact not found')

    server_address = (config.get('http_host', 'localhost'), config.get('http_port', 8080))
    httpd = HTTPServer(server_address, ArtifactRequestHandler)
    logging.info(f"Starting HTTP server on {server_address[0]}:{server_address[1]}")
    httpd.serve_forever()

def main():
    """Main entry point for Artifact Vault.
    
    Parses command-line arguments, loads configuration, initializes backends,
    and starts the HTTP server.
    
    Config File Example:
    ```yaml
    http_host: localhost
    http_port: 8080
    cache_dir: /path/to/cache
    backends:
      - type: pypi
        config:
          prefix: /pypi
          index_url: https://pypi.org/simple
      - type: dockerhub
        config:
          prefix: /dockerhub
          registry_url: https://registry.hub.docker.com
      - type: http
        config:
          prefix: /example
          base_url: https://example.com/artifacts
    ```
    """
    parser = argparse.ArgumentParser(description="Artifact Vault - A read-through cache for binary artifacts")
    parser.add_argument('--config', type=str, help='Path to configuration file', required=True)
    parser.add_argument('--log-level', type=str, choices=['DEBUG', 'INFO', 'WARNING', 'ERROR', 'CRITICAL'], default='INFO', help='Logging level')
    args = parser.parse_args()

    # Set up logging
    logging.basicConfig(level=getattr(logging, args.log_level))
    logger = logging.getLogger(__name__)
    logger.info("Starting Artifact Vault with config: %s", args.config)

    # Load configuration
    config = load_config(args.config)
    if not config:
        logger.error("Failed to load configuration.")
        return

    # Initialize backends
    backends = initialize_backends(config)
    if not backends:
        logger.error("No backends initialized.")
        return

    # Start HTTP server
    start_http_server(config, backends)

if __name__ == "__main__":
    main()
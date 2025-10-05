from .cache import Cache
import requests

class HTTPBackend:
    def __init__(self, config, cache : Cache):
        self.config = config
        self.cache : Cache = cache
        self.prefix = config.get('prefix', '/http/')
        self.base_url = config.get('base_url', '')
        if not self.base_url:
            raise ValueError(f"HTTPBackend {self.prefix} requires 'base_url' in config")
    
    def can_handle(self, path):
        return path.startswith(self.prefix)

    def fetch(self, path):
        import requests
        artifact_path = path[len(self.prefix):]
        url = f"{self.base_url}/{artifact_path}"
        hit = self.cache.has(self.prefix, artifact_path)
        if hit:
            # For cached content, yield it as a single block
            cached_content = hit.binary
            yield {
                "total_length": len(cached_content), 
                "content": cached_content,
                "bytes_downloaded": len(cached_content)
                }
            return
        
        response = None
        try:
            response = requests.get(url, stream=True, timeout=30)
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
                    self.cache.add(self.prefix, artifact_path, bytes(content_buffer))
                    
            except Exception as e:
                yield {"error": f"Error during streaming download: {str(e)}"}
                return
                
        except requests.RequestException as e:
            yield {"error": f"Failed to download {url}: {str(e)}"}
            return
        finally:
            # Ensure response is properly closed
            if response is not None:
                response.close()

import os

class Cache:
    def __init__(self, config):
        self.cache_dir = config.get('cache_dir', '/tmp/artifact_vault_cache')

    def has(self, prefix, name):
        path = os.path.join(self.cache_dir, prefix.strip('/'), name + ".binary")
        if os.path.isfile(path):
            return path
        return None

    def get(self, path):
        with open(path, 'rb') as f:
            return f.read()
        
    def get_content_type(self, path):
        ctype_path = path.replace(".binary", ".content_type")
        if os.path.isfile(ctype_path):
            with open(ctype_path, 'r') as f:
                return f.read().strip()
        return "application/octet-stream"

    def set(self, prefix, name, content, content_type=None):
        path = os.path.join(self.cache_dir, prefix.strip('/'), name + ".binary")
        dir_path = os.path.dirname(path)
        os.makedirs(dir_path, exist_ok=True)

        # Save content type if provided
        if content_type:
            ctype_path = path.replace(".binary", ".content_type")
            with open(ctype_path, 'w') as f:
                f.write(content_type)

        # Save the binary content
        with open(path, 'wb') as f:
            f.write(content)
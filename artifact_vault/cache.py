
import os
import json
import logging

class Artifact:
    def __init__(self, path):
        self.path = path
        self.is_dirty = False
        self.xattr = self.load_xattr()

    def load_xattr(self):
        xpath = self.path.replace(".binary", ".xattr")
        ctpath = self.path.replace(".binary", ".content-type") # legacy
        if os.path.isfile(xpath):
            with open(xpath, 'rt') as f:
                xattr = json.loads(f.read())
        elif os.path.isfile(ctpath):
            with open(ctpath, 'rt') as f:
                xattr = {"content_type": f.read().strip()}
        else:
            xattr = {}
        return xattr
    
    def save_xattr(self):
        if not self.is_dirty:
            return
        xpath = self.path.replace(".binary", ".xattr")
        dir_path = os.path.dirname(xpath)
        os.makedirs(dir_path, exist_ok=True)
        with open(xpath, 'wt') as f:
            f.write(json.dumps(self.xattr))
        self.is_dirty = False
    
    def exists(self):
        return os.path.isfile(self.path)
    
    def __bool__(self):
        return self.exists()

    @property
    def content_type(self):
        return self.xattr.get("content_type", "application/octet-stream")

    @content_type.setter
    def content_type(self, value):
        self.xattr["content_type"] = value
        self.is_dirty = True

    @property
    def binary(self):
        with open(self.path, 'rb') as f:
            return f.read()

    @binary.setter
    def binary(self, value):
        with open(self.path, 'wb') as f:
            f.write(value)


class Cache:
    def __init__(self, config):
        self.cache_dir = config.get('cache_dir', '/tmp/artifact_vault_cache')

    def has(self, prefix, name) -> Artifact:
        path = os.path.join(self.cache_dir, prefix.strip('/'), name.strip('/') + ".binary")
        art = Artifact(path)
        logging.debug(f"Cache lookup for {prefix}{name}: {'HIT' if art.exists() else 'MISS'}")
        return art

    def add(self, prefix, name, content, content_type=None) -> Artifact:
        art = self.has(prefix, name)

        # Ensure directory exists
        os.makedirs(os.path.dirname(art.path), exist_ok=True)

        # Write the artifact
        art.binary = content
        art.content_type = content_type
        art.save_xattr()
        logging.debug(f"Cached artifact at {art.path} with content_type={art.content_type}")
        return art

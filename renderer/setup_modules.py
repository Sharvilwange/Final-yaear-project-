import os
import urllib.request
import tarfile
import json
import io

NODE_MODULES = os.path.join(os.path.dirname(__file__), 'node_modules')
os.makedirs(NODE_MODULES, exist_ok=True)

def install_pkg(pkg_name, version=None):
    print(f"Installing {pkg_name}...")
    url = f"https://registry.npmjs.org/{pkg_name}"
    req = urllib.request.Request(url, headers={'User-Agent': 'Mozilla/5.0'})
    with urllib.request.urlopen(req) as resp:
        meta = json.loads(resp.read().decode('utf-8'))
    
    if not version:
        version = meta['dist-tags']['latest']
    
    tarball_url = meta['versions'][version]['dist']['tarball']
    print(f"Downloading {tarball_url}...")
    
    req_tar = urllib.request.Request(tarball_url, headers={'User-Agent': 'Mozilla/5.0'})
    with urllib.request.urlopen(req_tar) as resp_tar:
        tar_bytes = resp_tar.read()
    
    target_dir = os.path.join(NODE_MODULES, pkg_name)
    os.makedirs(target_dir, exist_ok=True)
    
    with tarfile.open(fileobj=io.BytesIO(tar_bytes), mode='r:gz') as tar:
        for member in tar.getmembers():
            # Skip top-level 'package/' directory prefix
            parts = member.name.split('/', 1)
            if len(parts) > 1 and parts[1]:
                rel_path = parts[1]
                dest_path = os.path.join(target_dir, rel_path)
                if member.isdir():
                    os.makedirs(dest_path, exist_ok=True)
                else:
                    os.makedirs(os.path.dirname(dest_path), exist_ok=True)
                    with tar.extractfile(member) as src, open(dest_path, 'wb') as dst:
                        dst.write(src.read())

    print(f"Successfully installed {pkg_name}@{version} into node_modules/{pkg_name}")

if __name__ == '__main__':
    install_pkg('three', '0.170.0')

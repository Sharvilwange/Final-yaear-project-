import os
import urllib.request
import tarfile
import json
import io

NODE_MODULES = os.path.join(os.path.dirname(__file__), 'node_modules')
os.makedirs(NODE_MODULES, exist_ok=True)

installed = set()

def install_pkg(pkg_name, version=None):
    if pkg_name in installed:
        return
    installed.add(pkg_name)
    
    print(f"Installing {pkg_name}...")
    try:
        url = f"https://registry.npmjs.org/{pkg_name}"
        req = urllib.request.Request(url, headers={'User-Agent': 'Mozilla/5.0'})
        with urllib.request.urlopen(req) as resp:
            meta = json.loads(resp.read().decode('utf-8'))
        
        if not version or version == 'latest' or version.startswith('^') or version.startswith('~'):
            version = meta['dist-tags']['latest']
        
        ver_info = meta['versions'].get(version)
        if not ver_info:
            version = meta['dist-tags']['latest']
            ver_info = meta['versions'][version]

        tarball_url = ver_info['dist']['tarball']
        print(f"  -> Downloading {tarball_url}...")
        
        req_tar = urllib.request.Request(tarball_url, headers={'User-Agent': 'Mozilla/5.0'})
        with urllib.request.urlopen(req_tar) as resp_tar:
            tar_bytes = resp_tar.read()
        
        # Determine install target path (handling scoped packages like @esbuild/win32-x64)
        target_dir = os.path.join(NODE_MODULES, *pkg_name.split('/'))
        os.makedirs(target_dir, exist_ok=True)
        
        with tarfile.open(fileobj=io.BytesIO(tar_bytes), mode='r:gz') as tar:
            for member in tar.getmembers():
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

        # Recursively install dependencies
        deps = ver_info.get('dependencies', {})
        for dep_name, dep_ver in deps.items():
            install_pkg(dep_name, dep_ver)

    except Exception as e:
        print(f"Warning/Error installing {pkg_name}: {e}")

if __name__ == '__main__':
    install_pkg('vite', '5.4.11')
    install_pkg('esbuild', '0.21.5')
    install_pkg('@esbuild/win32-x64', '0.21.5')
    print("Vite installation completed.")

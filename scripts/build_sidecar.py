import os
import sys
import subprocess
import shutil

def get_platform_name():
    if sys.platform == 'win32':
        return 'win'
    elif sys.platform == 'darwin':
        return 'mac'
    else:
        return 'linux'

def main():
    root_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    os.chdir(root_dir)

    print("Checking for PyInstaller...")
    try:
        import PyInstaller.__main__
    except ImportError:
        print("PyInstaller not found. Installing...")
        subprocess.check_call([sys.executable, "-m", "pip", "install", "pyinstaller"])
        import PyInstaller.__main__

    platform = get_platform_name()
    dist_path = os.path.join(root_dir, 'sidecar', 'bin', platform)
    
    print(f"Building sidecar for {platform} into {dist_path}...")
    
    # Run PyInstaller using the spec file
    spec_path = os.path.join('packaging', 'llm_kosh.spec')
    
    PyInstaller.__main__.run([
        spec_path,
        '--distpath', dist_path,
        '--workpath', os.path.join('build', 'sidecar'),
        '--noconfirm',
        '--clean'
    ])
    
    exe_name = 'llm-kosh.exe' if platform == 'win' else 'llm-kosh'
    exe_path = os.path.join(dist_path, exe_name)
    
    if os.path.exists(exe_path):
        print(f"\nSUCCESS: Built standalone executable at: {exe_path}")
    else:
        print("\nFAILURE: Executable not found after build.")
        sys.exit(1)

if __name__ == '__main__':
    main()

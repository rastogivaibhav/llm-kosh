import sys
from setuptools import setup
from setuptools.errors import CCompilerError, PlatformError

# Try to load Pybind11 setup helpers
try:
    from pybind11.setup_helpers import Pybind11Extension, build_ext
    ext_modules = [
        Pybind11Extension(
            "llm_kosh.engine.math_core",
            ["llm_kosh/engine/bindings.cpp"],
            cxx_std=11,
        ),
    ]
except ImportError:
    Pybind11Extension = None
    build_ext = None
    ext_modules = []

if build_ext:
    class SafeBuildExt(build_ext):
        def run(self):
            try:
                super().run()
            except (CCompilerError, PlatformError, Exception) as e:
                print("\n" + "="*80)
                print("WARNING: C++ math extension compilation failed. Falling back to pure Python implementation.")
                print(f"Reason: {e}")
                print("="*80 + "\n")
                # Clear extensions so setuptools continues packaging pure Python files only
                self.extensions.clear()

        def build_extension(self, ext):
            try:
                super().build_extension(ext)
            except (CCompilerError, PlatformError, Exception) as e:
                print(f"\nWARNING: Failed to build C++ extension {ext.name}. Falling back to pure Python.")
                print(f"Reason: {e}\n")
                raise
else:
    SafeBuildExt = object

setup(
    ext_modules=ext_modules,
    cmdclass={"build_ext": SafeBuildExt} if build_ext else {},
)

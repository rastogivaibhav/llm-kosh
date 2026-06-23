import os
from setuptools import setup
from setuptools.errors import CCompilerError, PlatformError

# Native math is an explicit opt-in so the default PyPI artifact stays a
# portable pure-Python wheel. The tested Python fallback is always available.
try:
    if os.environ.get("LLM_KOSH_BUILD_NATIVE") != "1":
        raise ImportError
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
        def build_extensions(self):
            if self.compiler.compiler_type == "mingw32":
                for ext in self.extensions:
                    # Strip MSVC-specific flags (flags starting with /)
                    new_args = []
                    for arg in ext.extra_compile_args:
                        if not arg.startswith('/') and not arg.startswith('-std:c++'):
                            new_args.append(arg)
                    # Add GCC-compatible standards flag
                    new_args.append("-std=c++14")
                    ext.extra_compile_args = new_args
                    
                    # Clean up link arguments as well
                    ext.extra_link_args = [arg for arg in ext.extra_link_args if not arg.startswith('/')]
            super().build_extensions()

        def run(self):
            try:
                super().run()
            except (CCompilerError, PlatformError, Exception) as e:
                print("\n" + "="*80)
                print("WARNING: C++ math extension compilation failed. Falling back to pure Python implementation.")
                print(f"Reason: {e}")
                print("="*80 + "\n")
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

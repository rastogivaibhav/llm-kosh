import importlib.util
import json
import sys
from pathlib import Path
from typing import List, Tuple, Optional, Type

class BaseVectorStorePlugin:
    """Base interface for overriding the vector store index backend."""
    def initialize(self, root: Path, dim: int, backend: str, model: str, idf: dict) -> None:
        pass

    def add_vectors(self, ids: List[str], kinds: List[str], statuses: List[str], 
                    vecs_sem: List[List[float]], vecs_proc: List[List[float]]) -> None:
        pass

    def search(self, query_vector_sem: List[float], query_vector_proc: List[float], k: int, 
               kinds: Optional[List[str]] = None, active_only: bool = False) -> List[Tuple[float, str]]:
        return []

class BaseContextCompilerPlugin:
    """Base interface for overriding the document context skeletonization."""
    def skeletonize(self, text: str, file_path: str, profile: str) -> str:
        return text

class PluginManager:
    @staticmethod
    def load_plugin_class(class_path: str):
        """Dynamically loads a class from a dotted path or a local .py file path."""
        class_path = class_path.strip()
        if class_path.endswith(".py"):
            p = Path(class_path).resolve()
            if not p.exists():
                raise FileNotFoundError(f"Plugin file not found: {p}")
            mod_name = f"custom_plugin_{p.stem}"
            spec = importlib.util.spec_from_file_location(mod_name, str(p))
            if spec and spec.loader:
                mod = importlib.util.module_from_spec(spec)
                sys.modules[mod_name] = mod
                spec.loader.exec_module(mod)
                for name, obj in vars(mod).items():
                    if isinstance(obj, type) and obj.__name__ not in ("BaseContextCompilerPlugin", "BaseVectorStorePlugin"):
                        # Check if matches plugin interface subclasses
                        if issubclass(obj, (BaseVectorStorePlugin, BaseContextCompilerPlugin)):
                            return obj
                raise ValueError(f"No suitable plugin class found in file: {p}")
        else:
            parts = class_path.split(".")
            if len(parts) < 2:
                raise ValueError(f"Invalid plugin dotted path: {class_path}")
            module_name = ".".join(parts[:-1])
            class_name = parts[-1]
            mod = importlib.import_module(module_name)
            return getattr(mod, class_name)

    @staticmethod
    def get_vector_store_plugin(root: Path) -> Optional[BaseVectorStorePlugin]:
        cfg_path = root / "LLM_KOSH.json"
        if not cfg_path.exists():
            return None
        try:
            with open(cfg_path, "r", encoding="utf-8") as f:
                cfg = json.load(f)
            plugin_path = cfg.get("plugins", {}).get("vector_store")
            if plugin_path:
                cls = PluginManager.load_plugin_class(plugin_path)
                return cls()
        except Exception:
            return None
        return None

    @staticmethod
    def get_context_compiler_plugin(root: Path) -> Optional[BaseContextCompilerPlugin]:
        cfg_path = root / "LLM_KOSH.json"
        if not cfg_path.exists():
            return None
        try:
            with open(cfg_path, "r", encoding="utf-8") as f:
                cfg = json.load(f)
            plugin_path = cfg.get("plugins", {}).get("context_compiler")
            if plugin_path:
                cls = PluginManager.load_plugin_class(plugin_path)
                return cls()
        except Exception:
            return None
        return None

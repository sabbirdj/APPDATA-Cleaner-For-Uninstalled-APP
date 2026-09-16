import os
import shutil
import stat
from typing import List, Dict, Any
from send2trash import send2trash

def _remove_readonly(func, path, excinfo):
    """Clear the readonly bit and reattempt removal on Windows."""
    try:
        os.chmod(path, stat.S_IWRITE)
        func(path)
    except Exception:
        pass

class CleanerEngine:
    @staticmethod
    def delete_items(items: List[Dict[str, Any]], use_recycle_bin: bool = True) -> Dict[str, Any]:
        """
        Deletes a list of AppData items.
        Each item is a dict with 'path', 'size', 'name'.
        
        Returns summary:
            {
                "success_count": int,
                "failed_count": int,
                "freed_bytes": int,
                "errors": List[str]
            }
        """
        success_count = 0
        failed_count = 0
        freed_bytes = 0
        errors = []

        for item in items:
            folder_path = item.get("path")
            folder_size = item.get("size", 0)
            folder_name = item.get("name", folder_path)

            if not folder_path or not os.path.exists(folder_path):
                continue

            try:
                if use_recycle_bin:
                    # Send to Windows Recycle Bin
                    send2trash(folder_path)
                else:
                    # Permanent deletion
                    shutil.rmtree(folder_path, onerror=_remove_readonly)

                success_count += 1
                freed_bytes += folder_size
            except Exception as e:
                failed_count += 1
                errors.append(f"Failed to delete {folder_name}: {str(e)}")

        return {
            "success_count": success_count,
            "failed_count": failed_count,
            "freed_bytes": freed_bytes,
            "errors": errors
        }

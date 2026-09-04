import os
import subprocess
from typing import Optional, Dict, Any, List

class GitService:
    @staticmethod
    def get_git_info(source_path: str) -> Dict[str, Any]:
        """
        Extrae información detallada de Git desde un directorio fuente.
        Soporta repositorios estándar y worktrees.
        Solo operaciones de LECTURA (Read-Only).
        """
        info = {
            "is_git_repo": False,
            "branch": "main",
            "commit_hash": "",
            "short_hash": "",
            "commit_message": "",
            "commit_date": "",
            "is_dirty": False,
            "worktree": False
        }

        if not source_path or not os.path.exists(source_path):
            return info

        git_path = os.path.join(source_path, ".git")
        if not os.path.exists(git_path):
            return info

        info["is_git_repo"] = True
        if os.path.isfile(git_path):
            # Es un git worktree apuntando a un gitdir
            info["worktree"] = True

        # 1. Intentar con comandos Git si git está disponible
        try:
            # Rama actual
            cmd_branch = subprocess.run(
                ["git", "-c", "safe.directory=*", "-C", source_path, "rev-parse", "--abbrev-ref", "HEAD"],
                capture_output=True, text=True, check=True, timeout=5
            )
            branch = cmd_branch.stdout.strip()
            if branch and branch != "HEAD":
                info["branch"] = branch
            else:
                # Detached HEAD - intentar obtener tag o hash
                cmd_tag = subprocess.run(
                    ["git", "-c", "safe.directory=*", "-C", source_path, "describe", "--tags", "--exact-match"],
                    capture_output=True, text=True, timeout=3
                )
                if cmd_tag.returncode == 0 and cmd_tag.stdout.strip():
                    info["branch"] = f"tag:{cmd_tag.stdout.strip()}"
                else:
                    info["branch"] = "detached"

            # Commit Hash completo
            cmd_hash = subprocess.run(
                ["git", "-c", "safe.directory=*", "-C", source_path, "rev-parse", "HEAD"],
                capture_output=True, text=True, check=True, timeout=5
            )
            info["commit_hash"] = cmd_hash.stdout.strip()
            info["short_hash"] = info["commit_hash"][:8] if info["commit_hash"] else ""

            # Mensaje y fecha del commit
            cmd_log = subprocess.run(
                ["git", "-c", "safe.directory=*", "-C", source_path, "log", "-1", "--format=%s||%cd", "--date=iso"],
                capture_output=True, text=True, timeout=5
            )
            if cmd_log.returncode == 0 and cmd_log.stdout.strip():
                parts = cmd_log.stdout.strip().split("||", 1)
                info["commit_message"] = parts[0]
                if len(parts) > 1:
                    info["commit_date"] = parts[1]

            # Estado sucio (archivos sin commitear)
            cmd_status = subprocess.run(
                ["git", "-c", "safe.directory=*", "-C", source_path, "status", "--porcelain"],
                capture_output=True, text=True, timeout=5
            )
            info["is_dirty"] = bool(cmd_status.stdout.strip())

            return info

        except Exception as e:
            # 2. Fallback de lectura directa de archivos en .git
            try:
                actual_git_dir = git_path
                if os.path.isfile(git_path):
                    with open(git_path, "r", encoding="utf-8") as f:
                        line = f.read().strip()
                        if line.startswith("gitdir:"):
                            actual_git_dir = line.split(":", 1)[1].strip()
                            if not os.path.isabs(actual_git_dir):
                                actual_git_dir = os.path.normpath(os.path.join(source_path, actual_git_dir))

                head_file = os.path.join(actual_git_dir, "HEAD")
                if os.path.exists(head_file):
                    with open(head_file, "r", encoding="utf-8") as f:
                        head_content = f.read().strip()

                    if head_content.startswith("ref: refs/heads/"):
                        info["branch"] = head_content.replace("ref: refs/heads/", "").strip()
                        ref_file = os.path.join(actual_git_dir, "refs", "heads", info["branch"])
                        if os.path.exists(ref_file):
                            with open(ref_file, "r", encoding="utf-8") as rf:
                                info["commit_hash"] = rf.read().strip()
                                info["short_hash"] = info["commit_hash"][:8]
                    else:
                        info["commit_hash"] = head_content
                        info["short_hash"] = head_content[:8]
                        info["branch"] = "detached"
            except Exception:
                pass

        return info

    @staticmethod
    def get_local_branches(source_path: str) -> List[Dict[str, Any]]:
        """
        Retorna la lista de todas las ramas locales existentes en el repositorio local.
        Solo operaciones de LECTURA (Read-Only).
        """
        if not source_path or not os.path.exists(source_path):
            return []

        git_path = os.path.join(source_path, ".git")
        if not os.path.exists(git_path):
            return []

        branches = []
        try:
            cmd = subprocess.run(
                [
                    "git", "-c", "safe.directory=*", "-C", source_path,
                    "for-each-ref",
                    "--format=%(refname:short)|||%(objectname)|||%(objectname:short)|||%(subject)|||%(committerdate:iso)",
                    "refs/heads/"
                ],
                capture_output=True, text=True, timeout=5
            )
            if cmd.returncode == 0 and cmd.stdout.strip():
                for line in cmd.stdout.splitlines():
                    if not line.strip():
                        continue
                    parts = line.split("|||")
                    b_name = parts[0].strip()
                    c_hash = parts[1].strip() if len(parts) > 1 else ""
                    s_hash = parts[2].strip() if len(parts) > 2 else c_hash[:8]
                    c_msg = parts[3].strip() if len(parts) > 3 else ""
                    c_date = parts[4].strip() if len(parts) > 4 else ""
                    
                    branches.append({
                        "branch": b_name,
                        "commit_hash": c_hash,
                        "short_hash": s_hash,
                        "commit_message": c_msg,
                        "commit_date": c_date
                    })
                return branches
        except Exception as e:
            print(f"Error executing git for-each-ref on {source_path}: {e}")

        # Fallback si git command falla: inspeccionar .git/refs/heads/
        try:
            actual_git_dir = git_path
            if os.path.isfile(git_path):
                with open(git_path, "r", encoding="utf-8") as f:
                    line = f.read().strip()
                    if line.startswith("gitdir:"):
                        actual_git_dir = line.split(":", 1)[1].strip()
                        if not os.path.isabs(actual_git_dir):
                            actual_git_dir = os.path.normpath(os.path.join(source_path, actual_git_dir))

            heads_dir = os.path.join(actual_git_dir, "refs", "heads")
            if os.path.exists(heads_dir):
                for root, _, files in os.walk(heads_dir):
                    for f in files:
                        full_ref = os.path.join(root, f)
                        rel_b = os.path.relpath(full_ref, heads_dir).replace("\\", "/")
                        c_hash = ""
                        try:
                            with open(full_ref, "r", encoding="utf-8") as rf:
                                c_hash = rf.read().strip()
                        except Exception:
                            pass
                        branches.append({
                            "branch": rel_b,
                            "commit_hash": c_hash,
                            "short_hash": c_hash[:8],
                            "commit_message": "",
                            "commit_date": ""
                        })
        except Exception:
            pass

        return branches

    @staticmethod
    def get_diff_files(source_path: str, from_commit: str, to_commit: str = "HEAD") -> List[str]:
        """
        Retorna la lista de rutas relativas de archivos modificados, agregados o eliminados entre dos commits.
        Solo operaciones de LECTURA estrictas (Read-Only).
        """
        if not source_path or not from_commit or not os.path.exists(source_path):
            return []

        # Sanitización estricta: solo permitir caracteres seguros de commit hashes / refs
        safe_from = "".join(c for c in from_commit if c.isalnum() or c in ("-", "_", "~", "^", "."))
        safe_to = "".join(c for c in to_commit if c.isalnum() or c in ("-", "_", "~", "^", "."))

        if not safe_from or not safe_to or safe_from.startswith("-") or safe_to.startswith("-"):
            return []

        try:
            cmd = subprocess.run(
                ["git", "-c", "safe.directory=*", "-C", source_path, "diff", "--name-only", "--", safe_from, safe_to],
                capture_output=True, text=True, check=True, timeout=10
            )
            lines = [line.strip() for line in cmd.stdout.splitlines() if line.strip()]
            return lines
        except Exception as e:
            print(f"Error getting git diff between {safe_from} and {safe_to}: {e}")
            return []

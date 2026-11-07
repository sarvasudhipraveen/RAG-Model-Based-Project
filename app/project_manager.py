import json
import uuid
import shutil
from datetime import datetime
from typing import List, Dict, Any, Optional
from pathlib import Path
from app.config import PROJECTS_FILE, PROJECTS_DIR, BASE_DIR, DATA_DIR

class ProjectManager:
    def __init__(self):
        self._ensure_storage()

    def _ensure_storage(self):
        PROJECTS_DIR.mkdir(parents=True, exist_ok=True)
        if not PROJECTS_FILE.exists():
            self._save_projects_index([])

    def _load_projects_index(self) -> List[Dict[str, Any]]:
        try:
            if PROJECTS_FILE.exists():
                with open(PROJECTS_FILE, "r", encoding="utf-8") as f:
                    return json.load(f)
        except Exception as e:
            print(f"Error loading {PROJECTS_FILE}: {e}")
        return []

    def _save_projects_index(self, projects: List[Dict[str, Any]]):
        with open(PROJECTS_FILE, "w", encoding="utf-8") as f:
            json.dump(projects, f, indent=2, ensure_ascii=False)

    def _get_project_dir(self, project_id: str) -> Path:
        pdir = PROJECTS_DIR / project_id
        pdir.mkdir(parents=True, exist_ok=True)
        return pdir

    def _get_project_chunks_file(self, project_id: str) -> Path:
        return self._get_project_dir(project_id) / "chunks.json"

    def _get_project_meta_file(self, project_id: str) -> Path:
        return self._get_project_dir(project_id) / "meta.json"

    def list_projects(self) -> List[Dict[str, Any]]:
        return self._load_projects_index()

    def get_project(self, project_id: str) -> Optional[Dict[str, Any]]:
        meta_file = self._get_project_meta_file(project_id)
        if meta_file.exists():
            try:
                with open(meta_file, "r", encoding="utf-8") as f:
                    return json.load(f)
            except Exception as e:
                print(f"Error reading project meta for {project_id}: {e}")
        
        # Fallback to index
        for p in self._load_projects_index():
            if p["id"] == project_id:
                return p
        return None

    def create_project(self, name: str, description: str = "") -> Dict[str, Any]:
        project_id = f"proj_{uuid.uuid4().hex[:8]}"
        now = datetime.now().isoformat()
        
        project_data = {
            "id": project_id,
            "name": name.strip(),
            "description": description.strip(),
            "created_at": now,
            "updated_at": now,
            "documents": [],
            "total_chunks": 0,
            "total_pages": 0,
            "chat_history": []
        }

        # Save project folder meta
        meta_file = self._get_project_meta_file(project_id)
        with open(meta_file, "w", encoding="utf-8") as f:
            json.dump(project_data, f, indent=2, ensure_ascii=False)

        # Save empty chunks
        chunks_file = self._get_project_chunks_file(project_id)
        with open(chunks_file, "w", encoding="utf-8") as f:
            json.dump([], f)

        # Update global list
        projects = self._load_projects_index()
        summary = {
            "id": project_id,
            "name": project_data["name"],
            "description": project_data["description"],
            "created_at": now,
            "updated_at": now,
            "document_count": 0,
            "total_chunks": 0
        }
        projects.insert(0, summary)
        self._save_projects_index(projects)

        return project_data

    def delete_project(self, project_id: str) -> bool:
        pdir = PROJECTS_DIR / project_id
        if pdir.exists():
            shutil.rmtree(pdir, ignore_errors=True)

        projects = self._load_projects_index()
        projects = [p for p in projects if p["id"] != project_id]
        self._save_projects_index(projects)
        return True

    def get_project_chunks(self, project_id: str) -> List[Dict[str, Any]]:
        chunks_file = self._get_project_chunks_file(project_id)
        if chunks_file.exists():
            try:
                with open(chunks_file, "r", encoding="utf-8") as f:
                    return json.load(f)
            except Exception as e:
                print(f"Error loading chunks for {project_id}: {e}")
        return []

    def save_project_chunks(self, project_id: str, new_chunks: List[Dict[str, Any]], append: bool = True):
        chunks_file = self._get_project_chunks_file(project_id)
        existing = self.get_project_chunks(project_id) if append else []
        combined = existing + new_chunks

        with open(chunks_file, "w", encoding="utf-8") as f:
            json.dump(combined, f, ensure_ascii=False)

        # Update metadata counts
        project = self.get_project(project_id)
        if project:
            project["total_chunks"] = len(combined)
            project["updated_at"] = datetime.now().isoformat()
            self._save_project_meta(project)

    def add_document_to_project(self, project_id: str, doc_info: Dict[str, Any]):
        project = self.get_project(project_id)
        if not project:
            raise ValueError(f"Project {project_id} not found")

        project["documents"].append(doc_info)
        project["total_pages"] = sum(d.get("total_pages", 0) for d in project["documents"])
        project["updated_at"] = datetime.now().isoformat()
        self._save_project_meta(project)

    def remove_document_from_project(self, project_id: str, doc_id: str) -> bool:
        project = self.get_project(project_id)
        if not project:
            return False

        # Find document and keep remaining
        doc_to_remove = None
        remaining_docs = []
        for d in project.get("documents", []):
            if d.get("doc_id") == doc_id:
                doc_to_remove = d
            else:
                remaining_docs.append(d)

        if not doc_to_remove:
            return False

        # 1. Delete physical PDF file from documents directory if it exists
        proj_docs_dir = DATA_DIR / "projects" / project_id / "documents"
        if proj_docs_dir.exists():
            for f in proj_docs_dir.glob(f"{doc_id}_*"):
                try:
                    f.unlink()
                except Exception as e:
                    print(f"Error removing document file {f}: {e}")

        # 2. Filter out chunks matching this doc_id
        chunks = self.get_project_chunks(project_id)
        remaining_chunks = [c for c in chunks if c.get("doc_id") != doc_id]
        chunks_file = self._get_project_chunks_file(project_id)
        try:
            with open(chunks_file, "w", encoding="utf-8") as f:
                json.dump(remaining_chunks, f, ensure_ascii=False)
        except Exception as e:
            print(f"Error saving updated chunks for {project_id}: {e}")

        # 3. Update project metadata, reset chat history, and persist
        project["documents"] = remaining_docs
        project["total_chunks"] = len(remaining_chunks)
        project["total_pages"] = sum(d.get("total_pages", 0) for d in remaining_docs)
        project["chat_history"] = []
        project["updated_at"] = datetime.now().isoformat()
        self._save_project_meta(project)
        return True

    def _save_project_meta(self, project: Dict[str, Any]):
        project_id = project["id"]
        meta_file = self._get_project_meta_file(project_id)
        with open(meta_file, "w", encoding="utf-8") as f:
            json.dump(project, f, indent=2, ensure_ascii=False)

        # Update global list
        projects = self._load_projects_index()
        for p in projects:
            if p["id"] == project_id:
                p["name"] = project["name"]
                p["description"] = project["description"]
                p["updated_at"] = project["updated_at"]
                p["document_count"] = len(project.get("documents", []))
                p["total_chunks"] = project.get("total_chunks", 0)
                break
        self._save_projects_index(projects)

    def append_chat(
        self, 
        project_id: str, 
        user_message: str, 
        assistant_message: str, 
        citations: List[Dict[str, Any]], 
        provider: str, 
        model: str
    ):
        project = self.get_project(project_id)
        if not project:
            return

        now = datetime.now().isoformat()
        entry = {
            "id": f"msg_{uuid.uuid4().hex[:6]}",
            "timestamp": now,
            "user": user_message,
            "assistant": assistant_message,
            "citations": citations,
            "provider": provider,
            "model": model
        }

        if "chat_history" not in project:
            project["chat_history"] = []

        project["chat_history"].append(entry)
        project["updated_at"] = now
        self._save_project_meta(project)

    def clear_chat(self, project_id: str):
        project = self.get_project(project_id)
        if project:
            project["chat_history"] = []
            self._save_project_meta(project)

    def delete_chat_message(self, project_id: str, message_id: str) -> bool:
        project = self.get_project(project_id)
        if not project or "chat_history" not in project:
            return False

        orig_len = len(project["chat_history"])
        project["chat_history"] = [m for m in project["chat_history"] if m.get("id") != message_id]
        if len(project["chat_history"]) != orig_len:
            project["updated_at"] = datetime.now().isoformat()
            self._save_project_meta(project)
            return True
        return False

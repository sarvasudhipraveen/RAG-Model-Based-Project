import os
import shutil
import uuid
from pathlib import Path
from typing import Optional, List
from fastapi import FastAPI, UploadFile, File, Form, HTTPException, BackgroundTasks
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse, JSONResponse
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

from app.config import BASE_DIR, DATA_DIR, PROVIDERS, DEFAULT_CHUNK_SIZE, DEFAULT_CHUNK_OVERLAP, DEFAULT_TOP_K
from app.project_manager import ProjectManager
from app.pdf_processor import PDFProcessor
from app.rag_engine import HybridRAGEngine
from app.llm_service import LLMService

app = FastAPI(title="PDF RAG Project Studio", version="1.0.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Services
project_mgr = ProjectManager()
rag_engine = HybridRAGEngine()
llm_service = LLMService()

# In-memory index cache: {project_id: built_index_dict}
INDEX_CACHE = {}

def get_or_build_index(project_id: str):
    if project_id in INDEX_CACHE:
        return INDEX_CACHE[project_id]
    chunks = project_mgr.get_project_chunks(project_id)
    idx = rag_engine.build_index(chunks)
    INDEX_CACHE[project_id] = idx
    return idx

def invalidate_index_cache(project_id: str):
    if project_id in INDEX_CACHE:
        del INDEX_CACHE[project_id]

# Models
class CreateProjectRequest(BaseModel):
    name: str
    description: Optional[str] = ""

class QueryRequest(BaseModel):
    query: str
    top_k: Optional[int] = DEFAULT_TOP_K
    provider: Optional[str] = "gemini"
    model: Optional[str] = None
    api_key: Optional[str] = None

class QuickAttachRequest(BaseModel):
    filename: str
    start_page: Optional[int] = 1
    end_page: Optional[int] = 50
    chunk_size: Optional[int] = DEFAULT_CHUNK_SIZE
    chunk_overlap: Optional[int] = DEFAULT_CHUNK_OVERLAP

# Endpoints
@app.get("/api/config/providers")
def get_providers():
    return {
        "providers": PROVIDERS,
        "default_provider": "gemini"
    }

@app.get("/api/workspace_files")
def list_workspace_files():
    """List any PDF files located in workspace root."""
    pdfs = []
    for f in BASE_DIR.glob("*.pdf"):
        pdfs.append({
            "filename": f.name,
            "size_bytes": f.stat().st_size,
            "size_mb": round(f.stat().st_size / (1024 * 1024), 2)
        })
    return {"workspace_pdfs": pdfs}

@app.get("/api/projects")
def list_projects():
    return project_mgr.list_projects()

@app.post("/api/projects")
def create_project(req: CreateProjectRequest):
    if not req.name.strip():
        raise HTTPException(status_code=400, detail="Project name cannot be empty")
    return project_mgr.create_project(req.name, req.description or "")

@app.get("/api/projects/{project_id}")
def get_project(project_id: str):
    proj = project_mgr.get_project(project_id)
    if not proj:
        raise HTTPException(status_code=404, detail="Project not found")
    return proj

@app.delete("/api/projects/{project_id}")
def delete_project(project_id: str):
    invalidate_index_cache(project_id)
    success = project_mgr.delete_project(project_id)
    return {"success": success}

@app.post("/api/projects/{project_id}/upload")
async def upload_pdf(
    project_id: str,
    file: UploadFile = File(...),
    start_page: int = Form(1),
    end_page: Optional[int] = Form(None),
    chunk_size: int = Form(DEFAULT_CHUNK_SIZE),
    chunk_overlap: int = Form(DEFAULT_CHUNK_OVERLAP),
):
    project = project_mgr.get_project(project_id)
    if not project:
        raise HTTPException(status_code=404, detail="Project not found")

    if not file.filename.lower().endswith(".pdf"):
        raise HTTPException(status_code=400, detail="Uploaded file must be a PDF")

    # Save uploaded file inside project's documents directory
    proj_dir = DATA_DIR / "projects" / project_id / "documents"
    proj_dir.mkdir(parents=True, exist_ok=True)
    
    doc_id = f"doc_{uuid.uuid4().hex[:6]}"
    saved_path = proj_dir / f"{doc_id}_{file.filename}"
    
    with open(saved_path, "wb") as buffer:
        shutil.copyfileobj(file.file, buffer)

    # Process PDF
    processor = PDFProcessor(chunk_size=chunk_size, chunk_overlap=chunk_overlap)
    pdf_info = processor.get_pdf_info(saved_path)
    total_pages = pdf_info["total_pages"]

    # Extract pages
    extracted_pages = processor.extract_pages(
        saved_path, 
        start_page=start_page, 
        end_page=end_page if (end_page and end_page > 0) else total_pages
    )
    
    # Chunk text
    chunks = processor.chunk_text(extracted_pages, filename=file.filename, doc_id=doc_id)

    # Save chunks & update metadata
    project_mgr.save_project_chunks(project_id, chunks, append=True)
    doc_info = {
        "doc_id": doc_id,
        "filename": file.filename,
        "file_size": saved_path.stat().st_size,
        "total_pages": total_pages,
        "indexed_start_page": start_page,
        "indexed_end_page": end_page if (end_page and end_page > 0) else total_pages,
        "chunk_count": len(chunks),
        "chunk_size": chunk_size,
        "chunk_overlap": chunk_overlap
    }
    project_mgr.add_document_to_project(project_id, doc_info)
    invalidate_index_cache(project_id)

    return {
        "success": True,
        "doc_info": doc_info,
        "chunks_created": len(chunks),
        "total_chunks": project_mgr.get_project(project_id)["total_chunks"]
    }

@app.post("/api/projects/{project_id}/quick_attach_local")
def quick_attach_local(project_id: str, req: QuickAttachRequest):
    project = project_mgr.get_project(project_id)
    if not project:
        raise HTTPException(status_code=404, detail="Project not found")

    target_file = BASE_DIR / req.filename
    if not target_file.exists():
        raise HTTPException(status_code=404, detail=f"File {req.filename} not found in workspace")

    # Copy to project documents folder
    proj_dir = DATA_DIR / "projects" / project_id / "documents"
    proj_dir.mkdir(parents=True, exist_ok=True)
    doc_id = f"doc_{uuid.uuid4().hex[:6]}"
    saved_path = proj_dir / f"{doc_id}_{req.filename}"
    shutil.copy2(target_file, saved_path)

    # Process PDF
    processor = PDFProcessor(chunk_size=req.chunk_size, chunk_overlap=req.chunk_overlap)
    pdf_info = processor.get_pdf_info(saved_path)
    total_pages = pdf_info["total_pages"]

    extracted_pages = processor.extract_pages(
        saved_path, 
        start_page=req.start_page, 
        end_page=req.end_page if (req.end_page and req.end_page > 0) else total_pages
    )
    chunks = processor.chunk_text(extracted_pages, filename=req.filename, doc_id=doc_id)

    project_mgr.save_project_chunks(project_id, chunks, append=True)
    doc_info = {
        "doc_id": doc_id,
        "filename": req.filename,
        "file_size": saved_path.stat().st_size,
        "total_pages": total_pages,
        "indexed_start_page": req.start_page,
        "indexed_end_page": req.end_page if (req.end_page and req.end_page > 0) else total_pages,
        "chunk_count": len(chunks),
        "chunk_size": req.chunk_size,
        "chunk_overlap": req.chunk_overlap
    }
    project_mgr.add_document_to_project(project_id, doc_info)
    invalidate_index_cache(project_id)

    return {
        "success": True,
        "doc_info": doc_info,
        "chunks_created": len(chunks),
        "total_chunks": project_mgr.get_project(project_id)["total_chunks"]
    }

@app.delete("/api/projects/{project_id}/documents/{doc_id}")
def delete_document(project_id: str, doc_id: str):
    success = project_mgr.remove_document_from_project(project_id, doc_id)
    if not success:
        raise HTTPException(status_code=404, detail="Document not found or could not be removed")
    invalidate_index_cache(project_id)
    return {
        "success": True,
        "project": project_mgr.get_project(project_id)
    }

@app.get("/api/projects/{project_id}/chunks")
def list_chunks(project_id: str, search: Optional[str] = None, limit: int = 50):
    chunks = project_mgr.get_project_chunks(project_id)
    if search:
        search_lower = search.lower()
        chunks = [c for c in chunks if search_lower in c.get("text", "").lower()]
    return {
        "total_matching": len(chunks),
        "chunks": chunks[:limit]
    }

@app.post("/api/projects/{project_id}/query")
async def query_project(project_id: str, req: QueryRequest):
    project = project_mgr.get_project(project_id)
    if not project:
        raise HTTPException(status_code=404, detail="Project not found")

    if not req.query.strip():
        raise HTTPException(status_code=400, detail="Query cannot be empty")

    # Get index and search
    index = get_or_build_index(project_id)
    top_chunks = rag_engine.search(req.query, index, top_k=req.top_k or DEFAULT_TOP_K)

    # Generate response
    response_data = await llm_service.generate_response(
        query=req.query,
        retrieved_chunks=top_chunks,
        provider=req.provider or "offline",
        model=req.model,
        api_key=req.api_key,
        chat_history=project.get("chat_history", [])
    )

    # Save in chat history
    project_mgr.append_chat(
        project_id=project_id,
        user_message=req.query,
        assistant_message=response_data["answer"],
        citations=top_chunks,
        provider=response_data.get("provider", req.provider),
        model=response_data.get("model", req.model or "default")
    )

    return {
        "answer": response_data["answer"],
        "citations": top_chunks,
        "provider": response_data.get("provider"),
        "model": response_data.get("model"),
        "notice": response_data.get("notice")
    }

@app.post("/api/projects/{project_id}/clear_chat")
def clear_chat(project_id: str):
    project_mgr.clear_chat(project_id)
    return {"success": True}

@app.delete("/api/projects/{project_id}/chat/{message_id}")
def delete_chat_message(project_id: str, message_id: str):
    success = project_mgr.delete_chat_message(project_id, message_id)
    if not success:
        raise HTTPException(status_code=404, detail="Message not found")
    return {"success": True}

# Serve static frontend files
static_dir = Path(__file__).resolve().parent / "static"
app.mount("/static", StaticFiles(directory=str(static_dir)), name="static")

@app.get("/")
@app.get("/index.html")
def serve_index():
    index_file = static_dir / "index.html"
    return FileResponse(str(index_file))

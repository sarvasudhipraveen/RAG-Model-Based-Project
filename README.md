# 🚀 DocuRAG Studio: Intelligent PDF RAG Project Application

A full-stack, production-grade Retrieval-Augmented Generation (RAG) web application with multi-project management, drag-and-drop PDF ingestion, hybrid retrieval, and grounded AI chat with inline citations.

---

## 🌐 Live Local Server

The application is actively running on your machine:
- **Local URL:** [http://localhost:8000](http://localhost:8000) or [http://127.0.0.1:8000](http://127.0.0.1:8000)

To start or restart anytime:
```bash
python run.py
```

---

## ✨ Features

1. **📁 Multi-Project Architecture**:
   - Create separate project workspaces for different PDFs or research topics.
   - Switch between projects with a click in the header dropdown.
   - Each project maintains its own isolated documents, indexed chunk vectors, and conversation history.

2. **📄 PDF Ingestion & Indexing**:
   - Drag-and-drop any `.pdf` file to upload.
   - **Workspace Quick-Attach**: 1-click attach existing local PDFs like [`Human-Nutrition-2020-Edition-1598491699.pdf`](file:///d:/pe%20lab/Human-Nutrition-2020-Edition-1598491699.pdf).
   - Configurable page range indexing (e.g., pages 1–50 for rapid exploration or custom ranges).

3. **🔍 Hybrid RAG Retrieval Engine**:
   - Paragraph-aware chunking preserving exact page numbers and context offsets.
   - BM25 lexical ranking combined with term-frequency scoring and n-gram boosting.
   - Returns top-k passages with relevance confidence scores and matching excerpts.

4. **🤖 Multi-Provider LLM Generation**:
   - **Google Gemini**: Powered by `gemini-3.5-flash-lite` (pre-configured with your API key in [`.env`](file:///d:/pe%20lab/.env)).
   - **Groq**: Ultra-fast Llama 3.3 70B & Llama 3.1 8B.
   - **OpenAI**: GPT-4o & GPT-4o-mini.
   - **Built-in Offline Engine**: Zero API key required, extractive QA synthesis with citations.

5. **🔖 Interactive Source Citations**:
   - Every answer displays clickable verified source cards with page badges (e.g., `Page 28`) and match percentages.
   - Click any citation to view the exact text passage in the source inspector modal.
   - **Chunks Explorer**: Browse and search all indexed text chunks across the project.

---

## 🛠 Project Structure

```
d:\pe lab\
├── app\
│   ├── config.py             # Config & API keys
│   ├── main.py               # FastAPI backend & API endpoints
│   ├── pdf_processor.py      # PDF text extractor & chunker
│   ├── rag_engine.py         # BM25 & Hybrid ranking engine
│   ├── llm_service.py        # Gemini, Groq, OpenAI & offline handlers
│   ├── project_manager.py    # Persistent project management
│   └── static\
│       ├── index.html        # Modern Glassmorphic UI
│       ├── css\style.css     # Premium dark theme stylesheet
│       └── js\app.js         # Reactive client-side logic
├── data\                     # Project metadata & chunk store
├── Human-Nutrition-2020-Edition-1598491699.pdf
├── .env                      # Gemini API Key configuration
├── requirements.txt          # Python dependencies
└── run.py                    # Server launcher
```

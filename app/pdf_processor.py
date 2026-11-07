import re
import uuid
from typing import List, Dict, Any, Optional
from pathlib import Path
import pypdf

class PDFProcessor:
    def __init__(self, chunk_size: int = 800, chunk_overlap: int = 150):
        self.chunk_size = chunk_size
        self.chunk_overlap = chunk_overlap

    def get_pdf_info(self, file_path: Path) -> Dict[str, Any]:
        """Read basic PDF metadata and page count quickly."""
        reader = pypdf.PdfReader(str(file_path))
        num_pages = len(reader.pages)
        return {
            "filename": file_path.name,
            "total_pages": num_pages,
            "size_bytes": file_path.stat().st_size,
        }

    def extract_pages(
        self, 
        file_path: Path, 
        start_page: int = 1, 
        end_page: Optional[int] = None
    ) -> List[Dict[str, Any]]:
        """
        Extract text from PDF pages (1-indexed).
        Returns a list of dicts: [{"page_number": int, "text": str}]
        """
        reader = pypdf.PdfReader(str(file_path))
        total = len(reader.pages)
        
        start_idx = max(0, start_page - 1)
        end_idx = min(total, end_page) if end_page else total

        extracted = []
        for i in range(start_idx, end_idx):
            page_num = i + 1
            try:
                page_text = reader.pages[i].extract_text() or ""
                # Normalize whitespace
                cleaned_text = re.sub(r'[ \t]+', ' ', page_text)
                cleaned_text = re.sub(r'\n{3,}', '\n\n', cleaned_text).strip()
                if cleaned_text:
                    extracted.append({
                        "page_number": page_num,
                        "text": cleaned_text
                    })
            except Exception as e:
                print(f"Error reading page {page_num} of {file_path.name}: {e}")
        return extracted

    def chunk_text(
        self, 
        extracted_pages: List[Dict[str, Any]], 
        filename: str, 
        doc_id: str
    ) -> List[Dict[str, Any]]:
        """
        Split page texts into overlapping chunks with sentence awareness.
        Preserves page number and exact context.
        """
        chunks = []
        global_chunk_idx = 0

        for page in extracted_pages:
            page_num = page["page_number"]
            page_text = page["text"]
            if not page_text:
                continue

            # Paragraph/sentence splitting strategy
            text_len = len(page_text)
            start = 0

            while start < text_len:
                end = start + self.chunk_size

                if end < text_len:
                    # Look for paragraph boundary near end
                    boundary = page_text.rfind("\n\n", start + self.chunk_size // 2, end)
                    if boundary == -1:
                        # Look for sentence boundary
                        boundary = max(
                            page_text.rfind(". ", start + self.chunk_size // 2, end),
                            page_text.rfind(".\n", start + self.chunk_size // 2, end),
                            page_text.rfind("? ", start + self.chunk_size // 2, end),
                            page_text.rfind("! ", start + self.chunk_size // 2, end),
                        )
                    if boundary != -1:
                        end = boundary + 1

                chunk_text = page_text[start:end].strip()

                if len(chunk_text) >= 50:  # Skip tiny fragments
                    chunk_id = f"{doc_id}_p{page_num}_c{global_chunk_idx}"
                    chunks.append({
                        "id": chunk_id,
                        "doc_id": doc_id,
                        "filename": filename,
                        "page_number": page_num,
                        "chunk_index": global_chunk_idx,
                        "char_start": start,
                        "char_end": end,
                        "text": chunk_text
                    })
                    global_chunk_idx += 1

                # Advance with overlap
                start = max(start + 1, end - self.chunk_overlap)
                if end >= text_len:
                    break

        return chunks

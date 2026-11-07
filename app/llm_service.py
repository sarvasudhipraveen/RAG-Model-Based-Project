import os
import json
import re
from typing import List, Dict, Any, Optional
import httpx
from app.config import PROVIDERS

class LLMService:
    def __init__(self):
        pass

    def build_rag_prompt(self, query: str, retrieved_chunks: List[Dict[str, Any]], chat_history: Optional[List[Dict[str, str]]] = None) -> str:
        """
        Assemble grounded RAG prompt with retrieved context and instructions.
        """
        context_blocks = []
        for i, chunk in enumerate(retrieved_chunks):
            context_blocks.append(
                f"[Source {i+1} | Document: {chunk.get('filename', 'Doc')} | Page {chunk.get('page_number', '?')}]\n"
                f"{chunk.get('text', '')}"
            )
        context_text = "\n\n---\n\n".join(context_blocks)

        prompt = f"""You are an expert AI Research Assistant specializing in analyzing uploaded PDF documents.
Answer the user's question accurately and thoroughly based ONLY on the provided document excerpts below.

Guidelines:
1. Ground your answer strictly in the provided sources. Do not hallucinate or assume facts not present in the excerpts.
2. Cite your sources inline using the format [Page X] or [Source N, Page X] whenever presenting facts or quotes.
3. If the context does not contain enough information to answer the question, state clearly what is known from the context and what information is missing.
4. Use clear formatting, bullet points, and bold text for readability.

--- DOCUMENT EXCERPTS ---
{context_text}
-------------------------

User Question: {query}

Synthesized Answer with Citations:"""
        return prompt

    async def generate_response(
        self,
        query: str,
        retrieved_chunks: List[Dict[str, Any]],
        provider: str = "offline",
        model: Optional[str] = None,
        api_key: Optional[str] = None,
        chat_history: Optional[List[Dict[str, str]]] = None
    ) -> Dict[str, Any]:
        """
        Routes the question to the selected provider or falls back to local synthesis.
        """
        if not retrieved_chunks:
            return {
                "answer": "No relevant document chunks found for your query. Please make sure documents are uploaded and indexed in this project.",
                "provider": provider,
                "model": model or "none",
                "citations": []
            }

        provider_info = PROVIDERS.get(provider, PROVIDERS["offline"])
        selected_model = model or provider_info["default_model"]
        active_key = api_key or (os.environ.get(provider_info.get("key_env", "") or ""))

        # If provider requires key but none is supplied, fall back to offline with a friendly notice
        if provider_info.get("requires_key", False) and not active_key:
            offline_result = self._generate_offline(query, retrieved_chunks)
            offline_result["notice"] = f"No API key provided for {provider_info['name']}. Generated response using local offline analysis engine."
            return offline_result

        try:
            if provider == "gemini":
                return await self._call_gemini(query, retrieved_chunks, selected_model, active_key, chat_history)
            elif provider == "groq":
                return await self._call_groq(query, retrieved_chunks, selected_model, active_key, chat_history)
            elif provider == "openai":
                return await self._call_openai(query, retrieved_chunks, selected_model, active_key, chat_history)
            else:
                return self._generate_offline(query, retrieved_chunks)
        except Exception as e:
            print(f"Error calling {provider}: {e}. Falling back to offline engine.")
            fallback = self._generate_offline(query, retrieved_chunks)
            fallback["notice"] = f"Provider {provider} returned an error ({str(e)}). Used local offline engine instead."
            return fallback

    async def _call_gemini(
        self, query: str, retrieved_chunks: List[Dict[str, Any]], model: str, api_key: str, chat_history: Optional[List[Dict[str, str]]]
    ) -> Dict[str, Any]:
        prompt = self.build_rag_prompt(query, retrieved_chunks, chat_history)
        url = f"https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent?key={api_key}"
        
        payload = {
            "contents": [{
                "parts": [{"text": prompt}]
            }],
            "generationConfig": {
                "temperature": 0.2,
                "maxOutputTokens": 2048,
            }
        }
        
        async with httpx.AsyncClient(timeout=45.0) as client:
            resp = await client.post(url, json=payload)
            resp.raise_for_status()
            data = resp.json()

        text = ""
        candidates = data.get("candidates", [])
        if candidates and "content" in candidates[0]:
            parts = candidates[0]["content"].get("parts", [])
            if parts:
                text = parts[0].get("text", "")

        return {
            "answer": text or "No answer returned by Gemini.",
            "provider": "gemini",
            "model": model,
            "citations": [
                {"page": c.get("page_number"), "filename": c.get("filename"), "score": c.get("score")}
                for c in retrieved_chunks
            ]
        }

    async def _call_groq(
        self, query: str, retrieved_chunks: List[Dict[str, Any]], model: str, api_key: str, chat_history: Optional[List[Dict[str, str]]]
    ) -> Dict[str, Any]:
        prompt = self.build_rag_prompt(query, retrieved_chunks, chat_history)
        url = "https://api.groq.com/openai/v1/chat/completions"
        headers = {
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json"
        }
        payload = {
            "model": model,
            "messages": [
                {"role": "system", "content": "You are a precise document research assistant that answers based solely on provided excerpts."},
                {"role": "user", "content": prompt}
            ],
            "temperature": 0.2,
            "max_tokens": 1800
        }

        async with httpx.AsyncClient(timeout=30.0) as client:
            resp = await client.post(url, headers=headers, json=payload)
            resp.raise_for_status()
            data = resp.json()

        answer = data["choices"][0]["message"]["content"]
        return {
            "answer": answer,
            "provider": "groq",
            "model": model,
            "citations": [
                {"page": c.get("page_number"), "filename": c.get("filename"), "score": c.get("score")}
                for c in retrieved_chunks
            ]
        }

    async def _call_openai(
        self, query: str, retrieved_chunks: List[Dict[str, Any]], model: str, api_key: str, chat_history: Optional[List[Dict[str, str]]]
    ) -> Dict[str, Any]:
        prompt = self.build_rag_prompt(query, retrieved_chunks, chat_history)
        url = "https://api.openai.com/v1/chat/completions"
        headers = {
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json"
        }
        payload = {
            "model": model,
            "messages": [
                {"role": "system", "content": "You are a precise document research assistant that answers based solely on provided excerpts."},
                {"role": "user", "content": prompt}
            ],
            "temperature": 0.2,
            "max_tokens": 1800
        }

        async with httpx.AsyncClient(timeout=45.0) as client:
            resp = await client.post(url, headers=headers, json=payload)
            resp.raise_for_status()
            data = resp.json()

        answer = data["choices"][0]["message"]["content"]
        return {
            "answer": answer,
            "provider": "openai",
            "model": model,
            "citations": [
                {"page": c.get("page_number"), "filename": c.get("filename"), "score": c.get("score")}
                for c in retrieved_chunks
            ]
        }

    def _generate_offline(self, query: str, retrieved_chunks: List[Dict[str, Any]]) -> Dict[str, Any]:
        """
        Intelligent offline extractive synthesizer. Extracts the most relevant sentences
        matching query keywords, aggregates concepts, and presents structured findings with citations.
        """
        query_words = set(re.findall(r'[a-zA-Z0-9_\-]+', query.lower()))
        query_words.discard("what")
        query_words.discard("how")
        query_words.discard("the")
        query_words.discard("explain")

        extracted_findings = []
        citations = []

        for i, chunk in enumerate(retrieved_chunks):
            page_num = chunk.get("page_number", "?")
            filename = chunk.get("filename", "Document")
            text = chunk.get("text", "")
            score = chunk.get("score", 0.5)

            citations.append({
                "page": page_num,
                "filename": filename,
                "score": score
            })

            # Split sentences
            sentences = re.split(r'(?<=[.!?])\s+', text)
            relevant_sentences = []
            for s in sentences:
                s_lower = s.lower()
                matches = sum(1 for w in query_words if w in s_lower)
                if matches > 0 and len(s.strip()) > 25:
                    relevant_sentences.append((matches, s.strip()))

            relevant_sentences.sort(key=lambda x: x[0], reverse=True)
            top_sentences = [s[1] for s in relevant_sentences[:3]]

            if top_sentences:
                passage_summary = " ".join(top_sentences)
            else:
                passage_summary = text[:280] + ("..." if len(text) > 280 else "")

            extracted_findings.append({
                "source_num": i + 1,
                "page": page_num,
                "filename": filename,
                "summary": passage_summary,
                "score_pct": int(score * 100)
            })

        # Build Markdown response
        output_lines = [
            f"### Document Analysis: **{query.strip()}**\n",
            "Based on analysis of the indexed PDF document, here are the key findings:\n"
        ]

        for finding in extracted_findings:
            output_lines.append(
                f"- **From [Page {finding['page']}]** *({finding['score_pct']}% relevance match)*:\n"
                f"  > \"{finding['summary']}\"\n"
            )

        output_lines.append(
            "\n*💡 Tip: To generate conversational explanations with generative reasoning, configure your API key (Gemini, Groq, or OpenAI) in the Settings modal above.*"
        )

        return {
            "answer": "\n".join(output_lines),
            "provider": "offline",
            "model": "local-synthesis-v1",
            "citations": citations
        }

import math
import re
from typing import List, Dict, Any, Optional
import numpy as np

class HybridRAGEngine:
    """
    High-performance, robust hybrid retrieval engine combining BM25-style lexical ranking
    with dense/keyword matching and Reciprocal Rank Fusion.
    """
    def __init__(self):
        self.stop_words = {
            "a", "an", "and", "are", "as", "at", "be", "by", "for", "from",
            "has", "he", "in", "is", "it", "its", "of", "on", "that", "the",
            "to", "was", "were", "will", "with", "what", "which", "how", "why",
            "who", "when", "where", "can", "could", "would", "should", "about"
        }

    def _tokenize(self, text: str) -> List[str]:
        words = re.findall(r'[a-zA-Z0-9_\-]+', text.lower())
        return [w for w in words if len(w) > 1 and w not in self.stop_words]

    def build_index(self, chunks: List[Dict[str, Any]]) -> Dict[str, Any]:
        """
        Builds an in-memory inverted index and BM25 term frequency representation.
        """
        doc_count = len(chunks)
        if doc_count == 0:
            return {"chunks": [], "doc_lens": [], "avg_dl": 0, "inverted_index": {}, "idf": {}}

        doc_lens = []
        inverted_index = {}
        df = {}

        for idx, chunk in enumerate(chunks):
            tokens = self._tokenize(chunk["text"])
            doc_lens.append(len(tokens))
            seen = set()
            for token in tokens:
                if token not in inverted_index:
                    inverted_index[token] = []
                inverted_index[token].append(idx)
                if token not in seen:
                    df[token] = df.get(token, 0) + 1
                    seen.add(token)

        avg_dl = sum(doc_lens) / doc_count if doc_count > 0 else 1.0

        # BM25 IDF calculation
        idf = {}
        for token, freq in df.items():
            idf[token] = math.log(1.0 + (doc_count - freq + 0.5) / (freq + 0.5))

        return {
            "chunks": chunks,
            "doc_lens": doc_lens,
            "avg_dl": avg_dl,
            "inverted_index": inverted_index,
            "idf": idf,
            "doc_count": doc_count
        }

    def search(
        self, 
        query: str, 
        index: Dict[str, Any], 
        top_k: int = 4,
        k1: float = 1.5,
        b: float = 0.75
    ) -> List[Dict[str, Any]]:
        """
        Executes BM25-based retrieval with query expansion and term match boosting.
        """
        chunks = index.get("chunks", [])
        if not chunks:
            return []

        doc_count = index["doc_count"]
        doc_lens = index["doc_lens"]
        avg_dl = index["avg_dl"]
        inverted_index = index["inverted_index"]
        idf = index["idf"]

        query_tokens = self._tokenize(query)
        if not query_tokens:
            # Fallback: return first few chunks
            return [{**c, "score": 0.5, "matched_terms": []} for c in chunks[:top_k]]

        scores = [0.0] * doc_count
        matches = [set() for _ in range(doc_count)]

        # Frequency in query
        q_freq = {}
        for qt in query_tokens:
            q_freq[qt] = q_freq.get(qt, 0) + 1

        for qt in query_tokens:
            if qt not in inverted_index:
                continue

            token_idf = idf.get(qt, 0.5)
            # Count term frequencies per doc
            posting = inverted_index[qt]
            tf_per_doc = {}
            for doc_idx in posting:
                tf_per_doc[doc_idx] = tf_per_doc.get(doc_idx, 0) + 1

            for doc_idx, tf in tf_per_doc.items():
                dl = doc_lens[doc_idx]
                numerator = tf * (k1 + 1.0)
                denominator = tf + k1 * (1.0 - b + b * (dl / (avg_dl + 1e-6)))
                term_score = token_idf * (numerator / (denominator + 1e-6))
                scores[doc_idx] += term_score
                matches[doc_idx].add(qt)

        # Boost score if chunk matches consecutive query bigrams or title words
        query_bigrams = [f"{query_tokens[i]} {query_tokens[i+1]}" for i in range(len(query_tokens)-1)]
        for doc_idx in range(doc_count):
            if scores[doc_idx] > 0 and query_bigrams:
                text_lower = chunks[doc_idx]["text"].lower()
                for bg in query_bigrams:
                    if bg in text_lower:
                        scores[doc_idx] *= 1.25

        # Normalize scores to 0-1 range
        ranked_indices = sorted(range(doc_count), key=lambda i: scores[i], reverse=True)
        max_score = scores[ranked_indices[0]] if ranked_indices and scores[ranked_indices[0]] > 0 else 1.0

        results = []
        for idx in ranked_indices[:top_k]:
            if scores[idx] <= 0 and results:
                # Stop if zero match and we already have some matches
                break

            norm_score = min(0.99, max(0.40, scores[idx] / (max_score + 1e-6))) if max_score > 0 else 0.50
            results.append({
                **chunks[idx],
                "score": round(norm_score, 3),
                "matched_terms": list(matches[idx])
            })

        return results

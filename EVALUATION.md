# 📊 System Evaluation Report

**Date:** 2026-01-05
**Environment:** Docker Containers (API + UI)
**Test Models:**
1.  **Cloud:** Google Gemini 2.5 Flash-Lite
2.  **Local:** Llama3 (via Ollama CPU)

---

## 1. Latency Performance

We benchmarked the system across two key operations: **Document Ingestion** (Parsing + Embedding) and **Chat Generation** (Retrieval + LLM Inference).

### ⚡ Benchmark Results

| Operation | Google Gemini 2.5 (Cloud) | Llama3 (Local CPU) | Performance Delta |
| :--- | :--- | :--- | :--- |
| **Ingestion (3 files)** | **0.62s** | 13.05s | ~20x faster |
| **Simple Query** | **0.93s** | 25.98s | ~28x faster |
| **Complex Query** | **2.58s** | 47.60s | ~18x faster |

### 🔍 Analysis
* **Bottleneck Identification:** The primary bottleneck in the local setup is **CPU Inference**.
    * *Ingestion:* Generating embeddings locally on CPU took ~13s, whereas the cloud provider processed them in sub-second time.
    * *Generation:* Llama3 on CPU struggled with larger contexts (1600+ chars), taking nearly 48 seconds to generate a summary.
* **Production Recommendation:** For a production deployment, a cloud provider (Gemini/OpenAI) or a GPU-accelerated container is strictly required to meet the <5s latency target.

---

## 2. Cost & Token Usage (Estimated)

Metrics were captured via the `observability.py` middleware using the Gemini provider logs.

| Query Type | Input Tokens | Output Tokens | Total Tokens | Est. Cost (Gemini Flash)* |
| :--- | :--- | :--- | :--- | :--- |
| **Summarization** | 397 | 378 | 775 | ~$0.0001 |
| **Fact Retrieval** | 388 | 49 | 437 | <$0.0001 |

* *Based on current pricing (~$0.10/1M input, ~$0.40/1M output).*
* **Conclusion:** The system is extremely cost-efficient. A typical user session (1 upload + 5 questions) would cost less than **$0.01**.

---

## 3. Groundedness & Accuracy

We verified the "Hallucination Guardrails" by comparing the `answer_snippet` logs against the source documents.

| Test Case | Query | Model Response Snippet | Verdict |
| :--- | :--- | :--- | :--- |
| **Entity Extraction** | "Who is Bob?" | *"Bob is a Backend Engineer with an allocation of 50%..."* | ✅ **Pass** (Accurate to `neon_team.txt`) |
| **Summarization** | "What are they about?" | *"Project Neon is a new mobile dashboard for an existing analytics platform..."* | ✅ **Pass** (Correct summary of `neon_product.txt`) |
| **Citations** | N/A | Logs confirm `citations: 3` returned with response | ✅ **Pass** |

---

## 4. Operational Stability

* **Error Rate:** 0% (during test window).
* **Health Checks:** The API maintained a `200 OK` health status with `<1ms` response time throughout the stress test.
* **Startup Time:**
    * API Container: ~0.5s to ready state.
    * Session Manager: initialized instantly on first request.

## 5. Summary & Recommendations

1.  **Adoption of Cloud LLM:** The specific requirement for a "lightweight" system is best served by **Gemini Flash-Lite**. It offers superior speed (0.9s vs 25s) with negligible cost.
2.  **Local Development:** Llama3 is functional but requires patience without GPU support.
3.  **Observability:** The implemented JSON logging (`structlog`) successfully captured all necessary metrics (Latency, Tokens, Context Size) to generate this report without external APM tools.

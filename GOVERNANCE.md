# 🏛️ Data Catalog Registration (Collibra Draft)

**Asset Name:** DocTalk RAG Service
**Asset Type:** AI/ML Application
**Lifecycle Status:** Development / POC

## 1. Ownership & Accountability
| Role | Assignee | Responsibility |
| :--- | :--- | :--- |
| **Business Owner** | *[Your Name]* | Budget and business value realization. |
| **Data Steward** | *[Your Name]* | Data quality, access approval, and policy enforcement. |
| **Technical Owner** | *DevOps Lead* | System uptime, patching, and Azure resource management. |

## 2. Data Privacy & Sensitivity
| Attribute | Details |
| :--- | :--- |
| **Data Classification** | **Internal Use Only** (Default) / **Confidential** (If flagged) |
| **PII Handling** | ⚠️ **Potential:** Users may upload resumes/contracts containing names or emails. |
| **Retention Policy** | **Ephemeral:** Data exists in memory (FAISS) only for the duration of the container lifecycle. |
| **Cross-Border Transfer** | **No.** All processing occurs within the Azure Region (e.g., East US). |

## 3. Tech Stack & Lineage
* **Upstream Source:** User Uploads (PDF/DOCX/TXT) via Streamlit UI.
* **Processing:**
    * *Ingestion:* LangChain RecursiveCharacterTextSplitter.
    * *Embedding:* Google Gemini 2.5 / OpenAI text-embedding-3-small.
* **Storage:** FAISS (In-Memory Vector Store).
* **Downstream Consumption:** Chat Interface (JSON Response).

## 4. Governance Policies Applied
- [x] **GP-001 (Access Control):** Application requires Azure AD Authentication in Production.
- [x] **GP-004 (Audit Logging):** All transactions log `user_oid`, `timestamp`, and `token_usage` to Azure Monitor.
- [x] **GP-012 (AI Safety):** "Hallucination Guardrails" enforced via strict context grounding; model refuses to answer queries outside the provided context.

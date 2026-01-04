import asyncio
import re
from typing import List, Dict, Any, Tuple, Optional, TypedDict

from langchain_community.vectorstores import FAISS
from langchain_core.documents import Document
from langchain_core.prompts import ChatPromptTemplate
from langchain_core.output_parsers import StrOutputParser
from langgraph.graph import StateGraph, END
import structlog

from src.core.llm_factory import LLMFactory
from src.core.ingestion import IngestionEngine

# Initialize Logger
logger = structlog.get_logger(__name__)


# --- State Definition for LangGraph ---
class GraphState(TypedDict):
    """
    Represents the flow of data through our Agent.
    """

    question: str
    generation: str
    documents: List[Document]
    is_safe: bool


class RAGEngine:
    def __init__(self):
        logger.info("rag_engine_initializing")

        self.provider = LLMFactory().get_provider()
        self.llm = self.provider.get_chat_model()
        self.embeddings = self.provider.get_embeddings()
        self.ingestion = IngestionEngine()

        # Vector Store is isolated per RAGEngine instance (Per User Session)
        self.vector_store: Optional[FAISS] = None

        # Build the Agentic Graph
        self.app = self._build_graph()

        logger.info("rag_engine_ready")

    # ---------------------------------------------------------
    # 1. Ingestion Logic
    # ---------------------------------------------------------
    async def ingest_files(self, files: List[Tuple[bytes, str]]) -> int:
        loop = asyncio.get_running_loop()
        return await loop.run_in_executor(None, self._ingest_sync, files)

    def _ingest_sync(self, files: List[Tuple[bytes, str]]) -> int:
        log = logger.bind(file_count=len(files))
        all_chunks = []

        for file_bytes, filename in files:
            chunks = self.ingestion.process_file(file_bytes, filename)
            all_chunks.extend(chunks)

        if not all_chunks:
            log.warn("ingest_no_chunks_generated")
            return 0

        # Create or Update Vector Store
        # This data stays in memory and is NEVER shared across sessions.
        if self.vector_store:
            self.vector_store.add_documents(all_chunks)
            log.info("vector_store_updated", added_chunks=len(all_chunks))
        else:
            self.vector_store = FAISS.from_documents(all_chunks, self.embeddings)
            log.info("vector_store_created", initial_chunks=len(all_chunks))

        return len(all_chunks)

    # ---------------------------------------------------------
    # 2. Agentic Graph Logic (Governance & Flow)
    # ---------------------------------------------------------
    def _build_graph(self):
        """
        Nodes: Retrieve -> Governance Check -> Generate
        """
        workflow = StateGraph(GraphState)

        # Define Nodes
        workflow.add_node("retrieve", self._retrieve_node)
        workflow.add_node("governance", self._governance_node)
        workflow.add_node("generate", self._generate_node)

        # Define Flow
        workflow.set_entry_point("retrieve")
        workflow.add_edge("retrieve", "governance")

        # Conditional Edge: Only generate if Governance passes
        workflow.add_conditional_edges(
            "governance", self._check_safety, {"safe": "generate", "unsafe": END}
        )
        workflow.add_edge("generate", END)

        return workflow.compile()

    # --- Conditional Logic ---
    def _check_safety(self, state: GraphState):
        return "safe" if state.get("is_safe", True) else "unsafe"

    # --- Nodes ---

    async def _retrieve_node(self, state: GraphState):
        """Node: Fetch documents (with Chit-Chat bypass)"""
        question = state["question"]

        # 1. SMART GREETING CHECK (Skip DB for "Hi")
        greetings = {"hi", "hello", "hey", "hola", "greetings", "thanks"}
        cleaned_q = question.lower().strip("!.,? ")

        if cleaned_q in greetings:
            logger.info("retrieval_skipped", reason="chit_chat_detected")
            return {"documents": []}

        if not self.vector_store:
            logger.warn("retrieval_skipped", reason="empty_vector_store")
            return {"documents": []}

        # 2. RETRIEVAL
        logger.debug("retrieving_documents", query=question)
        retriever = self.vector_store.as_retriever(search_kwargs={"k": 3})
        documents = retriever.invoke(question)

        logger.info("retrieval_complete", doc_count=len(documents))
        return {"documents": documents}

    async def _governance_node(self, state: GraphState):
        """
        Node: Governance & Data Privacy Check.
        Ensures we don't leak "CONFIDENTIAL" documents.
        """
        docs = state["documents"]

        for doc in docs:
            # Simple Rule: Block if document contains specific sensitive markers
            # In production, this would use a PII detection model (e.g., Presidio)
            if (
                "CONFIDENTIAL" in doc.page_content.upper()
                or "DO NOT SHARE" in doc.page_content.upper()
            ):
                logger.warn("governance_violation", source=doc.metadata.get("source"))
                return {
                    "is_safe": False,
                    "generation": "🛑 **Security Alert:** Access denied. One or more retrieved documents are marked CONFIDENTIAL.",
                }

        return {"is_safe": True}

    async def _generate_node(self, state: GraphState):
        """Node: Generate Answer with Table Formatting & Self-Correction"""
        question = state["question"]
        documents = state["documents"]

        # 1. HANDLE NO DOCS / GREETINGS
        if not documents:
            if not self.vector_store:
                return {
                    "generation": "Hello! I don't see any documents yet. Please **upload a file** in the sidebar to get started."
                }

            greetings = {"hi", "hello", "hey", "hola"}
            if question.lower().strip("!.,? ") in greetings:
                return {
                    "generation": "Hello! Your documents are indexed and ready. **What would you like to know?**"
                }

            return {"generation": "I cannot find the answer in the provided documents."}

        # --- CHANGED: Build Context with explicit Source IDs ---
        context_parts = []
        for doc in documents:
            source_name = doc.metadata.get("source", "unknown")
            context_parts.append(f"Source: {source_name}\nContent: {doc.page_content}")

        context = "\n\n---\n\n".join(context_parts)

        # --- CHANGED: Prompt asks for explicit Source Listing ---
        prompt = ChatPromptTemplate.from_template(
            """You are a professional AI assistant analyzing internal documents.

            Instructions:
            1. Answer the user's question based ONLY on the following context.
            2. **Format Logic:**
               - If the data is structured, **YOU MUST USE A MARKDOWN TABLE**.
               - Use **bold** for key entities.
            3. **Citation Check:** - At the very end of your response, output a single line listing ONLY the sources you actually used to answer.
               - Format: `SOURCES: [filename1.pdf, filename2.docx]`
               - If you didn't use any source, output `SOURCES: []`.
            4. **Follow-up:**
               - Before the citation line, add a section starting with "**Suggested Next Steps:**"
               - List 2 short, relevant follow-up questions.

            <context>
            {context}
            </context>

            Question: {question}
            """
        )

        # Standard LCEL Chain - Note: Do not change this
        chain = prompt | self.llm | StrOutputParser()

        try:
            logger.info("generating_answer", context_length=len(context))
            raw_response = await chain.ainvoke(
                {"question": question, "context": context}
            )

            # --- Parse and Filter Logic ---
            final_answer = raw_response

            # Regex to find "SOURCES: [...]" at the end
            match = re.search(
                r"SOURCES: \[(.*?)\]", raw_response, re.DOTALL | re.IGNORECASE
            )

            if match:
                # 1. Extract filenames from the LLM response
                source_str = match.group(1)
                used_filenames = [s.strip() for s in source_str.split(",") if s.strip()]

                # 2. Filter the original 'documents' list
                # We keep a document ONLY if its source was mentioned by the LLM
                filtered_docs = []
                for doc in documents:
                    doc_source = doc.metadata.get("source", "").lower()
                    # Loose matching (e.g. "ticket.pdf" matches "Ticket.pdf")
                    if any(u.lower() in doc_source for u in used_filenames):
                        filtered_docs.append(doc)

                # Update the documents list to only include what was really used
                if filtered_docs:
                    documents = filtered_docs

                # 3. Clean the answer (Remove the SOURCES line so user doesn't see it)
                final_answer = raw_response.replace(match.group(0), "").strip()

            # Return BOTH the cleaned answer AND the filtered documents
            return {"generation": final_answer, "documents": documents}

        except Exception as e:
            logger.error("generation_failed", error=str(e), exc_info=True)
            return {"generation": f"Error generating answer: {e}"}

    # ---------------------------------------------------------
    # 3. Main Interface
    # ---------------------------------------------------------
    async def ask(self, query: str) -> Dict[str, Any]:
        """Entry point for the API to call the Graph"""

        # Log the entry point
        log = logger.bind(query_snippet=query[:50])
        log.info("graph_execution_started")

        # Initialize State
        inputs = {"question": query, "documents": [], "generation": "", "is_safe": True}

        # Run the Graph
        result = await self.app.ainvoke(inputs)
        log.info("graph_execution_complete")

        # Extract Output
        return {
            "answer": result["generation"],
            # Extract citations from the documents that survived the flow
            "citations": [
                {
                    "source": d.metadata.get("source", "unknown"),
                    "text": d.page_content[:100].replace("\n", " ") + "...",
                }
                for d in result.get("documents", [])
            ],
        }

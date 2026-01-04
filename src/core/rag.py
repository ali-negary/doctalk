import asyncio
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
    Represents the state of our graph.
    """

    question: str
    generation: str
    documents: List[Document]
    retry_count: int


class RAGEngine:
    def __init__(self):
        logger.info("rag_engine_initializing")

        self.provider = LLMFactory().get_provider()
        self.llm = self.provider.get_chat_model()
        self.embeddings = self.provider.get_embeddings()
        self.ingestion = IngestionEngine()

        # Initialize Vector Store as None (lazy load)
        self.vector_store: Optional[FAISS] = None

        # Build the Agentic Graph
        self.app = self._build_graph()

        logger.info("rag_engine_ready")

    # ---------------------------------------------------------
    # 1. Ingestion Logic (Restored)
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
        if self.vector_store:
            self.vector_store.add_documents(all_chunks)
            log.info("vector_store_updated", added_chunks=len(all_chunks))
        else:
            self.vector_store = FAISS.from_documents(all_chunks, self.embeddings)
            log.info("vector_store_created", initial_chunks=len(all_chunks))

        return len(all_chunks)

    # ---------------------------------------------------------
    # 2. Agentic Graph Logic (The "Sophisticated" Upgrade)
    # ---------------------------------------------------------
    def _build_graph(self):
        """
        Builds the LangGraph State Machine.
        Nodes: Retrieve -> Grade -> Generate
        """
        workflow = StateGraph(GraphState)

        # Define Nodes
        workflow.add_node("retrieve", self._retrieve_node)
        workflow.add_node("grade_documents", self._grade_documents_node)
        workflow.add_node("generate", self._generate_node)

        # Define Edges
        workflow.set_entry_point("retrieve")
        workflow.add_edge("retrieve", "grade_documents")

        # Simple flow: Grade -> Generate -> End
        # (In a V2, we would loop back if grade is bad)
        workflow.add_edge("grade_documents", "generate")
        workflow.add_edge("generate", END)

        return workflow.compile()

    # --- Nodes ---

    async def _retrieve_node(self, state: GraphState):
        """Node: Fetch documents from Vector Store"""
        question = state["question"]

        if not self.vector_store:
            logger.warn("retrieval_skipped", reason="empty_vector_store")
            return {"documents": []}

        # Retrieve top 3
        # Log the search query for debugging retrieval quality
        logger.debug("retrieving_documents", query=question)

        retriever = self.vector_store.as_retriever(search_kwargs={"k": 3})
        documents = retriever.invoke(question)

        logger.info("retrieval_complete", doc_count=len(documents))
        return {"documents": documents}

    async def _grade_documents_node(self, state: GraphState):
        """Node: Filter out irrelevant documents (Grounding Check)"""
        # For this MVP, we pass all docs through, but we could add an LLM check here.
        # This placeholder node allows us to add 'Guardrails' later easily.
        logger.debug("grading_documents", doc_count=len(state["documents"]))
        return {"documents": state["documents"]}

    async def _generate_node(self, state: GraphState):
        """Node: Generate Answer"""
        question = state["question"]
        documents = state["documents"]

        if not documents:
            logger.info("generation_skipped", reason="no_context")
            return {
                "generation": "I'm sorry, I don't have any knowledge about that yet. Please upload a document."
            }

        context = "\n\n".join([doc.page_content for doc in documents])

        # Prompt Engineering
        prompt = ChatPromptTemplate.from_template(
            """You are a helpful assistant discussing internal documents.
            Answer the user's question based ONLY on the following context.
            If the answer is not in the context, say: "I cannot find the answer in the provided documents."

            <context>
            {context}
            </context>

            Question: {question}
            """
        )

        # Standard LCEL Chain
        chain = prompt | self.llm | StrOutputParser()

        try:
            logger.info("generating_answer", context_length=len(context))
            response = await chain.ainvoke({"question": question, "context": context})
            return {"generation": response}
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
        inputs = {
            "question": query,
            "retry_count": 0,
            "documents": [],
            "generation": "",
        }

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
                    "text": d.page_content[:150].replace("\n", " ") + "...",
                }
                for d in result.get("documents", [])
            ],
        }

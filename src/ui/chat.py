import uuid

import requests
import streamlit as st
import structlog

from src.core.config import settings as _settings


# --- 1. Logging Configuration (Cached Resource) ---
# We use st.cache_resource so logging isn't re-initialized on every button click
@st.cache_resource
def configure_logging():
    processors = [
        structlog.contextvars.merge_contextvars,
        structlog.processors.add_log_level,
        structlog.processors.TimeStamper(fmt="iso"),
        structlog.processors.JSONRenderer(),
    ]

    structlog.configure(
        processors=processors,
        logger_factory=structlog.PrintLoggerFactory(),
    )
    return structlog.get_logger()


logger = configure_logging()


# --- 2. Configuration & State ---
st.set_page_config(page_title="DocTalk AI", page_icon="📄", layout="wide")

API_BASE_URL = _settings.APP_API_URL

# Session State Initialization
if "session_id" not in st.session_state:
    st.session_state.session_id = str(uuid.uuid4())
    logger.info("new_session_started", session_id=st.session_state.session_id)

if "messages" not in st.session_state:
    st.session_state.messages = [
        {
            "role": "assistant",
            "content": "Hello! Upload a document and ask me anything about it.",
        }
    ]

# Bind session ID to logger for all subsequent calls
log = logger.bind(session_id=st.session_state.session_id)


# --- 3. Sidebar: Health Check & Upload ---
with st.sidebar:
    st.header("📁 Document Manager")

    # Auto-Health Check (Visual Indicator)
    try:
        health_check = requests.get(f"{API_BASE_URL}/health", timeout=2)
        if health_check.status_code == 200:
            st.success("🟢 API Online")
        else:
            st.warning(f"🟡 API Initializing ({health_check.status_code})")
    except requests.exceptions.ConnectionError:
        st.error("🔴 API Offline")
        log.error("api_health_check_failed", url=API_BASE_URL)

    st.caption(f"Session: {st.session_state.session_id[-8:]}")

    uploaded_files = st.file_uploader(
        "Upload PDF, DOCX, or TXT",
        type=["pdf", "docx", "txt", "md"],
        accept_multiple_files=True,
    )

    if uploaded_files and st.button("Ingest Documents", type="primary"):
        with st.spinner("Ingesting and Indexing..."):
            log.info("upload_initiated", file_count=len(uploaded_files))
            try:
                # Prepare payload
                files = [
                    ("files", (f.name, f.getvalue(), f.type)) for f in uploaded_files
                ]
                headers = {"X-Session-ID": st.session_state.session_id}

                # Call API
                response = requests.post(
                    f"{API_BASE_URL}/upload", files=files, headers=headers
                )

                if response.status_code == 200:
                    data = response.json()
                    st.success(
                        f"✅ Indexed {data['chunks_processed']} chunks from {len(data['files_processed'])} files."
                    )
                    log.info("upload_success", chunks=data["chunks_processed"])
                else:
                    st.error(f"❌ Error {response.status_code}: {response.text}")
                    log.error(
                        "upload_failed",
                        status=response.status_code,
                        error=response.text,
                    )

            except requests.exceptions.ConnectionError:
                st.error("❌ Could not connect to the API. Is the backend running?")
            except Exception as e:
                st.error(f"❌ An unexpected error occurred: {e}")
                log.error("upload_exception", error=str(e))

    st.markdown("---")
    with st.expander("🛠️ Debug Info"):
        st.json(
            {
                "API_URL": API_BASE_URL,
                "Session": st.session_state.session_id,
                "LLM Provider": _settings.LLM_PROVIDER,
            }
        )


# --- 4. Main Chat Interface ---
st.title("🤖 DocTalk: Discuss Your Documents")

# Display History
for message in st.session_state.messages:
    with st.chat_message(message["role"]):
        st.markdown(message["content"])

# Handle User Input
if prompt := st.chat_input("Ask a question about your documents..."):
    # Log the interaction
    log.info("user_query_received", query_length=len(prompt))

    # A. Display User Message
    st.session_state.messages.append({"role": "user", "content": prompt})
    with st.chat_message("user"):
        st.markdown(prompt)

    # B. Call API
    with st.chat_message("assistant"):
        message_placeholder = st.empty()
        message_placeholder.markdown("Thinking...")

        try:
            payload = {"message": prompt}
            headers = {"X-Session-ID": st.session_state.session_id}

            response = requests.post(
                f"{API_BASE_URL}/chat", json=payload, headers=headers
            )

            if response.status_code == 200:
                data = response.json()
                answer = data["answer"]
                citations = data.get("citations", [])

                # Format Citations
                if citations:
                    answer += "\n\n**Sources:**\n"
                    for cit in citations:
                        answer += f"- *{cit['source']}*: \"{cit['text']}\"\n"

                # Display Answer
                message_placeholder.markdown(answer)

                # Save to History
                st.session_state.messages.append(
                    {"role": "assistant", "content": answer}
                )
                log.info("chat_response_delivered", citation_count=len(citations))

            else:
                error_msg = f"Error {response.status_code}: {response.text}"
                message_placeholder.error(error_msg)
                st.session_state.messages.append(
                    {"role": "assistant", "content": error_msg}
                )
                log.error(
                    "chat_api_error",
                    status=response.status_code,
                    response=response.text,
                )

        except requests.exceptions.ConnectionError:
            error_msg = f"❌ Could not connect to {API_BASE_URL}."
            message_placeholder.error(error_msg)
            log.critical("chat_connection_failed", url=API_BASE_URL)
        except Exception as e:
            error_msg = f"❌ An error occurred: {str(e)}"
            message_placeholder.error(error_msg)
            log.error("chat_exception", error=str(e))

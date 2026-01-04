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

# Custom CSS for UI Polish
st.markdown(
    """
    <style>
    /* Hide the 'Deploy' button */
    .stDeployButton {display:none !important;}
    [data-testid="stDeployButton"] {display:none !important;}

    /* Style the Sources Expander Header */
    .streamlit-expanderHeader {
        font-weight: bold;
        color: #0e1117;
    }

    /* Clean top padding */
    .block-container {
        padding-top: 2rem;
    }
    </style>
""",
    unsafe_allow_html=True,
)

API_BASE_URL = _settings.APP_API_URL

# Session Initialization
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


# --- 3. Sidebar: Document Manager ---
with st.sidebar:
    st.header("📂 Document Manager")

    # API Status Check
    try:
        if requests.get(f"{API_BASE_URL}/health", timeout=1).status_code == 200:
            st.success("🟢 System Online")
        else:
            st.warning("🟡 System Initializing")
    except requests.exceptions.RequestException:
        # Specific catch for connection issues
        st.error("🔴 Backend Offline")
    except Exception as e:
        # Catch-all for other weird errors (like URL parsing issues)
        st.error(f"🔴 System Error: {e}")

    st.markdown("---")

    # File Uploader
    uploaded_files = st.file_uploader(
        "Upload Documents (Max 2MB)",
        type=["pdf", "docx", "txt", "md"],
        accept_multiple_files=True,
        help="Supported formats: PDF, Word, Text. Limit 2MB per file.",
    )

    # File Size Check
    valid_files = []
    if uploaded_files:
        for f in uploaded_files:
            if f.size > 2 * 1024 * 1024:  # 2MB Limit
                st.error(f"❌ {f.name} is too large (>2MB).")
            else:
                valid_files.append(f)

    # Ingest Button
    if valid_files:
        if st.button("🚀 Ingest Documents", type="primary", use_container_width=True):
            with st.spinner(f"Processing {len(valid_files)} files..."):
                log.info("upload_initiated", count=len(valid_files))
                try:
                    files = [
                        ("files", (f.name, f.getvalue(), f.type)) for f in valid_files
                    ]
                    headers = {"X-Session-ID": st.session_state.session_id}

                    res = requests.post(
                        f"{API_BASE_URL}/upload", files=files, headers=headers
                    )

                    if res.status_code == 200:
                        data = res.json()
                        st.success(f"✅ Indexed {data['chunks_processed']} chunks.")
                        log.info("upload_success", chunks=data["chunks_processed"])
                    else:
                        st.error(f"❌ Error: {res.text}")
                        log.error("upload_failed", error=res.text)
                except Exception as e:
                    st.error(f"❌ Error: {e}")
                    log.error("upload_exception", error=str(e))

    st.markdown("---")
    with st.expander("🛠️ Debug Info"):
        st.json(
            {
                "API": API_BASE_URL,
                "Session": st.session_state.session_id,
                "Provider": _settings.LLM_PROVIDER,
            }
        )


# --- 4. Main Chat Interface ---
st.title("🤖 DocTalk: Discuss Your Documents")
st.caption("Secure, Private Document Assistant")

# Display History
# We loop through history first so everything persists correctly on rerun
for msg in st.session_state.messages:
    with st.chat_message(msg["role"]):
        st.markdown(msg["content"])


# Input Handling
if prompt := st.chat_input("Ask about your documents..."):
    # 1. Log and Display User Query
    log.info("user_query", length=len(prompt))
    st.session_state.messages.append({"role": "user", "content": prompt})
    with st.chat_message("user"):
        st.markdown(prompt)

    # 2. Generate Response
    with st.chat_message("assistant"):
        # Create a placeholder for the "Thinking..." state
        placeholder = st.empty()
        placeholder.markdown("Thinking...")

        try:
            headers = {"X-Session-ID": st.session_state.session_id}
            res = requests.post(
                f"{API_BASE_URL}/chat", json={"message": prompt}, headers=headers
            )

            if res.status_code == 200:
                data = res.json()
                answer = data["answer"]
                citations = data.get("citations", [])

                # A. Save to History IMMEDIATELY
                # This ensures that if the script reruns, the answer is already in the list above.
                st.session_state.messages.append(
                    {"role": "assistant", "content": answer}
                )

                # B. Render the Answer (Overwriting "Thinking...")
                placeholder.markdown(answer)

                # C. Render Citations (The Senior Polish)
                if citations:
                    grouped = {}
                    for c in citations:
                        grouped.setdefault(c["source"], []).append(c["text"])

                    # Create a NEW container below the answer for citations
                    with st.expander("📚 View Sources", expanded=False):
                        for src, texts in grouped.items():
                            st.markdown(f"**📄 {src}**")
                            for t in texts:
                                st.caption(f'• "{t}"')

                log.info("chat_success", citations=len(citations))

            else:
                err_msg = f"Error {res.status_code}: {res.text}"
                placeholder.error(err_msg)
                st.session_state.messages.append(
                    {"role": "assistant", "content": err_msg}
                )
                log.error("chat_error", status=res.status_code)

        except Exception as e:
            placeholder.error(f"Connection Error: {e}")
            log.critical("chat_connection_fail", error=str(e))

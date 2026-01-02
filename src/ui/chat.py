import uuid

import requests
import streamlit as st

from src.core.config import settings as _settings


API_BASE_URL = _settings.APP_API_URL

# 1. Page Configuration
st.set_page_config(page_title="DocTalk AI", page_icon="📄", layout="wide")

# 2. Session State Initialization
if "session_id" not in st.session_state:
    st.session_state.session_id = str(uuid.uuid4())

if "messages" not in st.session_state:
    st.session_state.messages = [
        {
            "role": "assistant",
            "content": "Hello! Upload a document and ask me anything about it.",
        }
    ]

# 3. Sidebar: Document Ingestion
with st.sidebar:
    st.header("📁 Document Manager")
    st.caption(f"Session ID: {st.session_state.session_id[-8:]}...")

    uploaded_files = st.file_uploader(
        "Upload PDF, DOCX, or TXT",
        type=["pdf", "docx", "txt", "md"],
        accept_multiple_files=True,
    )

    if uploaded_files and st.button("Ingest Documents", type="primary"):
        with st.spinner("Ingesting and Indexing..."):
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
                else:
                    st.error(f"❌ Error {response.status_code}: {response.text}")

            except requests.exceptions.ConnectionError:
                st.error("❌ Could not connect to the API. Is the backend running?")
            except Exception as e:
                st.error(f"❌ An unexpected error occurred: {e}")

    st.markdown("---")
    st.markdown("### 🛠️ Debug Info")
    st.json({"API_URL": API_BASE_URL, "Session": st.session_state.session_id})


# 5. Main Chat Interface
st.title("🤖 DocTalk: Discuss Your Documents")

# Display History
for message in st.session_state.messages:
    with st.chat_message(message["role"]):
        st.markdown(message["content"])

# Handle User Input
if prompt := st.chat_input("Ask a question about your documents..."):
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

            else:
                error_msg = f"Error {response.status_code}: {response.text}"
                message_placeholder.error(error_msg)
                st.session_state.messages.append(
                    {"role": "assistant", "content": error_msg}
                )

        except requests.exceptions.ConnectionError:
            error_msg = "❌ Could not connect to the Backend API."
            message_placeholder.error(error_msg)
        except Exception as e:
            error_msg = f"❌ An error occurred: {str(e)}"
            message_placeholder.error(error_msg)

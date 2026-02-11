import os
import json
import requests
import streamlit as st
import uuid

st.set_page_config(page_title="RAG Assistant", layout="centered")

st.markdown(
    """
    <style>
    /* Larghezza “sidebar-like” per il popover */
    :root { --sidebar-like-width: 21rem; }

    /* Bottone del popover in sidebar: full width */
    section[data-testid="stSidebar"] [data-testid="stPopover"] button {
        width: 100% !important;
        justify-content: space-between !important;
    }

    /* Corpo del popover: forzalo a larghezza sidebar e aggancialo a sinistra */
    div[data-testid="stPopoverBody"]{
        width: var(--sidebar-like-width) !important;
        max-width: var(--sidebar-like-width) !important;
        min-width: var(--sidebar-like-width) !important;
        left: 0 !important;          /* evita che si “allarghi” verso destra */
        right: auto !important;
    }

    /* Contenuto interno: occupa tutta la larghezza del popover */
    div[data-testid="stPopoverBody"] div[data-testid="stVerticalBlock"],
    div[data-testid="stPopoverBody"] div[data-testid="stRadio"]{
        width: 100% !important;
        max-width: 100% !important;
    }
    </style>
    """,
    unsafe_allow_html=True
)


# === Config ===
RAG_API_BASE_URL = os.getenv("RAG_API_BASE_URL", "http://rag-api:8000")
RAG_API_TIMEOUT = float(os.getenv("RAG_API_TIMEOUT", "60"))
# Se in futuro vuoi proteggere /query con una chiave interna:
RAG_UI_API_KEY = os.getenv("RAG_UI_API_KEY", "")

if "session_id" not in st.session_state:
    st.session_state.session_id = str(uuid.uuid4())

def call_rag(question: str, technique: str, session_id: str, force_fallback: bool = False) -> dict:
    url = f"{RAG_API_BASE_URL.rstrip('/')}/query"
    payload = {
        "question": question,
        "search_technique": technique,
        "session_id": session_id,
        "force_fallback": force_fallback,
        "stream": False,
    }

    headers = {"Content-Type": "application/json"}
    if RAG_UI_API_KEY:
        headers["X-API-Key"] = RAG_UI_API_KEY

    r = requests.post(
        url,
        headers=headers,
        data=json.dumps(payload),
        timeout=RAG_API_TIMEOUT,
        verify=False
    )
    r.raise_for_status()
    return r.json()


def call_rag_stream(question: str, technique: str, session_id: str, force_fallback: bool = False):
    url = f"{RAG_API_BASE_URL.rstrip('/')}/query"
    payload = {
        "question": question,
        "search_technique": technique,
        "session_id": session_id,
        "force_fallback": force_fallback,
        "stream": True,
    }

    headers = {"Content-Type": "application/json"}
    headers["Accept"] = "text/event-stream"
    
    if RAG_UI_API_KEY:
        headers["X-API-Key"] = RAG_UI_API_KEY

    with requests.post(
        url,
        headers=headers,
        data=json.dumps(payload),
        timeout=RAG_API_TIMEOUT,
        verify=False,
        stream=True
    ) as r:
        r.raise_for_status()

        for raw_line in r.iter_lines(decode_unicode=True):
            if not raw_line:
                continue

            line = raw_line.strip()
            if not line.startswith("data:"):
                continue

            data = line[len("data:"):].strip()
            try:
                yield json.loads(data)
            except json.JSONDecodeError:
                continue



# === Sidebar ===

st.sidebar.title("Impostazioni")

OPTIONS = ["hybrid", "dense", "sparse"]

if "search_technique" not in st.session_state:
    st.session_state.search_technique = "dense"

def _update_technique():
    st.session_state.search_technique = st.session_state._technique_tmp

with st.sidebar.popover(f"Tecnica di ricerca: {st.session_state.search_technique}"):
    st.radio(
        "Tecnica di ricerca",
        OPTIONS,
        index=OPTIONS.index(st.session_state.search_technique),
        key="_technique_tmp",
        label_visibility="collapsed",
        on_change=_update_technique,
    )

search_technique = st.session_state.search_technique
show_sources = st.sidebar.checkbox("Mostra fonti/chunk", value=True)



# === Session memory ===
if "messages" not in st.session_state:
    st.session_state.messages = [
        {"role": "assistant", "content": "Ciao! Fammi una domanda sui documenti.", "sources": []}
    ]

# === Render chat history ===
st.title("RAG Assistant")

for m in st.session_state.messages:
    with st.chat_message(m["role"]):
        st.markdown(m["content"])
        if m["role"] == "assistant" and show_sources and m.get("sources"):
            with st.expander("Fonti / chunk usati"):
                for i, s in enumerate(m["sources"], 1):
                    st.markdown(f"**Fonte {i}**")
                    st.code(s)

# === Input ===
question = st.chat_input("Scrivi una domanda...")
use_stream = True
force_fallback_ui = False

if question:
    st.session_state.messages.append({"role": "user", "content": question, "sources": []})
    with st.chat_message("user"):
        st.markdown(question)

    with st.chat_message("assistant"):
        try:
            if not use_stream:
                with st.spinner("Sto cercando nei documenti..."):
                    resp = call_rag(
                        question,
                        search_technique,
                        st.session_state.session_id,
                        force_fallback=force_fallback_ui
                    )

                answer = resp.get("answer", "") or ""
                contexts = resp.get("contexts", [])
                if not isinstance(contexts, list):
                    contexts = []

                st.markdown(answer if answer else "_(nessuna risposta)_")

                if show_sources and contexts:
                    with st.expander("Fonti / chunk usati"):
                        for i, c in enumerate(contexts, 1):
                            st.markdown(f"**Fonte {i}**")
                            st.code(c)

                st.session_state.messages.append({
                    "role": "assistant",
                    "content": answer,
                    "sources": contexts
                })

            else:
                # STREAMING MODE (SSE)
                status_box = st.empty()
                answer_box = st.empty()
                sources_box = st.empty()

                with st.spinner("Sto cercando nei documenti..."):
                    events = call_rag_stream(
                        question,
                        search_technique,
                        st.session_state.session_id,
                        force_fallback=force_fallback_ui
                    )

                final_answer = ""
                final_contexts = []

                for ev in events:
                    ev_type = ev.get("type")

                    if ev_type == "heartbeat":
                        continue

                    if ev_type == "status":
                        msg = ev.get("message", "")
                        if msg:
                            status_box.info(msg)

                    elif ev_type == "error":
                        msg = ev.get("message", "Errore sconosciuto")
                        status_box.error(msg)
                        break

                    elif ev_type == "result":
                        final_answer = ev.get("answer", "") or ""
                        final_contexts = ev.get("contexts", [])
                        if not isinstance(final_contexts, list):
                            final_contexts = []

                        status_box.empty()
                        answer_box.markdown(final_answer if final_answer else "_(nessuna risposta)_")

                        if show_sources and final_contexts:
                            with sources_box.container():
                                with st.expander("Fonti / chunk usati"):
                                    for i, c in enumerate(final_contexts, 1):
                                        st.markdown(f"**Fonte {i}**")
                                        st.code(c)
                        break

                if final_answer:
                    st.session_state.messages.append({
                        "role": "assistant",
                        "content": final_answer,
                        "sources": final_contexts
                    })


        except requests.HTTPError as e:
            st.error(f"Errore HTTP dal backend: {e}")
        except requests.RequestException as e:
            st.error(f"Errore di rete verso il backend: {e}")
        except Exception as e:
            st.error(f"Errore inatteso: {e}")

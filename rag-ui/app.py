import os
import json
import requests
import streamlit as st

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

def call_rag(question: str, technique: str) -> dict:
    url = f"{RAG_API_BASE_URL.rstrip('/')}/query"
    payload = {"question": question, "search_technique": technique}

    headers = {"Content-Type": "application/json"}
    if RAG_UI_API_KEY:
        headers["X-API-Key"] = RAG_UI_API_KEY

    r = requests.post(url, headers=headers, data=json.dumps(payload), timeout=RAG_API_TIMEOUT, verify=False)
    r.raise_for_status()
    return r.json()

# === Sidebar ===
st.sidebar.title("Impostazioni")

OPTIONS = ["hybrid", "dense", "sparse"]

if "search_technique" not in st.session_state:
    st.session_state.search_technique = "hybrid"

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

if question:
    # Mostra e salva messaggio utente
    st.session_state.messages.append({"role": "user", "content": question, "sources": []})
    with st.chat_message("user"):
        st.markdown(question)

    # Chiamata al backend + risposta
    with st.chat_message("assistant"):
        with st.spinner("Sto cercando nei documenti..."):
            try:
                resp = call_rag(question, search_technique)
                answer = resp.get("answer", "")
                contexts = resp.get("contexts", []) if isinstance(resp.get("contexts", []), list) else []

                st.markdown(answer if answer else "_(nessuna risposta)_")

                if show_sources and contexts:
                    with st.expander("Fonti / chunk usati"):
                        for i, c in enumerate(contexts, 1):
                            st.markdown(f"**Fonte {i}**")
                            st.code(c)

                st.session_state.messages.append({
                    "role": "assistant",
                    "content": answer if answer else "",
                    "sources": contexts
                })

            except requests.HTTPError as e:
                st.error(f"Errore HTTP dal backend: {e}")
            except requests.RequestException as e:
                st.error(f"Errore di rete verso il backend: {e}")
            except Exception as e:
                st.error(f"Errore inatteso: {e}")

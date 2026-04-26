import os
import json
import requests
import streamlit as st
import uuid

st.set_page_config(page_title="Assistente accademico", layout="centered")

st.markdown("""
<div style="margin-top:10px;">
    <h1 style="margin-bottom:3px; padding:0;">
        Assistente accademico
    </h1>
    <h2 style="color:#6b7280; font-weight:400; font-size:20px; margin-bottom:40px; padding:0;">
        Corso di Laurea Magistrale in Ingegneria Informatica e Robotica
    </h2>
</div>
""", unsafe_allow_html=True)

RAG_API_BASE_URL = os.getenv("RAG_API_BASE_URL", "http://rag-api:8000")
RAG_API_TIMEOUT = float(os.getenv("RAG_API_TIMEOUT", "100"))

#RAG_UI_API_KEY = os.getenv("RAG_UI_API_KEY", "")

if "session_id" not in st.session_state:
    st.session_state.session_id = str(uuid.uuid4())

def reset_chat():
    st.session_state.session_id = str(uuid.uuid4())

    st.session_state.messages = [
        {"role": "assistant", "content": "Ciao! Fammi una domanda.", "sources": []}
    ]

    st.session_state._do_rerun = True

if st.session_state.get("_do_rerun"):
    st.session_state._do_rerun = False
    st.rerun()


def call_rag(question: str, session_id: str, force_fallback: bool = False) -> dict:
    url = f"{RAG_API_BASE_URL.rstrip('/')}/query"
    payload = {
        "question": question,
        "search_technique": "dense",
        "session_id": session_id,
        "force_fallback": force_fallback,
        "stream": False,
    }

    headers = {"Content-Type": "application/json"}

    r = requests.post(
        url,
        headers=headers,
        data=json.dumps(payload),
        timeout=RAG_API_TIMEOUT,
        verify=False
    )
    r.raise_for_status()
    return r.json()


def call_rag_stream(question: str, session_id: str, force_fallback: bool = False):
    url = f"{RAG_API_BASE_URL.rstrip('/')}/query"
    payload = {
        "question": question,
        "search_technique": "dense",
        "session_id": session_id,
        "force_fallback": force_fallback,
        "stream": True,
    }

    headers = {"Content-Type": "application/json"}
    headers["Accept"] = "text/event-stream"


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


def render_references(refs: list):
    if not isinstance(refs, list) or not refs:
        return

    for i, r in enumerate(refs, 1):
        if not isinstance(r, dict):
            continue

        title = r.get("title") or f"Fonte {i}"
        section = r.get("section") or ""
        url = r.get("url") or ""

        indices = r.get("indices") or []
        if isinstance(indices, list):
            clean_indices = sorted({int(x) for x in indices if str(x).isdigit()})
        else:
            clean_indices = []

        idx_suffix = (" " + " ".join(f"[{n}]" for n in clean_indices)) if clean_indices else ""

        label = title + (f" — {section}" if section else "")

        if url:
            st.markdown(f"- [{label}]({url}){idx_suffix}")
        else:
            st.markdown(f"- {label}{idx_suffix}")


if "messages" not in st.session_state:
    st.session_state.messages = [
        {"role": "assistant", "content": "Ciao! Fammi una domanda sui documenti.", "sources": []}
    ]

if "pending_question" not in st.session_state:
    st.session_state.pending_question = None

if "processing_qid" not in st.session_state:
    st.session_state.processing_qid = None

if "is_generating" not in st.session_state:
    st.session_state.is_generating = False

if "active_job" not in st.session_state:
    st.session_state.active_job = None

if st.session_state.is_generating and not st.session_state.pending_question and not st.session_state.active_job:
    st.session_state.is_generating = False

if "rerun_after_answer" not in st.session_state:
    st.session_state.rerun_after_answer = False


for m in st.session_state.messages:
    with st.chat_message(m["role"]):
        st.markdown(m["content"])
        if m["role"] == "assistant" and m.get("sources"):
            with st.expander("Fonti usate"):
                render_references(m["sources"])


question = st.chat_input("Scrivi una domanda...", key="chat_input", disabled=st.session_state.is_generating)

if question:
    if st.session_state.is_generating:
        st.toast("Sto ancora rispondendo…", icon="⏳")
    else:
        st.session_state.is_generating = True

        st.session_state.pending_question = {
            "id": str(uuid.uuid4()),
            "text": question
        }
        st.rerun()


#col_in, col_btn = st.columns([12, 1], vertical_alignment="bottom")

#with col_in:
#    question = st.chat_input("Scrivi una domanda…")

#with col_btn:
#    st.button("🔄", on_click=reset_chat, use_container_width=True)

use_stream = True
force_fallback_ui = False

pending = st.session_state.get("pending_question")

if st.session_state.is_generating and st.session_state.active_job:
    pending = st.session_state.active_job

if pending:
    qid = pending["id"]
    qtext = pending["text"]

    if st.session_state.processing_qid != qid:
        st.session_state.processing_qid = qid
        st.session_state.active_job = {"id": qid, "text": qtext, "user_added": False}
        st.session_state.pending_question = None
        st.session_state.is_generating = True
    else:
        st.session_state.pending_question = None
        st.session_state.is_generating = True

    if st.session_state.active_job and not st.session_state.active_job.get("user_added", False):
        st.session_state.messages.append({"role": "user", "content": qtext, "sources": []})
        st.session_state.active_job["user_added"] = True

    with st.chat_message("user"):
        st.markdown(qtext)

    with st.chat_message("assistant"):
        try:
            if not use_stream:
                with st.spinner("Sto cercando nei documenti..."):
                    resp = call_rag(
                        qtext,
                        st.session_state.session_id,
                        force_fallback=force_fallback_ui
                    )

                answer = resp.get("answer", "") or ""

                references = resp.get("references", [])
                if not isinstance(references, list):
                    references = []

                st.markdown(answer if answer else "_(nessuna risposta)_")

                if references:
                    with st.expander("Fonti usate"):
                        render_references(references)

                st.session_state.messages.append({
                    "role": "assistant",
                    "content": answer,
                    "sources": references
                })

            else:
                # STREAMING MODE (SSE)
                status_box = st.empty()
                answer_box = st.empty()
                sources_box = st.empty()

                status_box.info("Sto processando la richiesta...")

                events = call_rag_stream(
                    qtext,
                    st.session_state.session_id,
                    force_fallback=force_fallback_ui
                )

                final_answer = ""
                final_references = []

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
                        final_references = ev.get("references", [])

                        if not isinstance(final_references, list):
                            final_references = []

                        status_box.empty()
                        answer_box.markdown(final_answer if final_answer else "_(nessuna risposta)_")

                        if final_references:
                            with sources_box.container():
                                with st.expander("Fonti usate"):
                                    render_references(final_references)

                        break

                if final_answer:
                    st.session_state.messages.append({
                        "role": "assistant",
                        "content": final_answer,
                        "sources": final_references
                    })

        except requests.HTTPError as e:
            st.error(f"Errore HTTP dal backend: {e}")
        except requests.RequestException as e:
            st.error(f"Errore di rete verso il backend: {e}")
        except Exception as e:
            st.error(f"Errore inatteso: {e}")

        finally:
            st.session_state.is_generating = False
            st.session_state.processing_qid = None
            st.session_state.active_job = None
            st.session_state.pending_question = None
            st.session_state.rerun_after_answer = True

if st.session_state.get("rerun_after_answer", False):
    st.session_state.rerun_after_answer = False
    st.rerun()

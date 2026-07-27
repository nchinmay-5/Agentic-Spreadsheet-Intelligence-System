"""Small Streamlit UI for local workbook exploration."""

import requests
import streamlit as st

st.set_page_config(page_title="Spreadsheet Intelligence")
st.title("Spreadsheet Intelligence")
api_url = st.sidebar.text_input("API URL", "http://localhost:8000")
upload = st.file_uploader("Upload workbook", type=["xlsx"])
if upload and st.button("Process workbook"):
    response = requests.post(f"{api_url}/workbooks", files={"file": (upload.name, upload.getvalue(), "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")})
    if response.ok:
        st.session_state.workbook_id = response.json()["workbook_id"]
        st.success(f"Processed {st.session_state.workbook_id}")
    else:
        st.error(response.text)
question = st.text_input("Ask about a metric, formula, input, impact, or comparison")
if question and st.button("Ask"):
    response = requests.post(f"{api_url}/query", json={"workbook_id": st.session_state.get("workbook_id", ""), "question": question})
    if response.ok:
        result = response.json()
        st.write(result.get("answer") or result.get("clarification"))
        with st.expander("Evidence"):
            st.json(result.get("evidence"))
    else:
        st.error(response.text)
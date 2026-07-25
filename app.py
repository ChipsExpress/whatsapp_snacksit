import html
import os
from datetime import datetime

import pandas as pd
import streamlit as st
import streamlit.components.v1 as components

from utils.cloudinary_uploader import upload_media
from utils.excel_reader import read_contacts_from_excel
from utils.conversation_store import (
    ConversationStoreError,
    fetch_conversations,
    fetch_messages,
    is_configured as is_inbox_database_configured,
    mark_conversation_read,
    save_outbound_message,
)
from utils.twilio_content import fetch_content_template
from utils.whatsapp_sender import send_bulk_whatsapp_templates, send_whatsapp_text


st.set_page_config(
    page_title="WhatsApp Bulk Sender",
    page_icon="assets/logo.png",
    layout="wide",
)


def main():
    _initialize_session_state()
    _inject_styles()
    _render_header()

    if not st.session_state.get("logged_in", False):
        _render_login_page()
        return

    dashboard_tab, inbox_tab = st.tabs(["Dashboard", "Inbox"])

    with dashboard_tab:
        left_column, main_column = st.columns([0.85, 2.65], gap="large")

        with left_column:
            _render_stats_overview()

        with main_column:
            _render_dashboard()

    with inbox_tab:
        _render_inbox_tab()




def _initialize_session_state():
    defaults = {
        "latest_public_url": "",
        "latest_uploaded_image_key": "",
        "last_send_results": [],
        "current_contact_count": 0,
        "template_cache_sid": "",
        "template_cache": None,
        "template_error": "",
        "logged_in": False,
    }

    for key, value in defaults.items():
        if key not in st.session_state:
            st.session_state[key] = value



def _inject_styles():
    st.markdown(
        """
        <style>
        html, body, [data-testid="stAppViewContainer"], .stApp {
            overflow: auto !important;
            height: 100vh !important;
        }
        [data-testid="stAppViewContainer"] {
            display: flex;
            flex-direction: column;
            height: 100vh !important;
        }
        [data-testid="stMain"] {
            flex: 1;
            overflow: auto !important;
        }
        .block-container {
            min-height: 100% !important;
            overflow: visible !important;
            padding-top: 0 !important;
            padding-bottom: 1.5rem !important;
            max-width: 1240px;
        }
        div[data-testid="stHorizontalBlock"] {
            overflow-x: hidden !important;
            overflow-y: visible !important;
        }
        div[data-testid="stHorizontalBlock"] > div:first-child {
            overflow: hidden !important;
        }
        [data-testid="stVerticalBlockBorderWrapper"] {
            border: none !important;
            background: transparent !important;
            box-shadow: none !important;
            padding: 0 !important;
        }
        [data-testid="stHeader"],
        [data-testid="stToolbar"],
        #MainMenu {
            display: none !important;
            height: 0 !important;
        }

        .stApp {
            background:
                radial-gradient(circle at top right, rgba(37, 211, 102, 0.10), transparent 26%),
                linear-gradient(180deg, #f7f8fc 0%, #f3f5fb 100%);
            color: #1c1d2e;
        }
        .hero-shell {
            background: linear-gradient(135deg, #02312a 0%, #075E54 60%, #128C7E 100%);
            border: 1px solid rgba(255, 255, 255, 0.08);
            border-radius: 12px;
            padding: 0.4rem 1rem;
            box-shadow: 0 15px 35px rgba(2, 49, 42, 0.18);
            color: #ffffff;
            margin-bottom: 0.25rem;
            display: flex;
            flex-direction: row;
            justify-content: space-between;
            align-items: center;
        }
        .hero-title {
            font-size: 1.2rem;
            font-weight: 700;
            margin: 0;
            white-space: nowrap;
        }
        .hero-subtitle {
            font-size: 0.78rem;
            color: rgba(255, 255, 255, 0.72);
            margin: 0;
            text-align: right;
        }
        .panel-card {
            background: rgba(255, 255, 255, 0.92);
            border: 1px solid rgba(88, 95, 155, 0.10);
            border-radius: 12px;
            padding: 0.35rem 0.75rem;
            box-shadow: 0 10px 25px rgba(50, 56, 112, 0.05);
            margin-bottom: 0.3rem;
        }
        .panel-title {
            font-size: 0.88rem;
            font-weight: 700;
            color: #242742;
            margin-bottom: 0.1rem;
        }
        .panel-subtitle {
            font-size: 0.74rem;
            color: #7a7ea2;
            margin-bottom: 0px;
        }
        .action-tile {
            background: linear-gradient(180deg, #fbfbff 0%, #f6f7ff 100%);
            border: 1px solid rgba(108, 90, 255, 0.10);
            border-radius: 12px;
            padding: 0.8rem 0.8rem;
            margin-bottom: 0.5rem;
        }
        .action-row {
            display: flex;
            align-items: center;
            gap: 0.75rem;
        }
        .action-icon {
            width: 2rem;
            height: 2rem;
            border-radius: 999px;
            background: linear-gradient(135deg, #8a6cff 0%, #5d43ea 100%);
            color: #ffffff;
            display: flex;
            align-items: center;
            justify-content: center;
            font-weight: 700;
            font-size: 0.74rem;
            flex-shrink: 0;
        }
        .action-heading {
            font-size: 0.88rem;
            font-weight: 700;
            color: #1d2142;
            margin: 0;
        }
        .action-copy {
            font-size: 0.74rem;
            color: #76799b;
            margin-top: 0.1rem;
        }
        .stat-grid {
            display: grid;
            grid-template-columns: repeat(2, minmax(0, 1fr));
            gap: 0.5rem;
        }
        .stat-tile {
            border-radius: 12px;
            padding: 0.5rem 0.65rem 0.55rem;
            background: linear-gradient(180deg, #ffffff 0%, #f8f9ff 100%);
            border: 1px solid rgba(111, 117, 166, 0.10);
            overflow: visible;
        }
        .stat-label {
            font-size: 0.72rem;
            color: #7f82a4;
            margin-top: 0.12rem;
            white-space: nowrap;
        }
        .stat-value {
            font-size: 1.3rem;
            font-weight: 700;
            color: #232643;
            line-height: 1;
            margin-top: 0.2rem;
        }
        .mini-badge {
            display: inline-flex;
            align-items: center;
            justify-content: center;
            width: 1.35rem;
            height: 1.35rem;
            border-radius: 999px;
            background: rgba(37, 211, 102, 0.12);
            color: #075E54;
            font-size: 0.6rem;
            font-weight: 700;
        }
        .dropzone-card {
            border: 1.5px dashed rgba(37, 211, 102, 0.35);
            background: linear-gradient(180deg, #f8fffe 0%, #f0fdf8 100%);
            border-radius: 14px;
            padding: 0.8rem 0.8rem;
            text-align: center;
            margin-bottom: 0.5rem;
        }
        .dropzone-title {
            font-size: 0.82rem;
            font-weight: 700;
            color: #232643;
            margin-top: 0.4rem;
        }
        .dropzone-copy {
            font-size: 0.72rem;
            color: #7b7ea1;
            margin-top: 0.15rem;
        }
        .required-mark {
            color: #25D366;
            font-weight: 700;
        }
        .preview-card {
            min-height: 70px;
            border-radius: 12px;
            border: 1px solid rgba(111, 117, 166, 0.12);
            background: linear-gradient(180deg, #ffffff 0%, #fafaff 100%);
            display: flex;
            align-items: center;
            justify-content: center;
            color: #8b8ea8;
            text-align: center;
            padding: 0.5rem;
            font-size: 0.85rem;
        }
        .template-shell {
            background: linear-gradient(180deg, #ffffff 0%, #fbfbff 100%);
            border: 1px solid rgba(111, 117, 166, 0.12);
            border-radius: 12px;
            padding: 0.6rem;
            margin-top: 0.5rem;
            margin-bottom: 0.5rem;
        }
        .caption-line {
            font-size: 0.74rem;
            color: #7b7ea1;
            margin-bottom: 0.45rem;
        }
        .status-pill {
            display: inline-block;
            background: rgba(18, 140, 126, 0.10);
            color: #075E54;
            border: 1px solid rgba(18, 140, 126, 0.20);
            border-radius: 999px;
            font-size: 0.68rem;
            font-weight: 600;
            padding: 0.25rem 0.5rem;
            margin-right: 0.35rem;
            margin-bottom: 0.3rem;
        }
        .footer-note {
            text-align: center;
            color: #8d90ad;
            font-size: 0.72rem;
            padding: 0.3rem 0 0.1rem;
        }
        .section-card {
            background: rgba(255, 255, 255, 0.92);
            border: 1px solid rgba(88, 95, 155, 0.10);
            border-radius: 12px;
            padding: 0.35rem 0.75rem 0.25rem;
            box-shadow: 0 10px 25px rgba(50, 56, 112, 0.05);
            margin-bottom: 0.3rem;
        }
        /* ── File Uploader: left-aligned layout (matches Excel uploader) ── */
        div[data-testid="stFileUploader"] {
            display: flex !important;
            flex-direction: column !important;
            align-items: flex-start !important;
            width: 100% !important;
        }
        div[data-testid="stFileUploader"] > label {
            width: 100% !important;
            text-align: left !important;
            color: #3a3f68 !important;
            font-weight: 700 !important;
            font-size: 0.82rem !important;
            margin-bottom: 0.4rem !important;
        }
        /* The dashed drop-zone box */
        div[data-testid="stFileUploader"] section {
            width: 100% !important;
            border-radius: 12px !important;
            border: 1.5px dashed rgba(37, 211, 102, 0.45) !important;
            background: linear-gradient(180deg, #f8fffe 0%, #f0fdf8 100%) !important;
            display: flex !important;
            flex-direction: column !important;
            align-items: flex-start !important;
            justify-content: center !important;
            padding: 0.75rem 1.2rem !important;
            gap: 0 !important;
            text-align: left !important;
            box-sizing: border-box !important;
        }
        /* Inner dropzone – left-aligned */
        div[data-testid="stFileUploader"] [data-testid="stFileUploaderDropzone"] {
            background: transparent !important;
            border: 0 !important;
            display: flex !important;
            flex-direction: column !important;
            align-items: flex-start !important;
            justify-content: center !important;
            width: 100% !important;
            gap: 0 !important;
            padding: 0 !important;
        }
        /* Instructions block – hide icon, centre text */
        div[data-testid="stFileUploaderDropzoneInstructions"] {
            display: flex !important;
            flex-direction: column !important;
            align-items: center !important;
            justify-content: center !important;
            text-align: center !important;
            gap: 0.15rem !important;
            width: 100% !important;
            margin: 0 !important;
        }
        /* Hide the cloud upload SVG icon */
        div[data-testid="stFileUploaderDropzoneInstructions"] svg {
            display: none !important;
        }
        /* "Drag and drop file here" */
        div[data-testid="stFileUploaderDropzoneInstructions"] > div > span {
            color: #232643 !important;
            font-size: 0.82rem !important;
            font-weight: 700 !important;
            display: block !important;
            text-align: center !important;
            visibility: visible !important;
            opacity: 1 !important;
        }
        /* "Limit 200MB per file …" */
        div[data-testid="stFileUploaderDropzoneInstructions"] > div > small {
            color: #7b7ea1 !important;
            font-size: 0.71rem !important;
            display: block !important;
            text-align: center !important;
            visibility: visible !important;
            opacity: 1 !important;
            margin-top: 0.1rem !important;
        }
        /* Browse files button – centred within block */
        div[data-testid="stFileUploader"] button {
            display: block !important;
            margin: 0.6rem auto 0 !important;
            border-radius: 12px !important;
            border: 1px solid rgba(37, 211, 102, 0.25) !important;
            background: linear-gradient(135deg, #25D366 0%, #128C7E 100%) !important;
            color: #ffffff !important;
            font-weight: 700 !important;
            box-shadow: 0 10px 20px rgba(18, 140, 126, 0.18) !important;
        }
        div[data-testid="stFileUploader"] button:hover {
            border-color: rgba(37, 211, 102, 0.4) !important;
            background: linear-gradient(135deg, #2de070 0%, #159e8a 100%) !important;
            color: #ffffff !important;
        }
        /* Cap uploaded preview images */
        div[data-testid="stImage"] img {
            max-height: 80px !important;
            width: auto !important;
            object-fit: contain;
            margin: 0 auto;
        }
        div[data-testid="stTextInput"] input, div[data-testid="stSelectbox"] > div, div[data-testid="stSelectbox"] [data-baseweb="select"] > div {
            border-radius: 12px;
            background: #ffffff;
        }
        div[data-testid="stTextInput"] label {
            color: #3a3f68 !important;
            font-weight: 600 !important;
        }
        div[data-testid="stTextInput"] input {
            color: #1d2142 !important;
            border: 1px solid rgba(111, 117, 166, 0.18);
        }
        div[data-testid="stTextInput"] input:focus {
            border: 1px solid #25D366 !important;
            box-shadow: 0 0 0 1px rgba(37, 211, 102, 0.15) !important;
        }
        div[data-testid="stTextInput"] input:disabled {
            background: #f7f8fd !important;
            color: #5c6184 !important;
            -webkit-text-fill-color: #5c6184 !important;
        }
        .stButton > button {
            border-radius: 12px;
            border: 0;
            font-weight: 600;
            background: linear-gradient(135deg, #25D366 0%, #128C7E 100%);
            color: white;
            box-shadow: 0 12px 24px rgba(18, 140, 126, 0.22);
        }
        .secondary-button .stButton > button {
            background: rgba(37, 211, 102, 0.08);
            color: #075E54;
            box-shadow: none;
            border: 1px solid rgba(37, 211, 102, 0.20);
        }
        div[data-testid="stAlert"] {
            border-radius: 14px;
        }
        div[data-testid="stAlert"] [data-testid="stMarkdownContainer"] p {
            color: #2a2e54 !important;
            font-weight: 500;
        }
        .copy-row {
            display: flex;
            align-items: center;
            gap: 0.65rem;
            margin-top: 0.35rem;
            margin-bottom: 0.2rem;
        }
        .copy-button {
            width: 40px;
            height: 40px;
            border: 1px solid rgba(111, 117, 166, 0.22);
            border-radius: 10px;
            background: #ffffff;
            color: #128C7E;
            font-size: 1rem;
            cursor: pointer;
            box-shadow: 0 8px 18px rgba(50, 56, 112, 0.10);
        }
        .stTabs [data-baseweb="tab-list"] {
            gap: 2.25rem;
            justify-content: center;
            border-bottom: 1px solid rgba(111, 117, 166, 0.12);
            margin-bottom: 0.65rem;
        }
        .stTabs [data-baseweb="tab"] {
            height: 42px;
            padding: 0 0.25rem;
            color: #4b516f;
            font-size: 0.86rem;
            font-weight: 700;
        }
        .stTabs [aria-selected="true"] {
            color: #075E54 !important;
        }
        .inbox-shell {
            display: flex;
            flex-direction: column;
            gap: 0.65rem;
        }
        .inbox-metrics {
            display: grid;
            grid-template-columns: repeat(4, minmax(0, 1fr));
            gap: 0.75rem;
        }
        .inbox-metric-card,
        .inbox-panel,
        .chat-panel,
        .contact-panel {
            background: rgba(255, 255, 255, 0.96);
            border: 1px solid rgba(88, 95, 155, 0.10);
            border-radius: 8px;
            box-shadow: 0 10px 24px rgba(50, 56, 112, 0.05);
        }
        .inbox-metric-card {
            min-height: 88px;
            padding: 0.8rem 0.9rem;
            display: flex;
            align-items: center;
            justify-content: space-between;
            gap: 0.7rem;
        }
        .metric-left {
            display: flex;
            align-items: center;
            gap: 0.75rem;
            min-width: 0;
        }
        .metric-icon {
            width: 38px;
            height: 38px;
            border-radius: 8px;
            display: flex;
            align-items: center;
            justify-content: center;
            font-size: 0.72rem;
            font-weight: 800;
            flex-shrink: 0;
        }
        .metric-icon.green { background: rgba(37, 211, 102, 0.12); color: #079449; }
        .metric-icon.blue { background: rgba(54, 132, 255, 0.12); color: #2b72e8; }
        .metric-icon.violet { background: rgba(127, 87, 241, 0.13); color: #7353db; }
        .metric-title {
            font-size: 0.72rem;
            color: #6f748e;
            line-height: 1.1;
        }
        .metric-number {
            font-size: 1.25rem;
            font-weight: 800;
            color: #172033;
            line-height: 1.1;
            margin-top: 0.2rem;
        }
        .metric-link {
            color: #078a42;
            font-size: 0.68rem;
            font-weight: 800;
            white-space: nowrap;
            align-self: flex-end;
        }
        .inbox-grid {
            display: grid;
            grid-template-columns: minmax(210px, 0.9fr) minmax(420px, 2.1fr) minmax(170px, 0.75fr);
            gap: 0.75rem;
            min-height: 520px;
        }
        .inbox-panel,
        .contact-panel {
            padding: 0.9rem;
            min-height: 520px;
        }
        .inbox-panel-title,
        .contact-panel-title {
            font-size: 0.86rem;
            font-weight: 800;
            color: #172033;
            margin-bottom: 0.75rem;
        }
        .conversation-search {
            height: 36px;
            border: 1px solid rgba(111, 117, 166, 0.16);
            border-radius: 6px;
            color: #9aa0b5;
            font-size: 0.74rem;
            display: flex;
            align-items: center;
            padding: 0 0.7rem;
            margin-bottom: 0.85rem;
        }
        .empty-state {
            min-height: 310px;
            border: 1px dashed rgba(111, 117, 166, 0.20);
            border-radius: 8px;
            display: flex;
            flex-direction: column;
            align-items: center;
            justify-content: center;
            text-align: center;
            color: #8188a1;
            padding: 1rem;
        }
        .empty-state strong {
            color: #2b3148;
            font-size: 0.9rem;
            margin-bottom: 0.25rem;
        }
        .chat-panel {
            min-height: 520px;
            display: flex;
            flex-direction: column;
            overflow: hidden;
        }
        .chat-header {
            height: 64px;
            border-bottom: 1px solid rgba(111, 117, 166, 0.12);
            display: flex;
            align-items: center;
            justify-content: space-between;
            padding: 0 1rem;
        }
        .chat-identity {
            display: flex;
            align-items: center;
            gap: 0.75rem;
        }
        .avatar-empty {
            width: 38px;
            height: 38px;
            border-radius: 999px;
            background: #e8f5ef;
            color: #098f45;
            display: flex;
            align-items: center;
            justify-content: center;
            font-weight: 800;
        }
        .chat-name {
            color: #172033;
            font-size: 0.94rem;
            font-weight: 800;
            line-height: 1.2;
        }
        .chat-phone {
            color: #7c8298;
            font-size: 0.74rem;
        }
        .chat-actions {
            display: flex;
            gap: 0.75rem;
            color: #66708c;
            font-size: 0.9rem;
        }
        .conversation-preview {
            color: #7c8298;
            font-size: 0.7rem;
            padding: 0 0.2rem 0.55rem;
            overflow: hidden;
            text-overflow: ellipsis;
            white-space: nowrap;
        }
        .chat-body {
            flex: 1;
            background: #f7f3ee;
            display: flex;
            align-items: center;
            justify-content: center;
            padding: 1rem;
        }
        .chat-body-live {
            align-items: stretch;
            justify-content: flex-start;
            flex-direction: column;
            gap: 0.55rem;
            overflow-y: auto;
        }
        .message-row {
            display: flex;
            width: 100%;
        }
        .message-out {
            justify-content: flex-end;
        }
        .message-in {
            justify-content: flex-start;
        }
        .message-bubble {
            max-width: 78%;
            border-radius: 8px;
            padding: 0.5rem 0.65rem;
            background: #ffffff;
            color: #172033;
            font-size: 0.8rem;
            box-shadow: 0 5px 14px rgba(50, 56, 112, 0.06);
            overflow-wrap: anywhere;
        }
        .message-out .message-bubble {
            background: #d9fdd3;
        }
        .message-bubble span {
            display: block;
            color: #788094;
            font-size: 0.62rem;
            text-align: right;
            margin-top: 0.25rem;
        }
        .chat-compose {
            height: 58px;
            border-top: 1px solid rgba(111, 117, 166, 0.12);
            display: flex;
            align-items: center;
            gap: 0.65rem;
            padding: 0 0.85rem;
            background: #ffffff;
        }
        .compose-input {
            flex: 1;
            height: 36px;
            border: 1px solid rgba(111, 117, 166, 0.16);
            border-radius: 6px;
            color: #9aa0b5;
            display: flex;
            align-items: center;
            padding: 0 0.75rem;
            font-size: 0.76rem;
        }
        .compose-send {
            height: 36px;
            min-width: 54px;
            border-radius: 6px;
            background: #06a84f;
            color: #ffffff;
            display: flex;
            align-items: center;
            justify-content: center;
            font-size: 0.76rem;
            font-weight: 800;
        }
        .contact-row {
            margin-bottom: 0.85rem;
        }
        .contact-label {
            color: #6f748e;
            font-size: 0.7rem;
            font-weight: 700;
            margin-bottom: 0.2rem;
        }
        .contact-value {
            color: #172033;
            font-size: 0.78rem;
            min-height: 18px;
        }
        .status-chip {
            display: inline-flex;
            border-radius: 999px;
            background: rgba(37, 211, 102, 0.14);
            color: #078a42;
            padding: 0.28rem 0.52rem;
            font-size: 0.68rem;
            font-weight: 800;
        }
        .note-button {
            border: 1px solid rgba(111, 117, 166, 0.16);
            border-radius: 6px;
            padding: 0.45rem 0.65rem;
            display: inline-flex;
            align-items: center;
            gap: 0.35rem;
            color: #26314d;
            font-size: 0.72rem;
            font-weight: 800;
            background: #ffffff;
        }
        @media (max-width: 900px) {
            .inbox-metrics,
            .inbox-grid {
                grid-template-columns: 1fr;
            }
            .inbox-grid,
            .inbox-panel,
            .chat-panel,
            .contact-panel {
                min-height: auto;
            }
            html, body, [data-testid="stAppViewContainer"], .stApp, [data-testid="stMain"], .block-container {
                overflow: auto !important;
                height: auto !important;
                max-height: none !important;
            }
        }
        </style>
        """,
        unsafe_allow_html=True,
    )


def _render_header():
    st.markdown(
        """
        <div class="hero-shell" style="padding: 0; overflow: hidden; flex-direction: column; align-items: stretch;">
            <div style="
                height: 8px;
                background: linear-gradient(90deg, #075E54 0%, #128C7E 40%, #25D366 70%, #7BE495 100%);
                width: 100%;
            "></div>
            <div style="padding: 0.45rem 1rem; display: flex; justify-content: center; align-items: center;">
                <div class="hero-title">WhatsApp Bulk Sender</div>
            </div>
        </div>
        """,
        unsafe_allow_html=True,
    )


def _render_quick_actions():
    st.markdown(
        """
        <div class="panel-card">
            <div class="panel-title">Quick Actions</div>
            <div class="panel-subtitle">Move through the flow without hunting for controls.</div>
            <div class="action-tile">
                <div class="action-row">
                    <div class="action-icon">IMG</div>
                    <div>
                        <div class="action-heading">Create Link</div>
                        <div class="action-copy">Upload an image to Cloudinary and get a public URL.</div>
                    </div>
                </div>
            </div>
            <div class="action-tile">
                <div class="action-row">
                    <div class="action-icon">SEND</div>
                    <div>
                        <div class="action-heading">Send Templates</div>
                        <div class="action-copy">Load Excel contacts and send approved WhatsApp templates.</div>
                    </div>
                </div>
            </div>
        </div>
        """,
        unsafe_allow_html=True,
    )


def _render_stats_overview():
    results = st.session_state.get("last_send_results", [])
    stats = _build_stats(results, st.session_state.get("current_contact_count", 0))

    st.markdown(
        f"""
        <div class="panel-card" style="margin-bottom: 0.5rem;">
            <div class="panel-title">Stats Overview</div>
            <div class="panel-subtitle">Live numbers from the current session.</div>
        </div>
        <div class="stat-grid">
            <div class="stat-tile">
                <div class="mini-badge">CNT</div>
                <div class="stat-value">{stats["contacts"]}</div>
                <div class="stat-label">Total Contacts</div>
            </div>
            <div class="stat-tile">
                <div class="mini-badge">SNT</div>
                <div class="stat-value">{stats["sent"]}</div>
                <div class="stat-label">Messages Sent</div>
            </div>
            <div class="stat-tile">
                <div class="mini-badge">OK</div>
                <div class="stat-value">{stats["delivered"]}</div>
                <div class="stat-label">Successful</div>
            </div>
            <div class="stat-tile">
                <div class="mini-badge">ERR</div>
                <div class="stat-value">{stats["failed"]}</div>
                <div class="stat-label">Failed</div>
            </div>
        </div>
        """,
        unsafe_allow_html=True,
    )


def _render_dashboard():
    st.markdown(
        """
        <div class="panel-card">
            <div class="panel-title">Dashboard Overview</div>
            <div class="panel-subtitle">Manage links, templates, and send WhatsApp messages cleanly.</div>
        </div>
        """,
        unsafe_allow_html=True,
    )

    media_column, send_column = st.columns([1.15, 1], gap="large")

    with media_column:
        _render_cloudinary_panel()

    with send_column:
        _render_send_panel()

def _render_inbox_tab():
    if not is_inbox_database_configured():
        st.info(
            "Connect Supabase to activate the Inbox. Set SUPABASE_URL and SUPABASE_SERVICE_ROLE_KEY, then run database_schema.sql in Supabase."
        )
        _render_inbox_setup_help()
        return

    refresh_column, hint_column = st.columns([0.9, 2.6], gap="small")
    with refresh_column:
        if st.button("Refresh Inbox", use_container_width=True):
            st.rerun()
    with hint_column:
        st.caption(
            "If a recent WhatsApp reply is missing, refresh here and verify the webhook service is running."
        )

    _render_inbox_setup_help()

    try:
        conversations = fetch_conversations()
    except ConversationStoreError as exc:
        st.error(str(exc))
        conversations = []

    selected_conversation = _select_conversation(conversations)
    selected_messages = []
    if selected_conversation:
        try:
            selected_messages = fetch_messages(selected_conversation["id"])
            if selected_conversation.get("unread_count"):
                mark_conversation_read(selected_conversation["id"])
                selected_conversation["unread_count"] = 0
        except ConversationStoreError as exc:
            st.error(str(exc))

    _render_inbox_metrics(conversations)

    inbox_column, chat_column, contact_column = st.columns([0.9, 2.1, 0.75], gap="small")
    with inbox_column:
        _render_conversation_list(conversations, selected_conversation)

    with chat_column:
        _render_chat_panel(selected_conversation, selected_messages)

    with contact_column:
        _render_contact_panel(selected_conversation, selected_messages)


def _render_inbox_setup_help():
    webhook_base_url = os.getenv("PUBLIC_WEBHOOK_BASE_URL", "").strip().rstrip("/")
    incoming_webhook_url = (
        f"{webhook_base_url}/webhook/whatsapp" if webhook_base_url else "https://your-domain/webhook/whatsapp"
    )
    status_webhook_url = (
        f"{webhook_base_url}/webhook/whatsapp/status"
        if webhook_base_url
        else "https://your-domain/webhook/whatsapp/status"
    )
    supabase_ready = "Yes" if is_inbox_database_configured() else "No"
    webhook_ready = "Configured" if webhook_base_url else "Add PUBLIC_WEBHOOK_BASE_URL to .env"

    with st.expander("Inbox setup checklist", expanded=False):
        st.markdown(
            f"""
            **Current status**

            - Supabase connected: `{supabase_ready}`
            - Public webhook base URL: `{webhook_ready}`

            **Required for incoming chats to appear**

            1. Run the FastAPI webhook server: `uvicorn api:app --host 0.0.0.0 --port 8000`
            2. Expose that server on a public HTTPS URL.
            3. In Twilio WhatsApp sandbox or sender configuration, set:
               Incoming message webhook: `{incoming_webhook_url}`
            4. Set message status callback URL: `{status_webhook_url}`
            5. Keep this inbox open and click `Refresh Inbox` after a new reply arrives.
            """
        )


def _select_conversation(conversations):
    if not conversations:
        st.session_state.pop("selected_conversation_id", None)
        return None

    conversation_ids = [conversation["id"] for conversation in conversations]
    selected_id = st.session_state.get("selected_conversation_id")
    if selected_id not in conversation_ids:
        selected_id = conversation_ids[0]
        st.session_state["selected_conversation_id"] = selected_id

    return next(
        conversation for conversation in conversations if conversation["id"] == selected_id
    )


def _render_inbox_metrics(conversations):
    unread_count = sum(int(conversation.get("unread_count") or 0) for conversation in conversations)
    todays_replies = sum(
        1
        for conversation in conversations
        if _is_today(conversation.get("last_message_time"))
    )
    open_count = sum(
        1 for conversation in conversations if conversation.get("status", "open") == "open"
    )
    resolved_count = len(conversations) - open_count

    metrics_html = "".join(
        [
            _metric_card("MSG", "green", "Unread Messages", unread_count),
            _metric_card("RPL", "blue", "Today's Replies", todays_replies),
            _metric_card("OPN", "violet", "Open Conversations", open_count),
            _metric_card("OK", "green", "Resolved", resolved_count),
        ]
    )
    st.markdown(
        f'<div class="inbox-metrics">{metrics_html}</div>',
        unsafe_allow_html=True,
    )


def _render_conversation_list(conversations, selected_conversation):
    st.markdown('<div class="inbox-panel-title">Conversations</div>', unsafe_allow_html=True)
    search_term = st.text_input(
        "Search by name or number",
        key="conversation_search",
        label_visibility="collapsed",
        placeholder="Search by name or number",
    ).strip().lower()

    filtered_conversations = [
        conversation
        for conversation in conversations
        if not search_term
        or search_term in str(conversation.get("customer_name") or "").lower()
        or search_term in str(conversation.get("phone_number") or "").lower()
    ]

    if not filtered_conversations:
        st.markdown(
            """
            <div class="empty-state">
                <strong>No conversations yet</strong>
                <span>Incoming WhatsApp replies will appear here once Twilio is connected.</span>
            </div>
            """,
            unsafe_allow_html=True,
        )
        return

    for conversation in filtered_conversations:
        name = conversation.get("customer_name") or conversation.get("phone_number") or "Unknown"
        unread = int(conversation.get("unread_count") or 0)
        label = f"{name}"
        if unread:
            label = f"{label} ({unread})"

        if st.button(
            label,
            key=f"conversation_{conversation['id']}",
            use_container_width=True,
            type="primary" if selected_conversation and selected_conversation["id"] == conversation["id"] else "secondary",
        ):
            st.session_state["selected_conversation_id"] = conversation["id"]
            st.rerun()

        last_message = html.escape(str(conversation.get("last_message") or ""))
        st.markdown(
            f'<div class="conversation-preview">{last_message or "No message yet"}</div>',
            unsafe_allow_html=True,
        )


def _render_chat_panel(conversation, messages):
    if not conversation:
        st.markdown(
            """
            <div class="chat-panel">
                <div class="chat-header">
                    <div class="chat-identity">
                        <div class="avatar-empty">-</div>
                        <div>
                            <div class="chat-name">Select a conversation</div>
                            <div class="chat-phone">No contact selected</div>
                        </div>
                    </div>
                </div>
                <div class="chat-body"><div class="empty-state"><strong>No messages to show</strong><span>Choose a conversation from the left panel.</span></div></div>
            </div>
            """,
            unsafe_allow_html=True,
        )
        return

    name = html.escape(conversation.get("customer_name") or conversation.get("phone_number") or "Unknown")
    phone = html.escape(conversation.get("phone_number") or "")
    initial = html.escape((name[:1] or "?").upper())
    bubbles = "".join(_message_bubble(message) for message in messages)
    if not bubbles:
        bubbles = '<div class="empty-state"><strong>No messages yet</strong><span>Replies from this contact will appear here.</span></div>'

    st.markdown(
        f"""
        <div class="chat-panel">
            <div class="chat-header">
                <div class="chat-identity">
                    <div class="avatar-empty">{initial}</div>
                    <div>
                        <div class="chat-name">{name}</div>
                        <div class="chat-phone">{phone}</div>
                    </div>
                </div>
                <div class="chat-actions"><span>{html.escape(conversation.get("status") or "open")}</span></div>
            </div>
            <div class="chat-body chat-body-live">{bubbles}</div>
        </div>
        """,
        unsafe_allow_html=True,
    )

    with st.form(key=f"reply_form_{conversation['id']}", clear_on_submit=True):
        reply = st.text_input(
            "Reply",
            placeholder="Type your message...",
            label_visibility="collapsed",
        )
        send_reply = st.form_submit_button("Send", use_container_width=True)

    if send_reply:
        try:
            sent_message = send_whatsapp_text(conversation.get("phone_number"), reply)
            save_outbound_message(
                conversation.get("phone_number"),
                reply,
                sent_message.get("sid", ""),
                sent_message.get("status", "queued"),
            )
            st.success("Reply sent.")
            st.rerun()
        except (ValueError, ConversationStoreError) as exc:
            st.error(str(exc))
        except Exception as exc:
            st.error(f"Unable to send reply: {exc}")


def _render_contact_panel(conversation, messages):
    if not conversation:
        st.markdown(
            """
            <div class="contact-panel-title">Contact Details</div>
            <div class="contact-row"><div class="contact-label">Name</div><div class="contact-value">-</div></div>
            <div class="contact-row"><div class="contact-label">Phone</div><div class="contact-value">-</div></div>
            <div class="contact-row"><div class="contact-label">Status</div><span class="status-chip">No status</span></div>
            """,
            unsafe_allow_html=True,
        )
        return

    name = html.escape(conversation.get("customer_name") or "-")
    phone = html.escape(conversation.get("phone_number") or "-")
    status = html.escape(conversation.get("status") or "open")
    first_contact = html.escape(_format_datetime(conversation.get("created_at")))
    total_messages = len(messages)

    st.markdown(
        f"""
        <div class="contact-panel-title">Contact Details</div>
        <div class="contact-row"><div class="contact-label">Name</div><div class="contact-value">{name}</div></div>
        <div class="contact-row"><div class="contact-label">Phone</div><div class="contact-value">{phone}</div></div>
        <div class="contact-row"><div class="contact-label">Status</div><span class="status-chip">{status}</span></div>
        <div class="contact-row"><div class="contact-label">First Contact</div><div class="contact-value">{first_contact}</div></div>
        <div class="contact-row"><div class="contact-label">Total Messages</div><div class="contact-value">{total_messages}</div></div>
        <div class="contact-row"><div class="contact-label">Campaign</div><div class="contact-value">-</div></div>
        <div class="contact-row"><div class="contact-label">Notes</div><div class="contact-value">No notes yet.</div></div>
        """,
        unsafe_allow_html=True,
    )


def _metric_card(icon, color, title, number):
    return (
        f'<div class="inbox-metric-card">'
        f'<div class="metric-left">'
        f'<div class="metric-icon {color}">{icon}</div>'
        f'<div><div class="metric-title">{title}</div>'
        f'<div class="metric-number">{number}</div></div>'
        f'</div><div class="metric-link">View all</div></div>'
    )


def _message_bubble(message):
    direction = message.get("direction") or "inbound"
    bubble_class = "message-out" if direction == "outbound" else "message-in"
    body = html.escape(str(message.get("body") or ""))
    status = html.escape(str(message.get("status") or ""))
    time_text = html.escape(_format_datetime(message.get("created_at")))
    meta = " · ".join(value for value in [time_text, status] if value)
    return f'<div class="message-row {bubble_class}"><div class="message-bubble"><div>{body}</div><span>{meta}</span></div></div>'


def _is_today(value):
    if not value:
        return False
    try:
        normalized = str(value).replace("Z", "+00:00")
        return datetime.fromisoformat(normalized).date() == datetime.now().date()
    except ValueError:
        return False


def _format_datetime(value):
    if not value:
        return "-"
    try:
        normalized = str(value).replace("Z", "+00:00")
        return datetime.fromisoformat(normalized).strftime("%d %b, %I:%M %p")
    except ValueError:
        return str(value)

def _render_cloudinary_panel():
    st.markdown(
        """
        <div class="section-card">
            <div class="panel-title">Create Public Image Link</div>
            <div class="panel-subtitle">Upload media to Cloudinary and reuse the generated public URL inside your templates.</div>
        </div>
        """,
        unsafe_allow_html=True,
    )

    with st.container(height=270, border=False):
        image_file = st.file_uploader(
            "Upload files here",
            type=["png", "jpg", "jpeg", "webp"],
            key="cloudinary_image_file",
            help="Click to browse local files or drag and drop an image. Supports PNG, JPG, JPEG, and WEBP.",
        )

        if image_file:
            upload_key = f"{image_file.name}:{image_file.size}"
            if upload_key != st.session_state.get("latest_uploaded_image_key"):
                try:
                    with st.spinner("Uploading image to Cloudinary..."):
                        st.session_state["latest_public_url"] = upload_media(image_file)
                    st.session_state["latest_uploaded_image_key"] = upload_key
                    st.markdown(
                        "<div style='background:rgba(0,102,204,0.08);border:1px solid rgba(0,102,204,0.25);border-radius:10px;padding:0.6rem 0.9rem;color:#003d99;font-size:0.84rem;font-weight:500;margin-top:0.3rem;'>Public image link created successfully.</div>",
                        unsafe_allow_html=True,
                    )
                except ValueError as exc:
                    st.error(str(exc))
                except Exception as exc:
                    st.error(f"Cloudinary upload failed: {exc}")
        else:
            st.session_state["latest_uploaded_image_key"] = ""

        st.markdown("<div class='panel-title' style='font-size:0.92rem;margin-top:0.9rem;'>Generated Public URL</div>", unsafe_allow_html=True)
        _render_copyable_public_url(st.session_state.get("latest_public_url", ""))

        st.markdown("<div class='panel-title' style='font-size:0.92rem;margin-top:0.9rem;'>Image Preview</div>", unsafe_allow_html=True)
        if image_file:
            st.image(image_file, use_container_width=True)
        else:
            st.markdown(
                "<div class='preview-card'>No image selected yet.</div>",
                unsafe_allow_html=True,
            )


def _render_send_panel():
    st.markdown(
        """
        <div class="section-card">
            <div class="panel-title">Send WhatsApp Messages</div>
            <div class="panel-subtitle">Upload contacts, review the approved Twilio template, and send only compliant content.</div>
        </div>
        """,
        unsafe_allow_html=True,
    )

    with st.container(border=False):
        uploaded_file = st.file_uploader(
            "Upload Excel file *",
            type=["xlsx"],
            help=(
                "Required columns: countryco and PhoneNumber. Optional columns: firstname, lastname, and any template-specific fields."
            ),
            key="contacts_file",
        )
        content_sid = st.text_input(
            "Twilio Content SID *",
            placeholder="HX1234567890abcdef...",
            help="Paste the approved Twilio Content SID that starts with HX.",
            key="content_sid_input",
        )

        contacts = _load_contacts(uploaded_file)
        template_details, template_error = _load_template_details(content_sid)

        _render_status_hints(uploaded_file, content_sid, template_error)

        if contacts:
            with st.expander("Preview contacts", expanded=False):
                preview_data = [
                    {
                        "Name": contact["name"],
                        "WhatsApp Number": contact["whatsapp_number"],
                    }
                    for contact in contacts
                ]
                st.dataframe(pd.DataFrame(preview_data), use_container_width=True)

        variable_mappings = {}
        available_contact_fields = _get_available_contact_fields(contacts)

        if template_details:
            variable_mappings = _render_template_details(
                template_details,
                available_contact_fields,
                st.session_state.get("latest_public_url", ""),
            )

        send_button = st.button(
            "Send WhatsApp Template",
            type="primary",
            use_container_width=True,
            disabled=(
                not uploaded_file
                or not contacts
                or not content_sid.strip()
                or bool(template_error)
            ),
        )

        if send_button:
            with st.spinner("Sending WhatsApp messages..."):
                results = send_bulk_whatsapp_templates(
                    contacts,
                    content_sid.strip(),
                    variable_mappings,
                )
            st.session_state["last_send_results"] = results
            _render_send_results(results)

        elif st.session_state.get("last_send_results"):
            _render_send_results(st.session_state["last_send_results"], show_banner=False)


def _load_contacts(uploaded_file):
    if not uploaded_file:
        st.session_state["current_contact_count"] = 0
        return []

    try:
        contacts = read_contacts_from_excel(uploaded_file)
        st.session_state["current_contact_count"] = len(contacts)
        st.markdown(
            f"<div style='background:rgba(0,102,204,0.08);border:1px solid rgba(0,102,204,0.25);border-radius:10px;padding:0.6rem 0.9rem;color:#003d99;font-size:0.84rem;font-weight:500;'>Loaded {len(contacts)} contact(s) from the Excel file.</div>",
            unsafe_allow_html=True,
        )
        return contacts
    except ValueError as exc:
        st.session_state["current_contact_count"] = 0
        st.error(str(exc))
        return []


def _load_template_details(content_sid):
    normalized_sid = str(content_sid).strip()
    if not normalized_sid:
        st.session_state["template_cache_sid"] = ""
        st.session_state["template_cache"] = None
        st.session_state["template_error"] = ""
        return None, ""

    if (
        normalized_sid == st.session_state.get("template_cache_sid")
        and (
            st.session_state.get("template_cache") is not None
            or st.session_state.get("template_error")
        )
    ):
        return (
            st.session_state.get("template_cache"),
            st.session_state.get("template_error", ""),
        )

    try:
        template_details = fetch_content_template(normalized_sid)
        st.session_state["template_cache_sid"] = normalized_sid
        st.session_state["template_cache"] = template_details
        st.session_state["template_error"] = ""
        return template_details, ""
    except ValueError as exc:
        error_message = str(exc)
        st.session_state["template_cache_sid"] = normalized_sid
        st.session_state["template_cache"] = None
        st.session_state["template_error"] = error_message
        return None, error_message


def _render_status_hints(uploaded_file, content_sid, template_error):
    if template_error:
        st.error(template_error)


def _render_template_details(template_details, available_contact_fields, latest_public_url):
    friendly_name = template_details.get("friendly_name") or "Untitled template"
    language = template_details.get("language") or "unknown"
    st.markdown(
        f"""
        <div class="template-shell">
            <span class="status-pill">Template: {friendly_name}</span>
            <span class="status-pill">SID: {template_details.get("sid", "")}</span>
            <span class="status-pill">Language: {language}</span>
        </div>
        """,
        unsafe_allow_html=True,
    )

    template_types = template_details.get("types", {})
    body_text = (
        template_types.get("twilio/text", {}).get("body")
        or template_types.get("whatsapp/text", {}).get("body")
        or template_types.get("whatsapp/card", {}).get("body")
        or ""
    )
    if body_text:
        st.code(body_text, language="text")

    # Auto-build mappings using each variable's Twilio template default value.
    # _build_content_variables falls back to default_value when source_type is "default",
    # so Twilio receives properly populated ContentVariables without needing user input.
    template_variables = template_details.get("variables", {})
    variable_mappings = {}
    for variable_key, default_value in template_variables.items():
        variable_mappings[str(variable_key)] = {
            "source_type": "default",
            "default_value": str(default_value).strip(),
        }
    return variable_mappings


def _render_send_results(results, show_banner=True):
    successful_count = sum(1 for result in results if result["success"])
    failed_count = len(results) - successful_count

    if show_banner:
        if failed_count:
            st.warning(f"Sent {successful_count} message(s), {failed_count} failed.")
        else:
            st.success(f"Sent {successful_count} message(s) successfully.")

    st.dataframe(pd.DataFrame(results), use_container_width=True)

    unique_errors = sorted({result["error"] for result in results if result["error"]})
    for error in unique_errors:
        st.error(error)

    if any("21656" in error for error in unique_errors):
        st.info(
            "Twilio 21656 means the ContentVariables payload is invalid. Blank values are skipped, line breaks are sanitized, and every mapped variable should match your approved template."
        )


def _get_available_contact_fields(contacts):
    if not contacts:
        return []

    return sorted(
        {
            key
            for contact in contacts
            for key in contact.keys()
            if key != "name"
        }
    )


def _default_field_index(available_contact_fields):
    if not available_contact_fields:
        return 0

    if "first_name" in available_contact_fields:
        return available_contact_fields.index("first_name")

    return 0


def _build_stats(results, current_contact_count):
    contacts = current_contact_count or len(results)
    sent = sum(1 for result in results if result.get("sid"))
    failed = sum(1 for result in results if not result.get("success"))
    delivered = sum(
        1
        for result in results
        if result.get("success") and result.get("status") != "failed"
    )

    return {
        "contacts": contacts,
        "sent": sent,
        "failed": failed,
        "delivered": delivered,
    }


def _render_stat_card(label, value, caption):
    st.markdown(
        f"""
        <div class="stat-tile">
            <div class="mini-badge">{label}</div>
            <div class="stat-value">{value}</div>
            <div class="stat-label">{caption}</div>
        </div>
        """,
        unsafe_allow_html=True,
    )


def _render_copyable_public_url(public_url):
    display_value = public_url or "Cloudinary URL will appear here after upload."
    safe_value = (
        display_value.replace("&", "&amp;")
        .replace("<", "&lt;")
        .replace(">", "&gt;")
        .replace('"', "&quot;")
    )
    escaped_js_value = (public_url or "").replace("\\", "\\\\").replace("'", "\\'")
    components.html(
        f"""
        <div style="display:flex; align-items:center; gap:8px; width:100%; overflow:visible; font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, Helvetica, Arial, sans-serif;">
            <div style="
                flex:1;
                min-width:0;
                height:42px;
                display:flex;
                align-items:center;
                padding:0 14px;
                border:1px solid rgba(111, 117, 166, 0.18);
                border-radius:10px;
                background:#f7f8fd;
                color:#128C7E;
                font-size:0.86rem;
                white-space:nowrap;
                overflow:hidden;
                text-overflow:ellipsis;
                box-sizing:border-box;
                font-weight: 500;
            ">{safe_value}</div>
            <button
                id="copyBtn"
                onclick="copyPublicUrl()"
                title="Copy public URL"
                style="
                    width:42px;
                    min-width:42px;
                    height:42px;
                    border:none;
                    border-radius:10px;
                    background: linear-gradient(135deg, #25D366 0%, #128C7E 100%);
                    color:#ffffff;
                    cursor:pointer;
                    box-shadow: 0 8px 18px rgba(18, 140, 126, 0.18);
                    display:flex;
                    align-items:center;
                    justify-content:center;
                    flex-shrink:0;
                    transition: all 0.2s ease;
                "
                onmouseover="this.style.transform='scale(1.05)'; this.style.boxShadow='0 10px 22px rgba(18, 140, 126, 0.25)';"
                onmouseout="this.style.transform='scale(1)'; this.style.boxShadow='0 8px 18px rgba(18, 140, 126, 0.18)';"
            >
                <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5" stroke-linecap="round" stroke-linejoin="round" style="display:block;">
                    <rect x="9" y="9" width="13" height="13" rx="2" ry="2"></rect>
                    <path d="M5 15H4a2 2 0 0 1-2-2V4a2 2 0 0 1 2-2h9a2 2 0 0 1 2 2v1"></path>
                </svg>
            </button>
        </div>
        <script>
        function copyPublicUrl() {{
            const value = '{escaped_js_value}';
            if (!value) {{
                return;
            }}
            
            function showSuccess() {{
                const btn = document.getElementById('copyBtn');
                const origContent = btn.innerHTML;
                btn.innerHTML = `<svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="3" stroke-linecap="round" stroke-linejoin="round"><polyline points="20 6 9 17 4 12"></polyline></svg>`;
                btn.style.background = '#075E54';
                setTimeout(function() {{
                    btn.innerHTML = origContent;
                    btn.style.background = 'linear-gradient(135deg, #25D366 0%, #128C7E 100%)';
                }}, 1500);
            }}

            if (navigator.clipboard && navigator.clipboard.writeText) {{
                navigator.clipboard.writeText(value).then(showSuccess).catch(function() {{
                    fallbackCopy(value, showSuccess);
                }});
            }} else {{
                fallbackCopy(value, showSuccess);
            }}
        }}
        
        function fallbackCopy(text, callback) {{
            const textArea = document.createElement("textarea");
            textArea.value = text;
            textArea.style.position = "fixed";
            textArea.style.opacity = "0";
            document.body.appendChild(textArea);
            textArea.focus();
            textArea.select();
            try {{
                document.execCommand('copy');
                callback();
            }} catch (err) {{}}
            document.body.removeChild(textArea);
        }}
        </script>
        """,
        height=52,
    )


def _render_login_page():
    st.markdown(
        """
        <style>
        div[data-testid="stHorizontalBlock"] {
            justify-content: center !important;
        }
        form[data-testid="stForm"] {
            background: #ffffff !important;
            padding: 2.1rem 2.2rem 2rem !important;
            border-radius: 16px !important;
            box-shadow: 0 18px 45px rgba(32, 38, 76, 0.10) !important;
            border: 1px solid rgba(111, 117, 166, 0.14) !important;
            max-width: 420px !important;
            width: 100% !important;
            margin: 1.9rem auto !important;
        }
        .login-logo-wrapper {
            display: flex;
            justify-content: center;
            margin-bottom: 0.6rem;
        }
        .login-logo-circle {
            width: 58px;
            height: 58px;
            border-radius: 50%;
            background: #e8f5ef;
            display: flex;
            align-items: center;
            justify-content: center;
            border: 1px solid rgba(37, 211, 102, 0.20);
        }
        .login-logo-circle img {
            width: 32px;
            height: 32px;
        }
        .login-subtitle {
            text-align: center;
            color: #707795;
            font-size: 0.82rem;
            margin-bottom: 1.75rem;
            font-weight: 500;
        }
        .input-label {
            font-size: 0.78rem;
            font-weight: 700;
            color: #242742;
            margin-bottom: 0.4rem;
            margin-top: 1rem;
        }
        div[data-testid="stForm"] div[data-testid="stTextInput"] > div[data-baseweb="input"],
        div[data-testid="stForm"] div[data-testid="stTextInput"] [data-baseweb="base-input"],
        div[data-testid="stForm"] div[data-testid="stTextInput"] input {
            background: #ffffff !important;
            color: #1d2142 !important;
            -webkit-text-fill-color: #1d2142 !important;
        }
        div[data-testid="stForm"] div[data-testid="stTextInput"] > div[data-baseweb="input"] {
            border-radius: 10px !important;
            border: 1px solid rgba(111, 117, 166, 0.24) !important;
            box-shadow: 0 8px 18px rgba(50, 56, 112, 0.05) !important;
            height: 42px !important;
            display: flex !important;
            align-items: center !important;
        }
        div[data-testid="stForm"] div[data-testid="stTextInput"] > div[data-baseweb="input"]:focus-within {
            border-color: rgba(37, 211, 102, 0.70) !important;
            box-shadow: 0 0 0 3px rgba(37, 211, 102, 0.12) !important;
        }
        div[data-testid="stForm"] div[data-testid="stTextInput"] input {
            border: none !important;
            height: 100% !important;
            box-shadow: none !important;
        }
        div[data-testid="stForm"] div[data-testid="stTextInput"] input::placeholder {
            color: transparent !important;
        }
        div[data-testid="stForm"] div[data-testid="stTextInput"] input:-webkit-autofill,
        div[data-testid="stForm"] div[data-testid="stTextInput"] input:-webkit-autofill:hover,
        div[data-testid="stForm"] div[data-testid="stTextInput"] input:-webkit-autofill:focus {
            box-shadow: 0 0 0 1000px #ffffff inset !important;
            -webkit-box-shadow: 0 0 0 1000px #ffffff inset !important;
            -webkit-text-fill-color: #1d2142 !important;
            caret-color: #1d2142 !important;
        }
        div[data-testid="stForm"] div[data-testid="stTextInput"] button {
            background: transparent !important;
            color: #128C7E !important;
            border: 0 !important;
            border-radius: 8px !important;
            box-shadow: none !important;
            height: 30px !important;
            min-width: 30px !important;
            width: 30px !important;
            margin-left: auto !important;
            margin-right: 6px !important;
            padding: 0 !important;
            flex-shrink: 0 !important;
            display: flex !important;
            align-items: center !important;
            justify-content: center !important;
            align-self: center !important;
        }
        div[data-testid="stForm"] div[data-testid="stTextInput"] button:hover {
            background: rgba(37, 211, 102, 0.10) !important;
            color: #075E54 !important;
        }
        div[data-testid="stFormSubmitButton"] button {
            border-radius: 10px !important;
            border: 0 !important;
            font-weight: 700 !important;
            background: linear-gradient(135deg, #25D366 0%, #128C7E 100%) !important;
            color: #ffffff !important;
            box-shadow: 0 12px 24px rgba(18, 140, 126, 0.20) !important;
            height: 44px !important;
            font-size: 0.88rem !important;
            margin-top: 0 !important;
        }
        div[data-testid="stFormSubmitButton"] button:hover {
            background: linear-gradient(135deg, #2de070 0%, #159e8a 100%) !important;
            box-shadow: 0 14px 28px rgba(18, 140, 126, 0.28) !important;
        }
        </style>
        """,
        unsafe_allow_html=True,
    )

    _, col, _ = st.columns([1, 1.25, 1])
    with col:
        with st.form("login_form", clear_on_submit=False):
            st.markdown(
                """
                <div class="login-logo-wrapper">
                    <div class="login-logo-circle">
                        <img src="https://upload.wikimedia.org/wikipedia/commons/6/6b/WhatsApp.svg" />
                    </div>
                </div>
                <div class="login-subtitle">Login to your account to continue</div>
                """,
                unsafe_allow_html=True,
            )

            st.markdown('<div class="input-label">Username</div>', unsafe_allow_html=True)
            username = st.text_input(
                "Username",
                placeholder="",
                label_visibility="collapsed",
                key="login_username_input",
            )

            st.markdown('<div class="input-label">Password</div>', unsafe_allow_html=True)

            password = st.text_input(
                "Password",
                type="password",
                placeholder="",
                label_visibility="collapsed",
                key="login_password_input",
            )
            submit = st.form_submit_button("Login", use_container_width=True)

            if submit:
                if username == "Chips_Express" and password == "Chips@123!":
                    st.session_state["logged_in"] = True
                    st.rerun()
                else:
                    st.error("Invalid username or password.")


if __name__ == "__main__":
    main()
















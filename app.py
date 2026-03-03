import streamlit as st
import os
import re
import json
import time
import boto3
from tavily import TavilyClient
from utils.analyzer import perform_gap_analysis
from dotenv import load_dotenv
from tenacity import retry, stop_after_attempt, wait_exponential

load_dotenv()

st.set_page_config(page_title="IdeaForge | Analysis", layout="wide", initial_sidebar_state="collapsed")

bedrock = boto3.client(
    service_name="bedrock-runtime",
    region_name=os.getenv("AWS_REGION", "us-east-1"),
    aws_access_key_id=os.getenv("AWS_ACCESS_KEY_ID"),
    aws_secret_access_key=os.getenv("AWS_SECRET_ACCESS_KEY"),
)
tavily = TavilyClient(api_key=os.getenv("TAVILY_API_KEY"))

LANDER_URL = "https://YOUR-LANDER.vercel.app"

st.markdown("""
<style>
    @import url('https://fonts.googleapis.com/css2?family=Inter:wght@300;400;500;600;700;800&display=swap');

    #MainMenu {visibility: hidden;}
    footer {visibility: hidden;}
    header {visibility: hidden;}

    .block-container {
        padding-top: 2rem;
        padding-bottom: 2rem;
        padding-left: 2rem;
        padding-right: 2rem;
        max-width: 800px;
    }

    html, body, [class*="css"] {
        font-family: 'Inter', sans-serif;
    }

    .stApp {
        background-color: #f8f8f6;
        min-height: 100vh;
    }

    h1, h2, h3 {
        font-weight: 800;
        letter-spacing: -0.025em;
        color: #1e293b !important;
    }

    .stProgress > div > div > div > div {
        background: linear-gradient(90deg, #f59e0b, #fbbf24);
    }

    .loading-card {
        background: rgba(255, 255, 255, 0.8);
        backdrop-filter: blur(16px);
        border: 1px solid #e2e8f0;
        border-radius: 1.5rem;
        padding: 3rem;
        text-align: center;
        box-shadow: 0 10px 25px -5px rgba(0, 0, 0, 0.06);
    }

    .status-badge {
        display: inline-block;
        padding: 0.5rem 1.25rem;
        border-radius: 9999px;
        font-size: 0.8rem;
        font-weight: 600;
        text-transform: uppercase;
        letter-spacing: 0.05em;
        margin: 0.25rem;
    }

    .badge-yellow {
        background: rgba(245, 158, 11, 0.12);
        color: #92400e;
        border: 1px solid rgba(245, 158, 11, 0.35);
    }

    .badge-slate {
        background: rgba(100, 116, 139, 0.1);
        color: #475569;
        border: 1px solid rgba(100, 116, 139, 0.25);
    }

    .badge-green {
        background: rgba(16, 185, 129, 0.1);
        color: #065f46;
        border: 1px solid rgba(16, 185, 129, 0.3);
    }

    @keyframes float {
        0%, 100% { transform: translateY(0); }
        50% { transform: translateY(-10px); }
    }
    .floating { animation: float 3s ease-in-out infinite; }

    @keyframes pulse {
        0%, 100% { opacity: 1; }
        50% { opacity: 0.5; }
    }
    .pulsing { animation: pulse 2s ease-in-out infinite; }

    .streamlit-expanderHeader {
        background: white !important;
        border: 1px solid #e2e8f0 !important;
        border-radius: 0.75rem !important;
        color: #1e293b !important;
    }
    .streamlit-expanderContent {
        background: #fafafa !important;
        border: 1px solid #e2e8f0 !important;
        border-radius: 0 0 0.75rem 0.75rem !important;
    }

    .stMarkdown h2 {
        color: #d97706 !important;
        border-bottom: 2px solid rgba(245, 158, 11, 0.15);
        padding-bottom: 0.4rem;
        margin-top: 1.75rem;
    }
    .stMarkdown h3 {
        color: #1e293b !important;
        margin-top: 1.25rem;
    }
    .stMarkdown p, .stMarkdown li {
        color: #475569 !important;
        line-height: 1.75;
    }
    .stMarkdown strong {
        color: #1e293b !important;
    }
    .stMarkdown ul {
        padding-left: 1.25rem;
    }
    .stMarkdown li {
        margin-bottom: 0.4rem;
    }
</style>
""", unsafe_allow_html=True)


def invoke_nova(prompt: str, max_tokens: int = 800, temperature: float = 0.7) -> str:
    body = json.dumps({
        "messages": [{"role": "user", "content": [{"text": prompt}]}],
        "inferenceConfig": {"max_new_tokens": max_tokens, "temperature": temperature}
    })
    response = bedrock.invoke_model(
        modelId="amazon.nova-lite-v2:0",
        body=body
    )
    result = json.loads(response["body"].read())
    return result["output"]["message"]["content"][0]["text"]


@retry(wait=wait_exponential(multiplier=2, min=15, max=60), stop=stop_after_attempt(3))
def summarize_source(title, raw_text, topic):
    content_safe = raw_text[:4000]
    prompt = f"""
You are a Content Extraction Agent. Create a concise Topic Map of this article.

ARTICLE: {title}
FOCUS: {topic}
CONTENT: {content_safe}

INSTRUCTIONS:
1. List the main topics covered as headings.
2. Provide 2 sentences of detail per heading.
3. Keep the total output brief (max 300 words).
"""
    return invoke_nova(prompt, max_tokens=600, temperature=0.7)


def clean_web_text(text):
    if not text:
        return ""
    text = re.sub(r'https?://\S+|www\.\S+', '', text)
    text = re.sub(r'\s+', ' ', text)
    return text.strip()


# --- GET TOPIC ---
query_params = st.query_params
topic = query_params.get("topic", "").strip()

# --- NO TOPIC ---
if not topic:
    st.markdown(f"""
    <div style='text-align: center; padding: 6rem 2rem;'>
        <div style='font-size: 2rem; font-weight: 800; margin-bottom: 1rem; color: #1e293b;'>
            Idea<span style='color:#f59e0b;'>Forge</span>
        </div>
        <p style='color: #64748b; margin-bottom: 2rem; font-size: 1rem;'>
            Please use the landing page to submit a topic for analysis.
        </p>
        <a href='{LANDER_URL}' style='
            display: inline-block;
            background: #f59e0b;
            color: #1e293b;
            padding: 0.75rem 2rem;
            border-radius: 9999px;
            font-weight: 700;
            text-decoration: none;
            font-size: 0.9rem;
        '>← Back to IdeaForge</a>
    </div>
    """, unsafe_allow_html=True)
    st.stop()

# --- ANALYSIS PAGE ---

# Back link
st.markdown(f"""
<a href='{LANDER_URL}' style='
    display: inline-flex;
    align-items: center;
    gap: 6px;
    color: #94a3b8;
    font-size: 0.85rem;
    text-decoration: none;
    margin-bottom: 1rem;
    font-family: Inter, sans-serif;
'>← Back to IdeaForge</a>
""", unsafe_allow_html=True)

# Header
st.markdown(f"""
<div style='text-align: center; padding: 1rem 0 2rem 0;'>
    <div style='font-size: 1.4rem; font-weight: 800; margin-bottom: 0.5rem; color: #1e293b;'>
        Idea<span style='color:#f59e0b;'>Forge</span>
    </div>
    <h1 style='font-size: 1.8rem; margin-bottom: 0.5rem; color: #1e293b;'>Your Writing Guide</h1>
    <p style='color: #64748b;'>Topic: <strong style='color: #d97706;'>{topic}</strong></p>
</div>
""", unsafe_allow_html=True)

# Loading UI
loading_container = st.empty()

with loading_container.container():
    st.markdown("""
    <div class='loading-card'>
        <div style='font-size: 4rem; margin-bottom: 1.5rem;' class='floating'>🔍</div>
        <h2 style='color: #1e293b; margin-bottom: 1rem;'>Building Your Writing Guide</h2>
        <p style='color: #64748b; margin-bottom: 2rem;'>Scanning existing articles and identifying content gaps...</p>
    </div>
    """, unsafe_allow_html=True)

    c1, c2, c3 = st.columns(3)
    with c1:
        st.markdown("<div style='text-align:center'><span class='status-badge badge-yellow pulsing'>🛡️ Aggregating</span></div>", unsafe_allow_html=True)
    with c2:
        st.markdown("<div style='text-align:center'><span class='status-badge badge-slate'>🎯 Analyzing</span></div>", unsafe_allow_html=True)
    with c3:
        st.markdown("<div style='text-align:center'><span class='status-badge badge-green'>⚡ Synthesizing</span></div>", unsafe_allow_html=True)

    progress_bar = st.progress(0)

try:
    # Step 1: Fetch
    progress_bar.progress(10)
    search_result = tavily.search(query=topic, max_results=5, include_raw_content=True)
    raw_articles = search_result.get('results', [])

    if not raw_articles:
        loading_container.empty()
        st.markdown(f"""
        <div style='text-align:center; padding: 3rem 2rem;'>
            <div style='font-size:2.5rem; margin-bottom:1rem;'>🔎</div>
            <h3 style='color:#1e293b; margin-bottom:0.75rem;'>No articles found</h3>
            <p style='color:#64748b; margin-bottom:1.5rem; font-size:0.9rem;'>
                We couldn't find content on this topic. Try rephrasing or using a broader term.
            </p>
            <a href='{LANDER_URL}' style='
                display: inline-block;
                background: #f59e0b;
                color: #1e293b;
                padding: 0.65rem 1.75rem;
                border-radius: 9999px;
                font-weight: 700;
                text-decoration: none;
                font-size: 0.875rem;
            '>← Try a different topic</a>
        </div>
        """, unsafe_allow_html=True)
        st.stop()

    # Step 2: Summarize
    valid_summaries = []
    progress_increment = 60 / len(raw_articles)
    current_progress = 10

    for i, a in enumerate(raw_articles):
        clean_txt = clean_web_text(a.get('raw_content') or a.get('content'))
        summary = summarize_source(a['title'], clean_txt, topic)
        valid_summaries.append({
            "title": a['title'],
            "url": a['url'],
            "content": summary
        })
        current_progress += progress_increment
        progress_bar.progress(int(current_progress))
        if i < len(raw_articles) - 1:
            time.sleep(3)

    # Step 3: Gap analysis
    progress_bar.progress(75)
    guide = perform_gap_analysis(valid_summaries, topic)
    progress_bar.progress(100)

    time.sleep(0.5)
    loading_container.empty()

    # Results hint bar
    st.markdown("""
    <div style='background:#fef9c3; border-left:3px solid #f59e0b;
                border-radius:0.75rem; padding:1rem 1.25rem; margin-bottom:1.5rem;'>
        <p style='color:#92400e; font-size:0.875rem; margin:0;'>
            ✏️ Use this guide to write your blog — these are directions, not drafts.
        </p>
    </div>
    """, unsafe_allow_html=True)

    st.markdown(guide)

    with st.expander("📚 Articles analyzed"):
        for s in valid_summaries:
            st.markdown(f"- [{s['title']}]({s['url']})")

    st.markdown("""
    <div style='text-align:center; padding:3rem 0 1rem; color:#94a3b8;
                font-size:0.8rem; margin-top:2rem;'>
        Powered by <strong style='color:#64748b;'>Amazon Bedrock (Nova 2 Lite)</strong> &amp; Tavily
    </div>
    """, unsafe_allow_html=True)

except Exception:
    loading_container.empty()
    st.markdown(f"""
    <div style='text-align:center; padding: 3rem 2rem;'>
        <div style='font-size:2.5rem; margin-bottom:1rem;'>⚠️</div>
        <h3 style='color:#1e293b; margin-bottom:0.75rem;'>Something went wrong</h3>
        <p style='color:#64748b; margin-bottom:1.5rem; font-size:0.9rem;'>
            We hit an issue analyzing this topic. Please try again with a different topic.
        </p>
        <a href='{LANDER_URL}' style='
            display: inline-block;
            background: #f59e0b;
            color: #1e293b;
            padding: 0.65rem 1.75rem;
            border-radius: 9999px;
            font-weight: 700;
            text-decoration: none;
            font-size: 0.875rem;
        '>← Try a different topic</a>
    </div>
    """, unsafe_allow_html=True)

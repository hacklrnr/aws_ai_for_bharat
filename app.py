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
    region_name=os.getenv("AWS_REGION", "us-east-1")
)
tavily = TavilyClient(api_key=os.getenv("TAVILY_API_KEY"))

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

    /* Light Theme Landing Page Match */
    .stApp {
        background-color: #f8f8f6;
        min-height: 100vh;
    }

    h1, h2, h3, p, li, span {
        color: #1e293b !important;
    }

    h1, h2, h3 {
        font-weight: 800;
        letter-spacing: -0.025em;
    }

    /* Progress bar */
    .stProgress > div > div > div > div {
        background: linear-gradient(90deg, #f59e0b, #fbbf24);
    }

    /* Glass Loading card */
    .loading-card {
        background: rgba(255, 255, 255, 0.65);
        backdrop-filter: blur(16px);
        border: 1px solid rgba(255, 255, 255, 0.8);
        border-radius: 1.5rem;
        padding: 3rem;
        text-align: center;
        box-shadow: 0 10px 25px -5px rgba(0, 0, 0, 0.05);
    }

    /* Status badges */
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
        background: rgba(245, 158, 11, 0.1);
        color: #92400e;
        border: 1px solid rgba(245, 158, 11, 0.3);
    }

    .badge-slate {
        background: rgba(148, 163, 184, 0.1);
        color: #475569;
        border: 1px solid rgba(148, 163, 184, 0.3);
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

    /* Streamlit expander */
    .streamlit-expanderHeader {
        background: white !important;
        border: 1px solid #e2e8f0 !important;
        border-radius: 0.75rem !important;
        color: #1e293b !important;
    }

    /* Markdown styling */
    .stMarkdown h2 {
        color: #f59e0b !important;
        border-bottom: 2px solid rgba(245,158,11,0.1);
        padding-bottom: 0.4rem;
        margin-top: 1.75rem;
    }
    .stMarkdown p, .stMarkdown li {
        color: #475569 !important;
    }
</style>
""", unsafe_allow_html=True)

# (Remainder of functions summarize_source, invoke_nova, clean_web_text remain identical)

def invoke_nova(prompt: str, max_tokens: int = 800, temperature: float = 0.7) -> str:
    body = json.dumps({
        "messages": [{"role": "user", "content": [{"text": prompt}]}],
        "inferenceConfig": {"max_new_tokens": max_tokens, "temperature": temperature}
    })
    response = bedrock.invoke_model(modelId="global.amazon.nova-2-lite-v1:0", body=body)
    result = json.loads(response["body"].read())
    return result["output"]["message"]["content"][0]["text"]

@retry(wait=wait_exponential(multiplier=2, min=15, max=60), stop=stop_after_attempt(3))
def summarize_source(title, raw_text, topic):
    content_safe = raw_text[:4000]
    prompt = f"You are a Content Extraction Agent. Create a concise Topic Map.\n\nARTICLE: {title}\nFOCUS: {topic}\nCONTENT: {content_safe}\n\nINSTRUCTIONS:\n1. List headings.\n2. 2 sentences detail per heading.\n"
    return invoke_nova(prompt, max_tokens=600, temperature=0.7)

def clean_web_text(text):
    if not text: return ""
    text = re.sub(r'https?://\S+|www\.\S+', '', text)
    text = re.sub(r'\s+', ' ', text)
    return text.strip()

query_params = st.query_params
topic = query_params.get("topic", "")

if not topic:
    st.markdown("<div style='text-align: center; padding: 4rem 2rem;'><h1>IdeaForge</h1><p>Please use the landing page.</p></div>", unsafe_allow_html=True)
else:
    # Header display
    st.markdown(f"""
    <div style='text-align: center; padding: 1rem 0 2rem 0;'>
        <div style='font-size: 1.4rem; font-weight: 800; margin-bottom: 0.5rem; color: #1e293b;'>
            Idea<span style='color:#f59e0b;'>Forge</span>
        </div>
        <h1 style='font-size: 1.8rem; margin-bottom: 0.5rem; color: #1e293b;'>Your Writing Guide</h1>
        <p style='color: #64748b;'>Topic: <strong style='color: #f59e0b;'>{topic}</strong></p>
    </div>
    """, unsafe_allow_html=True)

    loading_container = st.empty()

    with loading_container.container():
        st.markdown("""
        <div class='loading-card'>
            <div style='font-size: 4rem; margin-bottom: 1.5rem;' class='floating'>🔍</div>
            <h2 style='color: #1e293b; margin-bottom: 1rem;'>Building Your Writing Guide</h2>
            <p style='color: #64748b; margin-bottom: 2rem;'>Scanning existing articles and identifying content gaps...</p>
        </div>
        """, unsafe_allow_html=True)
        progress_bar = st.progress(0)

    try:
        search_result = tavily.search(query=topic, max_results=5, include_raw_content=True)
        raw_articles = search_result.get('results', [])

        if not raw_articles:
            loading_container.empty()
            st.error("❌ No articles found.")
        else:
            valid_summaries = []
            for i, a in enumerate(raw_articles):
                clean_txt = clean_web_text(a.get('raw_content') or a.get('content'))
                summary = summarize_source(a['title'], clean_txt, topic)
                valid_summaries.append({"title": a['title'], "url": a['url'], "content": summary})
                progress_bar.progress(int(20 + (i * 15)))
                time.sleep(1)

            guide = perform_gap_analysis(valid_summaries, topic)
            loading_container.empty()

            st.markdown("""
            <div style='background: rgba(245,158,11,0.1); border-left: 3px solid #f59e0b;
                        border-radius: 0.75rem; padding: 1rem 1.25rem; margin-bottom: 1.5rem;'>
                <p style='color: #92400e !important; font-size: 0.875rem; margin: 0;'>
                    ✏️ Use this guide to write your blog — these are directions, not drafts.
                </p>
            </div>
            """, unsafe_allow_html=True)
            st.markdown(guide)

            with st.expander("📚 Articles analyzed"):
                for s in valid_summaries:
                    st.markdown(f"- [{s['title']}]({s['url']})")

    except Exception as e:
        st.error(f"Analysis Failed: {str(e)}")
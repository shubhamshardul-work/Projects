# I Built an Autonomous, Self-Deploying Generative AI News Agent. Here is How You Can Too.

Are you constantly overwhelmed by the sheer volume of AI news dropping every single day? Between new agentic frameworks, massive foundational models, ArXiv papers, and trending GitHub repositories, the signal-to-noise ratio in AI is approaching zero. It feels impossible to keep up.

I wanted a solution that didn't just blindly aggregate RSS feeds, but actively **read, filtered, and curated** the news for me with the discerning eye of a tech journalist. 

So, I built an autonomous GenAI News Agent. 

Every morning at 8:00 AM, my LangGraph-powered agent scours the internet, reads through papers and articles, aggressively discards outdated clickbait, synthesizes the crucial breakthroughs using Google's Gemini 2.5 Flash, emails a beautifully formatted newsletter to my subscribers, and publishes it live on my developer portfolio. No human intervention required.

Here is a step-by-step guide on how I built it using Python, LangGraph, and GitHub Actions, complete with code so you can build your own.

---

## 🏗️ The Architecture: A Directed Graph

To handle the complexity of multi-source fetching and intelligent deduction, I modeled the agent using **LangGraph**. Instead of a brittle, linear script, the pipeline is a Directed Acyclic Graph (DAG) consisting of specialized nodes:

1. **Ingestion Nodes (Parallel):** Fetch data from Tavily (web search), raw RSS feeds (OpenAI, TechCrunch, VentureBeat), ArXiv, GitHub, and Hugging Face.
2. **Aggregation Node:** Combines the distinct data streams into a unified state.
3. **Curator Node (Gemini 2.5 Flash):** Acts as the editor-in-chief, deduplicating stories and filtering out noise.
4. **Summarizer Node (Gemini 2.5 Flash):** Writes the final, high-impact markdown journalism piece.
5. **Distribution Nodes:** One function emails the subscribers; a separate CI/CD pipeline deploys the markdown to a GitHub Pages hosted website.

---

## Step 1: Multi-Source Data Ingestion

The biggest challenge with AI news is that it doesn't live in one place. You need to pull from APIs, Web Searches, and XML Feeds.

Here is a look at the **RSS Node**, which parses standard news feeds, checking the timestamp to strictly enforce a recency window (e.g., only news from the last 48 hours).

```python
import requests
import xml.etree.ElementTree as ET
from datetime import datetime, timedelta, timezone
import email.utils
import re

def rss_node(state: AgentState):
    """Fetches news from hardcoded RSS feeds."""
    days = state.get("days", 2)
    cutoff = datetime.now(timezone.utc) - timedelta(days=days)
    
    feeds = [
        "https://openai.com/blog/rss.xml",
        "https://techcrunch.com/category/artificial-intelligence/feed/",
        "https://venturebeat.com/category/ai/feed/"
    ]
    
    results = []
    for url in feeds:
        try:
            response = requests.get(url, timeout=5)
            if response.status_code == 200:
                root = ET.fromstring(response.content)
                items = list(root.findall('./channel/item'))
                for item in items[:10]:
                    # Strict Recency Check
                    pub_date_el = item.find('pubDate')
                    if pub_date_el is not None and pub_date_el.text:
                        pub_dt = email.utils.parsedate_to_datetime(pub_date_el.text)
                        if pub_dt and pub_dt < cutoff:
                            continue  # Skip old news
                            
                    title = item.find('title').text
                    link = item.find('link').text
                    description = item.find('description').text
                    
                    # Clean HTML artifacts
                    clean_description = re.sub(r'<[^>]+>', '', description)[:300] if description else ""
                    
                    results.append({
                        "title": f"[RSS] {title}", 
                        "url": link, 
                        "summary": clean_description,
                        "source": url
                    })
        except Exception as e:
            print(f"Error fetching RSS {url}: {e}")
            
    return {"rss_news": results[:5]}
```

This node pattern is repeated for ArXiv (via its specific XML Atom feed format), GitHub Trending, and HuggingFace, ensuring we have a wide, deep net of raw data.

---

## Step 2: The LLM Curator (Gemini 2.5 Flash)

Once all the parallel ingestion nodes finish executing, the state object is packed with dozens of uncurated articles. Many will be duplicates (e.g., TechCrunch and VentureBeat covering the same OpenAI release). 

We pass this massive JSON chunk to **Gemini 2.5 Flash**, prompting it to act as an expert curator. 

```python
from langchain_google_genai import ChatGoogleGenerativeAI
from langchain_core.messages import SystemMessage, HumanMessage
import json

def curate_node(state: AgentState):
    """Filters and curates the most important news."""
    days = state.get("days", 2)
    raw_news = state.get("raw_news", [])
    
    llm = ChatGoogleGenerativeAI(
        model="gemini-2.5-flash", 
        google_api_key=os.getenv("GOOGLE_API_KEY"),
        temperature=0 # Keep it highly deterministic
    )
    
    prompt = f"""
    You are an expert AI news curator.
    Evaluate the following list of raw news articles fetched from various sources.
    Select the most important, impactful breakthroughs in Generative AI from the last {days} days.
    
    CRITICAL: Actively filter out outdated news. Discard overlap and deduplicate stories.
    Focus on major releases and frontier models.
    
    News Articles:
    {raw_news}
    
    Return ONLY a valid JSON list of objects containing 'title', 'url', and a short 'summary'.
    """
    
    response = llm.invoke([
        SystemMessage(content="You return ONLY valid JSON and absolutely nothing else."), 
        HumanMessage(content=prompt)
    ])
    
    # Safely extract the JSON array from the response content
    content = response.content.strip()
    start_idx = content.find('[')
    end_idx = content.rfind(']')
    curated = json.loads(content[start_idx:end_idx+1])
        
    return {"curated_news": curated}
```

By explicitly enforcing JSON-only output and strict recency instructions, Gemini turns the firehose of raw data into a distilled list of 3-5 vital updates. A subsequent `summarizer_node` takes this JSON list and rewrites it into an engaging Markdown post.

---

## Step 3: Distribution via Email

Generating the markdown report is only half the battle. Next, the agent reads its subscriber list from an integrated Google Sheet and automatically distributes the newsletter via Python's `smtplib`.

```python
import smtplib
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
import markdown

def email_node(state: AgentState):
    """Sends the final report to all subscribers via email."""
    final_report = state.get("final_report", "")
    sender_email = os.getenv("GMAIL_USER")
    sender_password = os.getenv("GMAIL_APP_PASSWORD")
    
    subscribers = ["subscriber@example.com"] # Fetched dynamically in full code
    
    # Convert Markdown to formatted HTML for the email
    html_content = markdown.markdown(final_report)
    styled_html = f"<html><body>{html_content}</body></html>"
    
    msg = MIMEMultipart()
    msg['From'] = f"GenAI News Agent"
    msg['Subject'] = "🚀 Daily AI Highlights"
    msg.attach(MIMEText(styled_html, 'html'))
    
    # Connect and send via Gmail SMTP
    with smtplib.SMTP_SSL("smtp.gmail.com", 465) as server:
        server.login(sender_email, sender_password)
        # Using BCC to protect subscriber privacy
        server.sendmail(sender_email, [sender_email] + subscribers, msg.as_string())
            
    return {}
```

---

## Step 4: The Final Touch — Automated Deployment

I didn't want to run this script manually on my laptop. I wrapped the entire application in a **GitHub Actions** workflow. 

Every day at 8:00 AM UTC, GitHub spins up an Ubuntu runner, injects my secure API keys, and triggers the `main.py` LangGraph workflow.

```yaml
name: GenAI News Agent CRON
on:
  schedule:
    - cron: '0 8 * * *' # Runs every day at 08:00 UTC
  workflow_dispatch:

jobs:
  run-agent:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      
      - name: Setup Python
        uses: actions/setup-python@v5
        with:
          python-version: '3.11'
          
      - name: Install Dependencies
        run: pip install -r requirements.txt
        
      - name: Run LangGraph Agent
        env:
          GOOGLE_API_KEY: ${{ secrets.GOOGLE_API_KEY }}
          TAVILY_API_KEY: ${{ secrets.TAVILY_API_KEY }}
          GMAIL_USER: ${{ secrets.GMAIL_USER }}
          GMAIL_APP_PASSWORD: ${{ secrets.GMAIL_APP_PASSWORD }}
        run: python main.py
        
      - name: Commit and Push New Report
        run: |
          git config --global user.name "github-actions[bot]"
          git config --global user.email "github-actions[bot]@users.noreply.github.com"
          git add "Gen AI News Agent/reports/" "Gen AI News Agent/state/"
          git commit -m "🤖 Auto-generated GenAI Report"
          git push
```

A secondary GitHub workflow listens for these new markdown reports and automatically rebuilds my static portfolio website. 

The result? Let the robots do the work. The site updates itself, the emails send themselves, and I get a beautifully curated, hype-free summary of the AI landscape delivered directly to my audience every single day.

*If you want to read today's automated report, or see the rest of my portfolio, check out my developer site setup.*

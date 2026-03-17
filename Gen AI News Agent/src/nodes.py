import json
from langchain_community.tools.tavily_search import TavilySearchResults
import os
from langchain_google_genai import ChatGoogleGenerativeAI
from langchain_core.messages import SystemMessage, HumanMessage
from src.state import AgentState

import requests
import xml.etree.ElementTree as ET
from datetime import datetime, timedelta

def tavily_node(state: AgentState):
    """Fetches news via Tavily."""
    days = state.get("days", 2)
    query = state.get("search_query", "latest breakthroughs and news in Generative AI")
    # Append recency constraint to query
    query = f"{query} published in the last {days} days"
    tavily_tool = TavilySearchResults(max_results=3, search_depth="basic")
    try:
        results = tavily_tool.invoke({"query": query})
        
        # Standardize the output format
        formatted_results = []
        for r in results:
            formatted_results.append({
                "title": f"[Tavily] {r.get('title', 'No Title')}",
                "url": r.get('url', ''),
                "summary": r.get('content', ''),
                "source": "Tavily Search"
            })
    except Exception as e:
        print(f"Error fetching Tavily news: {e}")
        formatted_results = []
    
    return {"tavily_news": formatted_results}

def rss_node(state: AgentState):
    """Fetches news from hardcoded RSS feeds."""
    import email.utils
    from datetime import timezone
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
                    # Check publication date
                    pub_date_el = item.find('pubDate')
                    if pub_date_el is not None and pub_date_el.text:
                        try:
                            # Use email.utils to parse standard RSS date format
                            import email.utils
                            pub_dt = email.utils.parsedate_to_datetime(pub_date_el.text)
                            if pub_dt and pub_dt < cutoff:
                                continue  # Skip old news
                        except Exception:
                            pass # Fallback to keeping it if parsing fails
                            
                    title = item.find('title').text if item.find('title') is not None else "No Title"
                    link = item.find('link').text if item.find('link') is not None else ""
                    description = item.find('description').text if item.find('description') is not None else ""
                    
                    # Clean up HTML tags from description if any
                    import re
                    clean_description = re.sub(r'<[^>]+>', '', description)[:300] if description else ""
                    
                    results.append({
                        "title": f"[RSS] {title}", 
                        "url": link, 
                        "summary": clean_description,
                        "source": url
                    })
        except Exception as e:
            print(f"Error fetching RSS {url}: {e}")
            
    # Keep only the top 5 most recent across all feeds to prevent bloat
    return {"rss_news": results[:5]}

def arxiv_node(state: AgentState):
    """Fetches latest AI papers from ArXiv API."""
    from datetime import timezone
    days = state.get("days", 2)
    cutoff = datetime.now(timezone.utc) - timedelta(days=days)
    
    try:
        url = "http://export.arxiv.org/api/query?search_query=cat:cs.AI+OR+cat:cs.CL+OR+cat:cs.LG&sortBy=lastUpdatedDate&sortOrder=desc&max_results=10"
        response = requests.get(url, timeout=5)
        results = []
        if response.status_code == 200:
            root = ET.fromstring(response.content)
            # ArXiv uses Atom namespace
            ns = {'atom': 'http://www.w3.org/2005/Atom'}
            for entry in root.findall('atom:entry', ns):
                # Filter by update date
                updated_el = entry.find('atom:updated', ns)
                if updated_el is not None and updated_el.text:
                    try:
                        updated_dt = datetime.fromisoformat(updated_el.text.replace("Z", "+00:00"))
                        if updated_dt < cutoff:
                            continue # Skip old papers
                    except Exception:
                        pass
                        
                title_el = entry.find('atom:title', ns)
                title = title_el.text.replace('\n', ' ').strip() if title_el is not None and title_el.text else "No Title"
                
                link_el = entry.find('atom:id', ns)
                link = link_el.text if link_el is not None and link_el.text else ""
                
                summary_el = entry.find('atom:summary', ns)
                summary_text = summary_el.text if summary_el is not None and summary_el.text else ""
                summary = summary_text[:200] + "..." if summary_text else ""
                
                results.append({
                    "title": f"[ArXiv] {title}", 
                    "url": link, 
                    "summary": summary,
                    "source": "ArXiv API"
                })
    except Exception as e:
        print(f"Error fetching ArXiv: {e}")
        results = []
        
    return {"arxiv_news": results}

def github_node(state: AgentState):
    """Fetches trending AI repositories from GitHub."""
    days = state.get("days", 2)
    try:
        # Search for repos created in the last X days with AI topics
        date_str = (datetime.now() - timedelta(days=days)).strftime("%Y-%m-%d")
        url = f"https://api.github.com/search/repositories?q=topic:llm+OR+topic:generative-ai+created:>{date_str}&sort=stars&order=desc&per_page=3"
        response = requests.get(url, timeout=5)
        results = []
        if response.status_code == 200:
            data = response.json()
            for repo in data.get("items", []):
                results.append({
                    "title": f"[GitHub] {repo['full_name']} (⭐ {repo['stargazers_count']})",
                    "url": repo['html_url'],
                    "summary": repo.get('description', '') or 'No description',
                    "source": "GitHub Trending"
                })
    except Exception as e:
        print(f"Error fetching GitHub: {e}")
        results = []
        
    return {"github_news": results}

def hf_node(state: AgentState):
    """Fetches trending models from Hugging Face."""
    try:
        url = "https://huggingface.co/api/models?sort=trendingScore&direction=-1&limit=3"
        response = requests.get(url, timeout=5)
        results = []
        if response.status_code == 200:
            data = response.json()
            for model in data:
                results.append({
                    "title": f"[HuggingFace] {model.get('id', 'Unknown Model')}",
                    "url": f"https://huggingface.co/{model.get('id')}",
                    "summary": f"Trending HF Model. Downloads: {model.get('downloads', 0)}",
                    "source": "Hugging Face API"
                })
    except Exception as e:
        print(f"Error fetching Hugging Face: {e}")
        results = []
        
    return {"hf_news": results}

def hn_node(state: AgentState):
    """Fetches trending AI stories from HackerNews."""
    try:
        url = "https://hacker-news.firebaseio.com/v0/topstories.json"
        response = requests.get(url, timeout=10)
        results = []
        if response.status_code == 200:
            story_ids = response.json()[:30]  # Just top 30 to stay fast
            for story_id in story_ids:
                try:
                    item_url = f"https://hacker-news.firebaseio.com/v0/item/{story_id}.json"
                    item_res = requests.get(item_url, timeout=5)
                    if item_res.status_code == 200:
                        item = item_res.json()
                        title = item.get("title", "")
                        # Simple keyword filter before sending to Gemini
                        if any(kw in title.lower() for kw in ["ai", "llm", "model", "gpt", "claude", "machine learning", "sam altman", "openai", "anthropic", "llama"]):
                            results.append({
                                "title": f"[HackerNews] {title}",
                                "url": item.get("url", f"https://news.ycombinator.com/item?id={story_id}"),
                                "summary": f"HN Score: {item.get('score', 0)}. Comments: {item.get('descendants', 0)}",
                                "source": "HackerNews Top Stories"
                            })
                except Exception as item_err:
                    print(f"Error fetching HN item {story_id}: {item_err}")
    except Exception as e:
        print(f"Error fetching HackerNews: {e}")
        results = []
    
    return {"hn_news": results[:5]}

def reddit_node(state: AgentState):
    """Fetches trending discussions from r/LocalLLaMA and r/MachineLearning."""
    try:
        url = "https://www.reddit.com/r/LocalLLaMA+MachineLearning/top.json?t=day&limit=5"
        headers = {"User-Agent": "GenAINewsAgent/1.0"}
        response = requests.get(url, headers=headers, timeout=5)
        results = []
        if response.status_code == 200:
            data = response.json()
            for post in data.get("data", {}).get("children", []):
                post_data = post.get("data", {})
                title = post_data.get("title", "No Title")
                results.append({
                    "title": f"[Reddit - {post_data.get('subreddit_name_prefixed', 'r/AI')}] {title}",
                    "url": f"https://reddit.com{post_data.get('permalink', '')}",
                    "summary": f"Score: {post_data.get('score', 0)}. " + (post_data.get("selftext", "")[:400] + "..." if post_data.get("selftext") else ""),
                    "source": "Reddit Top Daily"
                })
    except Exception as e:
        print(f"Error fetching Reddit: {e}")
        results = []
        
    return {"reddit_news": results}

def youtube_node(state: AgentState):
    """Fetches latest AI video transcripts from top YouTube channels by parsing HTML to bypass RSS block."""
    from youtube_transcript_api import YouTubeTranscriptApi
    import re
    
    channels = [
        "https://www.youtube.com/@aiexplained-official/videos",
        "https://www.youtube.com/@YannicKilcher/videos"
    ]
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/114.0.0.0 Safari/537.36"
    }
    results = []
    
    for channel_url in channels:
        try:
            res = requests.get(channel_url, headers=headers, timeout=5)
            if res.status_code == 200:
                # Look for the first "videoId":"..." string in the source JSON injected into the page
                matches = re.findall(r'"videoId":"([^"]+)"', res.text)
                if matches:
                    video_id = matches[0]
                    # Try to extract the canonical title too, or just use the channel URL as title prefix
                    title = f"[YouTube AI] Video: {video_id}"
                    title_matches = re.findall(r'"title":{"runs":\[{"text":"([^"]+)"}\]', res.text)
                    if title_matches:
                        title = f"[YouTube AI] {title_matches[0]}"
                        
                    link = f"https://www.youtube.com/watch?v={video_id}"
                    
                    try:
                        # Fetch transcript (this is independent of YouTube API keys!)
                        transcript = YouTubeTranscriptApi().fetch(video_id)
                        text = " ".join([t.text for t in transcript])
                        summary = text[:1000] + "..."
                    except Exception as e:
                        print(f"Could not fetch transcript for {video_id}: {e}")
                        summary = "Video transcript unavailable."
                        
                    results.append({
                        "title": title,
                        "url": link,
                        "summary": summary,
                        "source": "YouTube AI Channels"
                    })
        except Exception as e:
            print(f"Error fetching YouTube channel {channel_url}: {e}")
            
    return {"youtube_news": results}

def aggregate_node(state: AgentState):
    """Aggregates all fetched news into a single list."""
    combined = []
    combined.extend(state.get("tavily_news", []))
    combined.extend(state.get("rss_news", []))
    combined.extend(state.get("arxiv_news", []))
    combined.extend(state.get("github_news", []))
    combined.extend(state.get("hf_news", []))
    combined.extend(state.get("hn_news", []))
    combined.extend(state.get("reddit_news", []))
    combined.extend(state.get("youtube_news", []))
    
    return {"raw_news": combined}

def curate_node(state: AgentState):
    """Filters and curates the most important news."""
    days = state.get("days", 2)
    raw_news = state.get("raw_news", [])
    if not raw_news:
        return {"curated_news": []}
    
    # We will use an LLM to select the top impactful news
    llm = ChatGoogleGenerativeAI(
        model="gemini-2.5-flash", 
        google_api_key=os.getenv("GOOGLE_API_KEY"),
        temperature=0,
        convert_system_message_to_human=True
    )
    
    from datetime import datetime
    today_str = datetime.now().strftime('%Y-%m-%d')
    prompt = f"""
    You are an expert AI news curator evaluating articles on {today_str}.
    Given the following list of raw news articles fetched from various sources,
    select the most important and impactful news stories in the field of Generative AI published in the last {days} days.
    
    IMPORTANT INSTRUCTIONS: 
    1. Filter out noise, clickbait, or less relevant articles. Focus on major releases, strategic partnerships, and frontier model updates.
    2. CRITICAL: Search engines sometimes return highly-ranked but OUTDATED news (e.g., Google rebranding Bard to Gemini in early 2024, or old OpenAI releases). 
       You MUST actively filter out any news that is older than {days} days. If an article describes an event that clearly happened months or years ago relative to {today_str}, DISCARD IT.
    3. If an article has a short or missing summary, judge its relevance and age based on its title and URL.
    
    News Articles:
    {raw_news}
    
    Return ONLY a valid JSON list of objects containing 'title', 'url', and a short 'summary'.
    Do not include any other text, markdown formatting, or explanations before or after the JSON.
    """
    
    response = llm.invoke([
        SystemMessage(content="You return ONLY valid JSON and absolutely nothing else."), 
        HumanMessage(content=prompt)
    ])
    
    # Debugging output for development
    print(f"Curator LLM response length: {len(response.content)}")
    
    try:
        content = response.content.strip()
        # Find the first '[' and last ']' to extract just the JSON array, ignoring any conversational text
        start_idx = content.find('[')
        end_idx = content.rfind(']')
        
        if start_idx != -1 and end_idx != -1 and start_idx < end_idx:
            json_str = content[start_idx:end_idx+1]
            curated = json.loads(json_str)
        else:
            raise ValueError(f"Could not find JSON array in response.")
            
    except Exception as e:
        print(f"Error parsing curated news: {e}\nResponse was: {response.content}")
        curated = []
        
    return {"curated_news": curated}

def summarize_node(state: AgentState):
    """Generates the final markdown report."""
    curated_news = state.get("curated_news", [])
    if not curated_news:
        return {"final_report": "No significant news found today."}
        
    llm = ChatGoogleGenerativeAI(
        model="gemini-2.5-flash", 
        google_api_key=os.getenv("GOOGLE_API_KEY"),
        temperature=0.2,
        convert_system_message_to_human=True
    )
    
    prompt = f"""
    You are an expert tech journalist. Write a concise, highly engaging markdown report 
    summarizing the following top Generative AI news.
    
    Instructions:
    - Start with an engaging title and a very short introduction (1-2 sentences).
    - For each news item, provide a bolded catchy headline linked to the source URL.
    - Write a short, insightful paragraph for each news item explaining why it matters.
    - Keep it professional, objective, yet interesting.
    - Conclude with a brief closing thought on the trend.
    
    Curated News:
    {json.dumps(curated_news, indent=2)}
    """
    
    response = llm.invoke([
        SystemMessage(content="You are a helpful assistant writing markdown reports."), 
        HumanMessage(content=prompt)
    ])
    
    return {"final_report": response.content}

def email_node(state: AgentState):
    """Sends the final report to all subscribers via email."""
    import smtplib
    from email.mime.multipart import MIMEMultipart
    from email.mime.text import MIMEText
    import markdown
    
    email_log = {"status": "started", "subscribers_found": 0, "sheet_status": "not_attempted", "email_status": "not_attempted"}
    
    final_report = state.get("final_report", "")
    if not final_report or final_report == "No significant news found today.":
        print("No report to email.")
        email_log["status"] = "skipped_no_report"
        return {"email_log": email_log}
        
    sender_email = os.getenv("GMAIL_USER")
    sender_password = os.getenv("GMAIL_APP_PASSWORD")
    
    if not sender_email or not sender_password:
        print("Email credentials not found. Skipping email node.")
        print(f"  GMAIL_USER set: {bool(sender_email)}, GMAIL_APP_PASSWORD set: {bool(sender_password)}")
        email_log["status"] = "skipped_no_credentials"
        return {"email_log": email_log}
        
    # Load subscribers
    subscribers = []
    
    # 1. Try to fetch from automated Google Sheet (if URL provided)
    sheet_url = os.getenv("SUBSCRIBERS_SHEET_URL")
    print(f"[EMAIL] SUBSCRIBERS_SHEET_URL is set: {bool(sheet_url)}")
    if sheet_url:
        try:
            import requests
            import csv
            from io import StringIO
            response = requests.get(sheet_url, timeout=15)
            print(f"[EMAIL] Sheet fetch status: {response.status_code}, Content length: {len(response.text)}")
            if response.status_code == 200:
                f = StringIO(response.text)
                reader = csv.reader(f)
                header = next(reader, None) # Skip header
                print(f"[EMAIL] Sheet header row: {header}")
                
                # Try to find email column dynamically
                email_col_idx = None
                if header:
                    for i, col in enumerate(header):
                        if 'email' in col.lower() or '@' in col.lower():
                            email_col_idx = i
                            break
                
                subscribers_from_sheet = []
                rows_processed = 0
                for row in reader:
                    rows_processed += 1
                    # Try the detected column first, then try ALL columns
                    if email_col_idx is not None and len(row) > email_col_idx and '@' in row[email_col_idx]:
                        subscribers_from_sheet.append(row[email_col_idx])
                    else:
                        # Fallback: scan every column in the row for an email
                        for cell in row:
                            if '@' in cell and '.' in cell:
                                subscribers_from_sheet.append(cell)
                                break
                
                subscribers.extend(subscribers_from_sheet)
                print(f"[EMAIL] Processed {rows_processed} rows, found {len(subscribers_from_sheet)} subscribers from Google Sheet.")
                email_log["sheet_status"] = f"ok_{len(subscribers_from_sheet)}_subscribers_from_{rows_processed}_rows"
            else:
                print(f"[EMAIL] Sheet returned non-200 status: {response.status_code}")
                email_log["sheet_status"] = f"http_error_{response.status_code}"
        except Exception as e:
            print(f"[EMAIL] Error fetching from Google Sheet: {e}")
            email_log["sheet_status"] = f"exception: {str(e)}"

    # 2. Fallback/Add from local subscribers.json
    try:
        subscribers_path = os.path.join(os.path.dirname(os.path.dirname(__file__)), "subscribers.json")
        if os.path.exists(subscribers_path):
            with open(subscribers_path, "r") as f:
                local_subs = json.load(f)
                subscribers.extend(local_subs)
                print(f"[EMAIL] Loaded {len(local_subs)} subscribers from local file.")
    except Exception as e:
        print(f"[EMAIL] Error loading local subscribers: {e}")
        
    # Clean up list (unique and valid)
    subscribers = list(set([s.strip().lower() for s in subscribers if s and "@" in s]))
    if not subscribers:
        subscribers = [sender_email]
        print(f"[EMAIL] WARNING: No subscribers found, falling back to sender only: {sender_email}")
    
    email_log["subscribers_found"] = len(subscribers)
    print(f"[EMAIL] Final recipient count: {len(subscribers)}")
        
    # Convert Markdown to HTML for the email
    html_content = markdown.markdown(final_report)
    
    # Add some basic styling to the HTML email
    styled_html = f"""
    <html>
    <head>
        <style>
            body {{ font-family: 'Helvetica Neue', Helvetica, Arial, sans-serif; line-height: 1.6; color: #333; max-width: 600px; margin: 0 auto; padding: 20px; }}
            h1, h2, h3 {{ color: #1a73e8; }}
            a {{ color: #1a73e8; text-decoration: none; font-weight: bold; }}
            hr {{ border: 0; border-top: 1px solid #eee; margin: 20px 0; }}
            .footer {{ font-size: 12px; color: #888; margin-top: 30px; text-align: center; border-top: 1px solid #eee; padding-top: 10px; }}
        </style>
    </head>
    <body>
        {html_content}
        <div class="footer">
            Sent by your automated GenAI News Agent.<br>
            To unsubscribe, reply to this email with "Unsubscribe".
        </div>
    </body>
    </html>
    """
    
    try:
        # Create message
        msg = MIMEMultipart()
        msg['From'] = f"GenAI News Agent <{sender_email}>"
        msg['To'] = sender_email # Primary recipient
        msg['Subject'] = f"🚀 Daily AI Highlights - {datetime.now().strftime('%b %d, %Y')}"
        
        msg.attach(MIMEText(styled_html, 'html'))
        
        # Connect and send
        with smtplib.SMTP_SSL("smtp.gmail.com", 465) as server:
            server.login(sender_email, sender_password)
            # Send to yourself + all subscribers as BCC to protect privacy
            recipients = list(set([sender_email] + subscribers))
            server.sendmail(sender_email, recipients, msg.as_string())
            print(f"[EMAIL] Successfully sent email to {len(recipients)} recipients: {recipients}")
            email_log["email_status"] = f"sent_to_{len(recipients)}"
            email_log["status"] = "success"
            
    except Exception as e:
        print(f"[EMAIL] Error sending email: {e}")
        email_log["email_status"] = f"error: {str(e)}"
        email_log["status"] = "failed"
        
    return {"email_log": email_log}

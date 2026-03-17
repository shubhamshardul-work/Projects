from typing import TypedDict, List, Any

class AgentState(TypedDict, total=False):
    """
    State of the agent.
    """
    search_query: str
    days: int
    tavily_news: List[Any]
    rss_news: List[Any]
    arxiv_news: List[Any]
    github_news: List[Any]
    hf_news: List[Any]
    hn_news: List[Any]
    reddit_news: List[Any]
    youtube_news: List[Any]
    raw_news: List[Any]
    categorized_news: dict       # {"business": [...], "technical": [...], "research": [...]}
    curated_news: List[dict]
    final_report: str
    email_log: dict

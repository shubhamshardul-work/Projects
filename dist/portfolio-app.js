// Interactive hover effects for glass panels
function initGlassPanels() {
    const cards = document.querySelectorAll('.glass-panel');

    cards.forEach(card => {
        card.removeEventListener('mousemove', handleMouseMove);
        card.addEventListener('mousemove', handleMouseMove);
    });
}

function handleMouseMove(e) {
    const rect = this.getBoundingClientRect();
    const x = e.clientX - rect.left;
    const y = e.clientY - rect.top;

    this.style.setProperty('--mouse-x', `${x}px`);
    this.style.setProperty('--mouse-y', `${y}px`);
}

// Handle About Me Toggle
function initAboutToggle() {
    const card = document.getElementById('about-card');
    const toggle = document.getElementById('about-toggle');

    if (toggle && card) {
        toggle.addEventListener('click', () => {
            card.classList.toggle('active');
        });
    }
}

// Fetch Medium Articles using rss2json.com with caching (24h expiry)
async function fetchMediumArticles() {
    const rss2jsonUrl = 'https://api.rss2json.com/v1/api.json?rss_url=https%3A%2F%2Fmedium.com%2Ffeed%2F%40shubham.shardul2019';
    const CACHE_KEY = 'medium_articles_cache';
    const CACHE_TS_KEY = 'medium_articles_cache_ts';
    const CACHE_TTL = 24 * 60 * 60 * 1000; // 24 hours
    const container = document.getElementById('medium-articles');

    if (!container) return;

    // 1. Load from cache immediately — but only if it hasn't expired
    const cachedData = localStorage.getItem(CACHE_KEY);
    const cachedTs = parseInt(localStorage.getItem(CACHE_TS_KEY) || '0', 10);
    const cacheIsValid = cachedData && (Date.now() - cachedTs < CACHE_TTL);

    if (cacheIsValid) {
        try {
            renderArticles(JSON.parse(cachedData), true);
        } catch (e) {
            console.error("Cache parse error:", e);
        }
    }

    try {
        // 2. Fetch fresh data with a timeout
        const controller = new AbortController();
        const timeoutId = setTimeout(() => controller.abort(), 8000);

        const response = await fetch(rss2jsonUrl, { signal: controller.signal });
        clearTimeout(timeoutId);

        const data = await response.json();
        if (!data || data.status !== 'ok' || !data.items) throw new Error("Invalid rss2json response");

        // 3. Map items (rss2json returns clean JSON — no XML parsing needed)
        const articles = data.items.slice(0, 3).map(item => {
            const title = item.title || "Article";
            const link = item.link || "#";

            // Extract brief text from description HTML
            const tempDiv = document.createElement('div');
            tempDiv.innerHTML = item.description || item.content || "";
            let text = (tempDiv.textContent || tempDiv.innerText || "").trim();
            text = text.substring(0, 120) + '...';

            let dateStr = "";
            if (item.pubDate) {
                dateStr = new Date(item.pubDate).toLocaleDateString(undefined, {
                    year: 'numeric', month: 'short', day: 'numeric'
                });
            }

            return { title, link, text, dateStr };
        });

        // 4. Update Cache (with timestamp) and Render
        localStorage.setItem(CACHE_KEY, JSON.stringify(articles));
        localStorage.setItem(CACHE_TS_KEY, String(Date.now()));
        renderArticles(articles);

    } catch (error) {
        console.error("Medium Fetch Error:", error);
        // If fetch fails and cache exists (even expired), show it as fallback
        if (cachedData && !cacheIsValid) {
            try {
                renderArticles(JSON.parse(cachedData), true);
            } catch (e) { /* ignore */ }
        }
        // If no cache at all, show error message
        if (!cachedData) {
            container.innerHTML = `<div class="glass-panel" style="text-align: center; color: var(--text-muted); width: 100%;">Unable to load articles right now. Please try again later.</div>`;
        }
    }
}

function renderArticles(articles, isCached = false) {
    const container = document.getElementById('medium-articles');
    if (!container) return;

    container.innerHTML = ''; // Clear

    articles.forEach(article => {
        const html = `
            <a href="${article.link}" target="_blank" rel="noopener noreferrer" class="project-card glass-panel article-card">
                <div class="project-info">
                    <div class="tags" style="margin-bottom: 12px;">
                        <span class="tag" style="background: rgba(139,92,246,0.15); color: #a78bfa;">Article</span>
                        ${article.dateStr ? `<span class="tag">${article.dateStr}</span>` : ''}
                    </div>
                    <h4 style="font-size: 1.25rem;">${article.title}</h4>
                    <p style="font-size: 0.95rem;">${article.text}</p>
                </div>
                <div class="project-link-arrow">
                    <i class="ph ph-arrow-up-right"></i>
                </div>
            </a>
        `;
        container.innerHTML += html;
    });

    initGlassPanels();
}

document.addEventListener('DOMContentLoaded', () => {
    initGlassPanels();
    initAboutToggle();
    fetchMediumArticles();

    // Smooth scrolling
    document.querySelectorAll('a[href^="#"]').forEach(anchor => {
        anchor.addEventListener('click', function (e) {
            e.preventDefault();
            const target = document.querySelector(this.getAttribute('href'));
            if (target) {
                target.scrollIntoView({
                    behavior: 'smooth',
                    block: 'start'
                });
            }
        });
    });
});

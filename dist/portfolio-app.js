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

// Fetch Medium Articles with caching and reliability fixes
async function fetchMediumArticles() {
    const mediumRssUrl = 'https://medium.com/feed/@shubham.shardul2019';
    const allOriginsUrl = `https://api.allorigins.win/get?url=${encodeURIComponent(mediumRssUrl)}`;
    const CACHE_KEY = 'medium_articles_cache';
    const container = document.getElementById('medium-articles');

    if (!container) return;

    // 1. Load from cache immediately for instant UI
    const cachedData = localStorage.getItem(CACHE_KEY);
    if (cachedData) {
        try {
            const articles = JSON.parse(cachedData);
            renderArticles(articles, true); // Render with "cached" flag
        } catch (e) {
            console.error("Cache parse error:", e);
        }
    }

    try {
        // 2. Fetch fresh data with a timeout
        const controller = new AbortController();
        const timeoutId = setTimeout(() => controller.abort(), 8000); // 8 second timeout

        const response = await fetch(allOriginsUrl, { signal: controller.signal });
        clearTimeout(timeoutId);

        const data = await response.json();
        if (!data || !data.contents) throw new Error("Invalid response from proxy");

        // 3. Parse XML
        const parser = new DOMParser();
        const xmlDoc = parser.parseFromString(data.contents, "text/xml");
        const items = xmlDoc.querySelectorAll("item");

        if (items.length > 0) {
            const articles = Array.from(items).slice(0, 3).map(item => {
                const title = item.querySelector("title")?.textContent || "Article";
                const link = item.querySelector("link")?.textContent || "#";
                const pubDate = item.querySelector("pubDate")?.textContent;
                const contentEncoded = item.getElementsByTagName("content:encoded")[0]?.textContent ||
                    item.querySelector("description")?.textContent || "";

                // Extract brief text 
                const tempDiv = document.createElement('div');
                tempDiv.innerHTML = contentEncoded;
                let text = (tempDiv.textContent || tempDiv.innerText || "").trim();
                text = text.substring(0, 120) + '...';

                let dateStr = "";
                if (pubDate) {
                    dateStr = new Date(pubDate).toLocaleDateString(undefined, {
                        year: 'numeric', month: 'short', day: 'numeric'
                    });
                }

                return { title, link, text, dateStr };
            });

            // 4. Update Cache and Render
            localStorage.setItem(CACHE_KEY, JSON.stringify(articles));
            renderArticles(articles);
        }
    } catch (error) {
        console.error("Medium Fetch Error:", error);
        // If fetch fails and nothing is in cache, show error
        if (!localStorage.getItem(CACHE_KEY)) {
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

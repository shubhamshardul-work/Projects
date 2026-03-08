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

// Fetch Medium Articles manually parsing XML due to third-party API instability
async function fetchMediumArticles() {
    const mediumRssUrl = 'https://medium.com/feed/@shubham.shardul2019';
    const allOriginsUrl = `https://api.allorigins.win/get?url=${encodeURIComponent(mediumRssUrl)}`;

    const container = document.getElementById('medium-articles');
    if (!container) return;

    try {
        const response = await fetch(allOriginsUrl);
        const data = await response.json();

        // Parse the raw XML string returned by allorigins
        const parser = new DOMParser();
        const xmlDoc = parser.parseFromString(data.contents, "text/xml");
        const items = xmlDoc.querySelectorAll("item");

        if (items.length > 0) {
            container.innerHTML = ''; // Clear loading text

            // Get up to 3 recent articles
            const articles = Array.from(items).slice(0, 3);

            articles.forEach(item => {
                const title = item.querySelector("title")?.textContent || "Article";
                const link = item.querySelector("link")?.textContent || "#";
                const pubDate = item.querySelector("pubDate")?.textContent;

                // Content Encoded often contains the full HTML body in Medium RSS
                const contentEncoded = item.getElementsByTagName("content:encoded")[0]?.textContent || item.querySelector("description")?.textContent || "";

                // Extract brief text 
                const tempDiv = document.createElement('div');
                tempDiv.innerHTML = contentEncoded;
                let text = tempDiv.textContent || tempDiv.innerText || "";

                // Medium appends "Continue reading..." which we can trim, or just take first 100 chars
                text = text.trim().substring(0, 120) + '...';

                // Format Date
                let dateStr = "";
                if (pubDate) {
                    dateStr = new Date(pubDate).toLocaleDateString(undefined, {
                        year: 'numeric', month: 'short', day: 'numeric'
                    });
                }

                const html = `
                    <a href="${link}" target="_blank" rel="noopener noreferrer" class="project-card glass-panel article-card">
                        <div class="project-info">
                            <div class="tags" style="margin-bottom: 12px;">
                                <span class="tag" style="background: rgba(139,92,246,0.15); color: #a78bfa;">Article</span>
                                ${dateStr ? `<span class="tag">${dateStr}</span>` : ''}
                            </div>
                            <h4 style="font-size: 1.25rem;">${title}</h4>
                            <p style="font-size: 0.95rem;">${text}</p>
                        </div>
                        <div class="project-link-arrow">
                            <i class="ph ph-arrow-up-right"></i>
                        </div>
                    </a>
                `;
                container.innerHTML += html;
            });
            initGlassPanels();
        } else {
            container.innerHTML = `<div class="glass-panel" style="text-align: center; color: var(--text-muted); width: 100%;">No articles found.</div>`;
        }
    } catch (error) {
        console.error("Error fetching or parsing Medium articles:", error);
        container.innerHTML = `<div class="glass-panel" style="text-align: center; color: var(--text-muted); width: 100%;">Unable to load articles right now.</div>`;
    }
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

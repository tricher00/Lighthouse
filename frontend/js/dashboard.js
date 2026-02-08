/**
 * Lighthouse Dashboard JavaScript
 * Handles fetching and rendering dashboard data.
 */

const API_BASE = '';
let dashboardData = null;

// Initialize on page load
document.addEventListener('DOMContentLoaded', () => {
    console.log('🗼 Lighthouse dashboard loaded');
    refreshDashboard();
});

// Fetch dashboard data from API
async function refreshDashboard() {
    console.log('🔄 Refreshing dashboard...');

    try {
        const response = await fetch(`${API_BASE}/api/dashboard`);
        if (!response.ok) {
            throw new Error(`HTTP ${response.status}`);
        }

        dashboardData = await response.json();
        console.log('✅ Dashboard data loaded', dashboardData);

        const locationName = dashboardData.location_name || 'Your Location';
        renderWeather(dashboardData.weather, locationName);
        renderTraffic(dashboardData.traffic, locationName);
        renderGames(dashboardData.games);
        renderAllSections(dashboardData.sections);
        updateStats(dashboardData.stats);

    } catch (err) {
        console.error('❌ Failed to load dashboard:', err);
        showError('Failed to connect to Lighthouse backend. Is it running?');
    }
}

// Render weather card
function renderWeather(weather, locationName) {
    const card = document.getElementById('weather-card');

    if (!weather) {
        card.innerHTML = `
            <div class="card-header">
                <span class="card-title">Weather</span>
            </div>
            <div class="empty-state">
                <div class="icon">🌤️</div>
                <p>Weather data not available</p>
                <small>Check your API key configuration</small>
            </div>
        `;
        return;
    }

    const iconMap = {
        '01d': '☀️', '01n': '🌙',
        '02d': '⛅', '02n': '☁️',
        '03d': '☁️', '03n': '☁️',
        '04d': '☁️', '04n': '☁️',
        '09d': '🌧️', '09n': '🌧️',
        '10d': '🌦️', '10n': '🌧️',
        '11d': '⛈️', '11n': '⛈️',
        '13d': '❄️', '13n': '❄️',
        '50d': '🌫️', '50n': '🌫️'
    };

    const icon = iconMap[weather.icon] || '🌡️';

    card.innerHTML = `
        <div class="card-header">
            <span class="card-title">Weather</span>
            <span class="card-meta">${escapeHtml(locationName)}</span>
        </div>
        <div class="weather-display">
            <span class="weather-icon">${icon}</span>
            <span class="temp">${Math.round(weather.temperature)}°</span>
        </div>
        <div class="conditions">${weather.conditions}</div>
        <div class="weather-details">
            <span>Feels like ${Math.round(weather.feels_like)}°</span>
            <span>H: ${Math.round(weather.high)}° L: ${Math.round(weather.low)}°</span>
        </div>
        ${weather.dress_suggestion ? `
            <div class="dress-tip">
                👕 ${weather.dress_suggestion}
            </div>
        ` : ''}
    `;
}

// Render traffic card
function renderTraffic(alerts, locationName) {
    const card = document.getElementById('traffic-card');

    if (!alerts || alerts.length === 0) {
        card.innerHTML = `
            <div class="card-header">
                <span class="card-title">Traffic</span>
                <span class="card-meta">${escapeHtml(locationName)}</span>
            </div>
            <div class="no-alerts">
                <span>✅</span>
                <span>No traffic alerts</span>
            </div>
        `;
        return;
    }

    const alertsHtml = alerts.map(alert => `
        <div class="alert ${alert.severity}">
            <span class="alert-icon">⚠️</span>
            <div class="alert-content">
                <strong>${alert.route}</strong>
                <p class="alert-text">${cleanAlertDescription(alert.description)}</p>
                ${alert.url ? `<a href="${alert.url}" target="_blank" class="alert-link">Read full alert →</a>` : ''}
            </div>
        </div>
    `).join('');

    card.innerHTML = `
        <div class="card-header">
            <span class="card-title">Traffic</span>
            <span class="card-meta">${alerts.length} alert(s)</span>
        </div>
        ${alertsHtml}
    `;
}

// Render games card
function renderGames(games) {
    const card = document.getElementById('sports-card');

    if (!games || games.length === 0) {
        card.innerHTML = `
            <div class="card-header">
                <span class="card-title">Upcoming Games</span>
            </div>
            <div class="empty-state">
                <div class="icon">🏟️</div>
                <p>No upcoming games</p>
            </div>
        `;
        return;
    }

    const gamesHtml = games.slice(0, 5).map(game => {
        const gameDate = new Date(game.game_time);
        const isToday = isSameDay(gameDate, new Date());
        const dateStr = isToday ? 'Today' : formatDate(gameDate);
        const timeStr = formatTime(gameDate);

        return `
            <div class="game">
                <div class="game-teams">
                    <span class="team">${game.team}</span>
                    <span class="vs">vs</span>
                    <span class="opponent">${game.opponent}</span>
                </div>
                <div class="game-time">
                    <div>${dateStr}</div>
                    <div>${timeStr}</div>
                </div>
            </div>
        `;
    }).join('');

    card.innerHTML = `
        <div class="card-header">
            <span class="card-title">Upcoming Games</span>
        </div>
        ${gamesHtml}
    `;
}

// Render article sections
function renderAllSections(sections) {
    if (!sections) return;

    const categoryMap = {
        'boston_sports': 'boston-sports',
        'other_teams': 'other-teams',
        'league_wide': 'league-wide',
        'national_news': 'news',
        'local_news': 'local-news',
        'long_form': 'long-form',
        'movies': 'movies'
    };

    for (const [category, articles] of Object.entries(sections)) {
        try {
            const sectionId = categoryMap[category];
            if (!sectionId) {
                console.log(`ℹ️ Skipping category ${category} (no ID mapping)`);
                continue;
            }

            const section = document.getElementById(sectionId);
            if (!section) {
                console.warn(`⚠️ Section element not found: ${sectionId}`);
                continue;
            }

            const grid = section.querySelector('.article-grid');
            if (!grid) continue;

            if (!articles || articles.length === 0) {
                grid.innerHTML = `
                    <div class="empty-state">
                        <p>No new articles</p>
                    </div>
                `;
                continue;
            }

            grid.innerHTML = articles.map(article => renderArticleCard(article)).join('');
        } catch (err) {
            console.error(`❌ Error rendering category ${category}:`, err);
        }
    }
}

// Render a single article card
function renderArticleCard(article) {
    const timeAgo = article.published_at ? getTimeAgo(new Date(article.published_at)) : '';

    return `
        <article class="card article-card" data-id="${article.id}" onclick="openArticle('${article.url}', ${article.id})">
            <div class="card-header">
                <span class="source">${article.source_name}</span>
                <span class="card-meta">${timeAgo}</span>
            </div>
            <h3 class="card-title">${escapeHtml(article.title)}</h3>
            ${article.summary_llm ?
            `<div class="ai-summary">
                    <span class="ai-badge">✨ AI Summary</span>
                    <p>${formatSummary(article.summary_llm)}</p>
                </div>` :
            (article.summary ? `<p class="summary">${escapeHtml(article.summary.substring(0, 200))}...</p>` : '')
        }
            <div class="card-footer">
                <div class="article-meta">
                    ${article.author ? `<span class="author">By ${escapeHtml(article.author)}</span>` : ''}
                </div>
                <div class="article-actions" onclick="event.stopPropagation()">
                    <button class="mark-read-btn ${article.is_read ? 'active' : ''}" onclick="markAsRead(${article.id})" title="Mark as read">
                        ${article.is_read ? '✓' : '○'}
                    </button>
                    <div class="rating-buttons">
                        <button class="rating-btn ${article.rating === 1 ? 'active' : ''}" onclick="rateArticle(${article.id}, 1)">👍</button>
                        <button class="rating-btn ${article.rating === -1 ? 'active' : ''}" onclick="rateArticle(${article.id}, -1)">👎</button>
                    </div>
                </div>
            </div>
        </article>
    `;
}

// Open article and mark as read
async function openArticle(url, articleId) {
    // Mark as read
    try {
        await fetch(`${API_BASE}/api/articles/${articleId}/read`, { method: 'POST' });
    } catch (err) {
        console.warn('Failed to mark as read:', err);
    }

    // Open in new tab
    window.open(url, '_blank');

    // Update UI
    const card = document.querySelector(`[data-id="${articleId}"]`);
    if (card) {
        card.classList.add('read');
    }
}

// Mark an article as read
async function markAsRead(articleId) {
    try {
        const response = await fetch(`${API_BASE}/api/articles/${articleId}/read`, {
            method: 'POST'
        });

        if (response.ok) {
            // Update UI
            const card = document.querySelector(`[data-id="${articleId}"]`);
            if (card) {
                card.classList.add('read');
                const markReadBtn = card.querySelector('.mark-read-btn');
                if (markReadBtn) {
                    markReadBtn.classList.add('active');
                    markReadBtn.textContent = '✓';
                }
            }
        }
    } catch (err) {
        console.error('Failed to mark as read:', err);
    }
}

// Rate an article
async function rateArticle(articleId, rating) {
    try {
        const response = await fetch(`${API_BASE}/api/articles/${articleId}/rate`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ rating })
        });

        if (response.ok) {
            // Update button states
            const card = document.querySelector(`[data-id="${articleId}"]`);
            if (card) {
                const thumbsUp = card.querySelector('.rating-btn:first-child');
                const thumbsDown = card.querySelector('.rating-btn:last-child');

                thumbsUp.classList.toggle('active', rating === 1);
                thumbsDown.classList.toggle('active', rating === -1);

                // Also mark as read when rating
                markAsRead(articleId);
            }
        }
    } catch (err) {
        console.error('Failed to rate article:', err);
    }
}

// Toggle collapsed sections
function toggleSection(sectionId) {
    const section = document.getElementById(sectionId);
    if (section) {
        section.classList.toggle('collapsed');
    }
}

// Update stats in footer
function updateStats(stats) {
    if (!stats) return;

    const unreadEl = document.getElementById('unread-count');
    const updatedEl = document.getElementById('last-updated');

    if (unreadEl) {
        unreadEl.textContent = stats.total_unread || 0;
    }

    if (updatedEl) {
        updatedEl.textContent = new Date().toLocaleTimeString();
    }
}

// Show error message
function showError(message) {
    const main = document.querySelector('main');
    main.innerHTML = `
        <div class="error-state">
            <div class="icon">⚠️</div>
            <h2>Connection Error</h2>
            <p>${message}</p>
            <button class="btn btn-primary" onclick="refreshDashboard()">Retry</button>
        </div>
    `;
}

// Format summary text to handle newlines/bullets
function formatSummary(text) {
    if (!text) return '';
    // Escape first
    let safe = escapeHtml(text);

    // Convert **bold** markdown to <b> tags
    safe = safe.replace(/\*\*(.+?)\*\*/g, '<b>$1</b>');

    // Convert newlines to breaks
    safe = safe.replace(/\n/g, '<br>');

    // Convert bullets at start of line or after break
    safe = safe.replace(/(^|<br>)\* /g, '$1• ');
    safe = safe.replace(/(^|<br>)- /g, '$1• ');

    return safe;
}

// Clean alert descriptions (remove technical IDs and truncate)
function cleanAlertDescription(text) {
    if (!text) return '';

    // Remove zone codes like MAZ005, MAZ006
    let cleaned = text.replace(/\b[A-Z]{2,3}Z?\d{3,4}\b/g, '');

    // Remove NWS office codes
    cleaned = cleaned.replace(/\bNWS [A-Za-z\/]+\b/g, '');

    // Remove extra whitespace
    cleaned = cleaned.replace(/\s+/g, ' ').trim();

    // Truncate if too long
    if (cleaned.length > 200) {
        cleaned = cleaned.substring(0, 197) + '...';
    }

    return cleaned;
}

// Utility functions
function escapeHtml(text) {
    if (!text) return '';
    const div = document.createElement('div');
    div.textContent = text;
    return div.innerHTML;
}

function getTimeAgo(date) {
    const seconds = Math.floor((new Date() - date) / 1000);

    if (seconds < 60) return 'just now';
    if (seconds < 3600) return `${Math.floor(seconds / 60)}m ago`;
    if (seconds < 86400) return `${Math.floor(seconds / 3600)}h ago`;
    if (seconds < 604800) return `${Math.floor(seconds / 86400)}d ago`;

    return formatDate(date);
}

function formatDate(date) {
    return date.toLocaleDateString('en-US', { month: 'short', day: 'numeric' });
}

function formatTime(date) {
    return date.toLocaleTimeString('en-US', { hour: 'numeric', minute: '2-digit' });
}

function isSameDay(d1, d2) {
    return d1.getFullYear() === d2.getFullYear() &&
        d1.getMonth() === d2.getMonth() &&
        d1.getDate() === d2.getDate();
}

// ============================================
// Source Manager Functions
// ============================================

let currentSourceTab = 'rss';
let sourcesData = [];
let categoriesData = [];

// Open source manager modal
async function openSourceManager() {
    const modal = document.getElementById('source-modal');
    modal.classList.add('open');

    // Load categories first, then sources
    await loadCategories();
    await loadSources();
}

// Close source manager modal
function closeSourceManager() {
    const modal = document.getElementById('source-modal');
    modal.classList.remove('open');
}

// Close on backdrop click
function closeSourceManagerOnBackdrop(event) {
    if (event.target.classList.contains('modal')) {
        closeSourceManager();
    }
}

// Close on Escape key
document.addEventListener('keydown', (e) => {
    if (e.key === 'Escape') {
        closeSourceManager();
    }
});

// Switch between RSS and Reddit tabs
function switchSourceTab(tab) {
    currentSourceTab = tab;

    // Update tab buttons
    document.querySelectorAll('.tab-btn').forEach(btn => {
        btn.classList.toggle('active', btn.dataset.tab === tab);
    });

    // Update forms
    document.getElementById('rss-form').classList.toggle('active', tab === 'rss');
    document.getElementById('reddit-form').classList.toggle('active', tab === 'reddit');

    // Re-render source list with filter
    renderSourceList();
}

// Load categories from API
async function loadCategories() {
    try {
        const response = await fetch(`${API_BASE}/api/sources/categories`);
        if (response.ok) {
            const data = await response.json();
            categoriesData = data.categories || [];
            populateCategoryDropdowns();
        }
    } catch (err) {
        console.error('Failed to load categories:', err);
    }
}

// Populate category dropdowns
function populateCategoryDropdowns() {
    const rssSelect = document.getElementById('rss-category');
    const redditSelect = document.getElementById('reddit-category');

    const optionsHtml = categoriesData.map(cat =>
        `<option value="${cat.value}">${cat.name}</option>`
    ).join('');

    rssSelect.innerHTML = `<option value="">Select category...</option>${optionsHtml}`;
    redditSelect.innerHTML = `<option value="">Select category...</option>${optionsHtml}`;
}

// Load sources from API
async function loadSources() {
    const sourceList = document.getElementById('source-list');
    sourceList.innerHTML = '<div class="loading">Loading sources...</div>';

    try {
        const response = await fetch(`${API_BASE}/api/sources`);
        if (response.ok) {
            const data = await response.json();
            sourcesData = data.sources || [];
            renderSourceList();
        } else {
            sourceList.innerHTML = '<div class="empty-state">Failed to load sources</div>';
        }
    } catch (err) {
        console.error('Failed to load sources:', err);
        sourceList.innerHTML = '<div class="empty-state">Failed to connect to server</div>';
    }
}

// Render the filtered source list
function renderSourceList() {
    const sourceList = document.getElementById('source-list');

    // Filter by current tab
    const filtered = sourcesData.filter(s => s.type === currentSourceTab);

    if (filtered.length === 0) {
        sourceList.innerHTML = `
            <div class="empty-state">
                <p>No ${currentSourceTab === 'rss' ? 'RSS feeds' : 'subreddits'} configured</p>
                <small>Add one above to get started</small>
            </div>
        `;
        return;
    }

    sourceList.innerHTML = filtered.map(source => `
        <div class="source-item ${source.enabled ? '' : 'disabled'}" data-source-id="${source.id}">
            <div class="source-info">
                <div class="source-name">
                    ${escapeHtml(source.name)}
                    <span class="source-type">${source.type}</span>
                </div>
                <div class="source-url">${escapeHtml(source.subreddit ? `r/${source.subreddit}` : source.url)}</div>
                <span class="source-category">${formatCategoryName(source.category)}</span>
            </div>
            <div class="source-actions">
                <label class="toggle-switch">
                    <input type="checkbox" ${source.enabled ? 'checked' : ''} onchange="toggleSource(${source.id})">
                    <span class="toggle-slider"></span>
                </label>
                <button class="delete-btn" onclick="deleteSource(${source.id}, '${escapeHtml(source.name)}')" title="Delete source">🗑</button>
            </div>
        </div>
    `).join('');
}

// Format category name for display
function formatCategoryName(categoryValue) {
    const cat = categoriesData.find(c => c.value === categoryValue);
    return cat ? cat.name : categoryValue.replace(/_/g, ' ');
}

// Add RSS source
async function addRssSource() {
    const name = document.getElementById('rss-name').value.trim();
    const url = document.getElementById('rss-url').value.trim();
    const category = document.getElementById('rss-category').value;

    if (!name || !url || !category) {
        alert('Please fill in all fields');
        return;
    }

    try {
        const response = await fetch(`${API_BASE}/api/sources`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({
                name,
                url,
                type: 'rss',
                category
            })
        });

        if (response.ok) {
            // Clear form
            document.getElementById('rss-name').value = '';
            document.getElementById('rss-url').value = '';
            document.getElementById('rss-category').value = '';

            // Reload sources
            await loadSources();
        } else {
            const error = await response.json();
            alert(error.detail || 'Failed to add source');
        }
    } catch (err) {
        console.error('Failed to add source:', err);
        alert('Failed to add source');
    }
}

// Add Reddit source
async function addRedditSource() {
    const subreddit = document.getElementById('reddit-subreddit').value.trim().replace(/^r\//, '');
    const sortBy = document.getElementById('reddit-sort').value;
    const category = document.getElementById('reddit-category').value;

    if (!subreddit || !category) {
        alert('Please fill in all fields');
        return;
    }

    try {
        const response = await fetch(`${API_BASE}/api/sources`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({
                name: `r/${subreddit}`,
                url: `https://reddit.com/r/${subreddit}`,
                type: 'reddit',
                category,
                subreddit,
                sort_by: sortBy,
                limit: 5
            })
        });

        if (response.ok) {
            // Clear form
            document.getElementById('reddit-subreddit').value = '';
            document.getElementById('reddit-category').value = '';

            // Reload sources
            await loadSources();
        } else {
            const error = await response.json();
            alert(error.detail || 'Failed to add subreddit');
        }
    } catch (err) {
        console.error('Failed to add subreddit:', err);
        alert('Failed to add subreddit');
    }
}

// Toggle source enabled/disabled
async function toggleSource(sourceId) {
    try {
        const response = await fetch(`${API_BASE}/api/sources/${sourceId}/toggle`, {
            method: 'POST'
        });

        if (response.ok) {
            const data = await response.json();
            // Update local data
            const source = sourcesData.find(s => s.id === sourceId);
            if (source) {
                source.enabled = data.enabled;
                renderSourceList();
            }
        }
    } catch (err) {
        console.error('Failed to toggle source:', err);
    }
}

// Delete source
async function deleteSource(sourceId, sourceName) {
    if (!confirm(`Delete "${sourceName}"? This will also remove all its articles.`)) {
        return;
    }

    try {
        const response = await fetch(`${API_BASE}/api/sources/${sourceId}`, {
            method: 'DELETE'
        });

        if (response.ok) {
            // Remove from local data and re-render
            sourcesData = sourcesData.filter(s => s.id !== sourceId);
            renderSourceList();
        }
    } catch (err) {
        console.error('Failed to delete source:', err);
        alert('Failed to delete source');
    }
}

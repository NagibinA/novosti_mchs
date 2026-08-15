// ============================================
// Карточка "Новости МЧС" для Home Assistant
// Версия: 1.0.2
// ============================================

class NewsMCHSCard extends HTMLElement {
  constructor() {
    super();
    this.attachShadow({ mode: 'open' });
    this._config = {};
    this._hass = null;
  }

  setConfig(config) {
    if (!config.entity) {
      throw new Error('Укажите entity');
    }
    this._config = {
      title: config.title || '📰 Новости МЧС',
      max_articles: config.max_articles || 15,
      show_description: config.show_description !== false,
      show_date: config.show_date !== false,
      show_image: config.show_image !== false,
      image_width: config.image_width || 100,
      image_height: config.image_height || 70,
      card_height: config.card_height || 400,
      ...config
    };
    this._render();
  }

  set hass(hass) {
    this._hass = hass;
    this._render();
  }

  _getArticles() {
    const state = this._hass?.states[this._config.entity];
    if (!state?.attributes?.articles) return [];
    return state.attributes.articles.slice(0, this._config.max_articles);
  }

  _render() {
    if (!this._hass) {
      this.shadowRoot.innerHTML = `<div style="padding:16px;text-align:center;">Загрузка...</div>`;
      return;
    }

    const articles = this._getArticles();
    let html = `
      <style>
        .card {
          background: var(--ha-card-background, white);
          border-radius: 12px;
          padding: 16px;
          box-shadow: var(--ha-card-box-shadow, 0 2px 4px rgba(0,0,0,0.1));
          max-height: ${this._config.card_height}px;
          display: flex;
          flex-direction: column;
        }
        .header {
          font-size: 20px;
          font-weight: bold;
          padding-bottom: 12px;
          border-bottom: 2px solid var(--divider-color, #e0e0e0);
          margin-bottom: 12px;
          flex-shrink: 0;
          display: flex;
          justify-content: space-between;
        }
        .header .count {
          font-size: 14px;
          font-weight: normal;
          color: var(--secondary-text-color, #666);
        }
        .articles {
          overflow-y: auto;
          flex: 1;
        }
        .article {
          padding: 10px 0;
          border-bottom: 1px solid var(--divider-color, #e0e0e0);
          display: flex;
          gap: 12px;
          cursor: pointer;
        }
        .article-content {
          flex: 1;
        }
        .article-title {
          font-weight: 500;
          color: var(--primary-text-color, #333);
        }
        .article-description {
          font-size: 13px;
          color: var(--secondary-text-color, #666);
          display: ${this._config.show_description ? 'block' : 'none'};
        }
        .article-date {
          font-size: 12px;
          color: var(--secondary-text-color, #999);
        }
        .article-image {
          width: ${this._config.image_width}px;
          height: ${this._config.image_height}px;
          object-fit: cover;
          border-radius: 6px;
          flex-shrink: 0;
          display: ${this._config.show_image ? 'block' : 'none'};
        }
        .empty {
          text-align: center;
          padding: 20px;
          color: var(--secondary-text-color, #666);
        }
      </style>
      <div class="card">
        <div class="header">
          <span>${this._config.title}</span>
          <span class="count">${articles.length} нов.</span>
        </div>
        <div class="articles">
    `;

    if (articles.length === 0) {
      html += `<div class="empty">Нет новостей</div>`;
    } else {
      articles.forEach(a => {
        html += `
          <div class="article" onclick="window.open('${a.link || '#'}', '_blank')">
            <div class="article-content">
              <div class="article-title">${a.title || 'Без названия'}</div>
              <div class="article-description">${(a.description || '').slice(0, 200)}</div>
              <div class="article-date">${a.pubDate || ''}</div>
            </div>
            ${a.image ? `<img class="article-image" src="${a.image}" loading="lazy" onerror="this.style.display='none'">` : ''}
          </div>
        `;
      });
    }

    html += `</div></div>`;
    this.shadowRoot.innerHTML = html;
  }

  getCardSize() {
    return 3;
  }
}

customElements.define('news-mchs-card', NewsMCHSCard);

// ============================================
// Карточка "Новости МЧС" для Home Assistant
// Версия: 1.1.1
// ============================================

class NewsMCHSCard extends HTMLElement {
  constructor() {
    super();
    this.attachShadow({ mode: 'open' });
    this._config = {};
    this._hass = null;
    this._entities = [];
    this._imageCache = new Map();
    this._lastArticlesHash = '';
  }

  static getConfigElement() {
    return document.createElement('news-mchs-card-editor');
  }

  static getStubConfig() {
    return {
      entity: "",
      title: "📰 Сводка ЧС",
      max_articles: 15,
      show_description: true,
      show_date: true,
      show_image: true,
      card_height: 400,
      image_width: 100,
      image_height: 70
    };
  }

  setConfig(config) {
    this._config = {
      entity: config.entity || "",
      title: config.title || '📰 Сводка ЧС',
      max_articles: config.max_articles || 15,
      show_description: config.show_description !== false,
      show_date: config.show_date !== false,
      show_image: config.show_image !== false,
      show_source: config.show_source !== false,
      image_width: config.image_width || 100,
      image_height: config.image_height || 70,
      card_height: config.card_height || 400,
      clickable: config.clickable !== false,
      source_color: config.source_color || '#e63946',
    };
    this._render();
  }

  set hass(hass) {
    this._hass = hass;
    this._findNovostiEntities();
    this._render();
  }

  _findNovostiEntities() {
    if (!this._hass) return;
    
    this._entities = [];
    for (const [entity_id, state] of Object.entries(this._hass.states)) {
      if (
        (entity_id.startsWith('sensor.novosti_mchs_') || 
         entity_id === 'sensor.novosti_mchs' ||
         entity_id.includes('novosti_mchs')) && 
        state.attributes && 
        state.attributes.articles
      ) {
        this._entities.push({
          entity_id: entity_id,
          name: state.attributes.friendly_name || entity_id,
          articles: state.attributes.articles
        });
      }
    }
    
    if (this._entities.length === 0) {
      for (const [entity_id, state] of Object.entries(this._hass.states)) {
        if (
          state.attributes && 
          state.attributes.articles &&
          (state.attributes.source_name === "Сводка ЧС и происшествий" ||
           state.attributes.filter === "только сводка ЧС и происшествий")
        ) {
          this._entities.push({
            entity_id: entity_id,
            name: state.attributes.friendly_name || entity_id,
            articles: state.attributes.articles
          });
          break;
        }
      }
    }
  }

  _getArticles() {
    if (this._config.entity) {
      const state = this._hass.states[this._config.entity];
      if (state && state.attributes && state.attributes.articles) {
        return state.attributes.articles.map(a => ({
          ...a,
          _source: state.attributes.source_name || this._config.entity
        }));
      }
      return [];
    }

    if (this._entities.length > 0) {
      const firstEntity = this._entities[0];
      const state = this._hass.states[firstEntity.entity_id];
      if (state && state.attributes && state.attributes.articles) {
        return state.attributes.articles.map(a => ({
          ...a,
          _source: state.attributes.source_name || firstEntity.entity_id
        }));
      }
    }

    return [];
  }

  _formatDate(dateStr) {
    if (!dateStr) return '';
    try {
      const date = new Date(dateStr);
      if (isNaN(date.getTime())) return dateStr;
      return date.toLocaleString('ru-RU', {
        day: '2-digit',
        month: '2-digit',
        year: 'numeric',
        hour: '2-digit',
        minute: '2-digit'
      });
    } catch {
      return dateStr;
    }
  }

  _escapeHtml(text) {
    if (!text) return '';
    const div = document.createElement('div');
    div.textContent = text;
    return div.innerHTML;
  }

  _getResizedImageUrl(url) {
    if (!url) return null;
    
    if (this._imageCache.has(url)) {
      return this._imageCache.get(url);
    }
    
    let resizedUrl = url;
    const w = this._config.image_width;
    const h = this._config.image_height;
    
    try {
      const urlObj = new URL(url);
      const hostname = urlObj.hostname;
      
      if (hostname.includes('yandex')) {
        urlObj.searchParams.set('w', w);
        urlObj.searchParams.set('h', h);
        urlObj.searchParams.set('crop', 'fill');
        resizedUrl = urlObj.toString();
      }
      else if (hostname.includes('mchs')) {
        const separator = url.includes('?') ? '&' : '?';
        resizedUrl = url + `${separator}w=${w}&h=${h}`;
      }
      else if (hostname.includes('vk')) {
        resizedUrl = url.replace(/\?.*$/, '') + `?w=${w}&h=${h}`;
      }
      else {
        const separator = url.includes('?') ? '&' : '?';
        resizedUrl = url + `${separator}width=${w}&height=${h}`;
      }
    } catch (e) {
      resizedUrl = url;
    }
    
    this._imageCache.set(url, resizedUrl);
    return resizedUrl;
  }

  _hasDataChanged(articles) {
    const hash = JSON.stringify(articles.map(a => a.title + a.pubDate));
    if (hash === this._lastArticlesHash) {
      return false;
    }
    this._lastArticlesHash = hash;
    return true;
  }

  _render() {
    if (!this._hass) {
      this.shadowRoot.innerHTML = `
        <div style="padding: 16px; text-align: center; color: var(--secondary-text-color, #666);">
          Загрузка...
        </div>
      `;
      return;
    }

    if (this._entities.length === 0 && !this._config.entity) {
      this.shadowRoot.innerHTML = `
        <style>
          .card {
            background: var(--ha-card-background, var(--card-background-color, white));
            border-radius: var(--ha-card-border-radius, 12px);
            padding: 16px;
            box-shadow: var(--ha-card-box-shadow, 0 2px 4px rgba(0,0,0,0.1));
            font-family: var(--paper-font-common-base, -apple-system, BlinkMacSystemFont, sans-serif);
            text-align: center;
          }
          .error {
            color: var(--error-color, #e53935);
            padding: 20px;
            font-size: 16px;
          }
          .hint {
            color: var(--secondary-text-color, #666);
            font-size: 14px;
            margin-top: 8px;
          }
        </style>
        <div class="card">
          <div class="error">⚠️ Сенсоры Новости МЧС не найдены</div>
          <div class="hint">Добавьте интеграцию "Новости МЧС" в Настройках</div>
        </div>
      `;
      return;
    }

    const articles = this._getArticles();
    
    if (!this._hasDataChanged(articles) && this._lastRenderHtml) {
      return;
    }

    const imgWidth = this._config.image_width;
    const imgHeight = this._config.image_height;

    let html = `
      <style>
        :host {
          display: block;
        }
        .card {
          background: var(--ha-card-background, var(--card-background-color, white));
          border-radius: var(--ha-card-border-radius, 12px);
          padding: 16px;
          box-shadow: var(--ha-card-box-shadow, 0 2px 4px rgba(0,0,0,0.1));
          max-height: ${this._config.card_height}px;
          display: flex;
          flex-direction: column;
          font-family: var(--paper-font-common-base, -apple-system, BlinkMacSystemFont, sans-serif);
        }
        .header {
          font-size: 20px;
          font-weight: bold;
          color: var(--primary-text-color, #333);
          padding-bottom: 12px;
          border-bottom: 2px solid var(--divider-color, #e0e0e0);
          margin-bottom: 12px;
          flex-shrink: 0;
          display: flex;
          justify-content: space-between;
          align-items: center;
        }
        .header .count {
          font-size: 14px;
          font-weight: normal;
          color: var(--secondary-text-color, #666);
        }
        .articles-container {
          overflow-y: auto;
          flex: 1;
          padding-right: 4px;
        }
        .articles-container::-webkit-scrollbar {
          width: 6px;
        }
        .articles-container::-webkit-scrollbar-track {
          background: var(--divider-color, #e0e0e0);
          border-radius: 3px;
        }
        .articles-container::-webkit-scrollbar-thumb {
          background: var(--secondary-text-color, #999);
          border-radius: 3px;
        }
        .article {
          padding: 10px 8px;
          border-bottom: 1px solid var(--divider-color, #e0e0e0);
          display: flex;
          gap: 12px;
          cursor: ${this._config.clickable ? 'pointer' : 'default'};
          transition: background 0.15s;
          border-radius: 8px;
          text-decoration: none;
          min-height: ${imgHeight + 10}px;
        }
        .article:hover {
          background: var(--hover-color, rgba(0,0,0,0.04));
        }
        .article-content {
          flex: 1;
          min-width: 0;
          display: flex;
          flex-direction: column;
          justify-content: flex-start;
        }
        .article-title {
          font-weight: 500;
          color: var(--primary-text-color, #333);
          margin-bottom: 4px;
          font-size: 14px;
          line-height: 1.3;
        }
        .article-description {
          font-size: 12px;
          color: var(--secondary-text-color, #666);
          line-height: 1.4;
          display: ${this._config.show_description ? 'block' : 'none'};
          word-break: break-word;
        }
        .article-meta {
          display: flex;
          gap: 8px;
          margin-top: 4px;
          font-size: 11px;
          color: var(--secondary-text-color, #999);
          flex-wrap: wrap;
          align-items: center;
        }
        .article-source {
          background: ${this._config.source_color};
          color: white;
          padding: 0 8px;
          border-radius: 4px;
          font-size: 10px;
          line-height: 18px;
          display: ${this._config.show_source ? 'inline-block' : 'none'};
        }
        .article-image-wrapper {
          flex-shrink: 0;
          width: ${imgWidth}px;
          min-width: ${imgWidth}px;
          max-width: ${imgWidth}px;
          height: ${imgHeight}px;
          min-height: ${imgHeight}px;
          max-height: ${imgHeight}px;
          border-radius: 6px;
          overflow: hidden;
          background: var(--divider-color, #e0e0e0);
          display: ${this._config.show_image ? 'block' : 'none'};
          position: relative;
        }
        .article-image-wrapper img {
          width: 100% !important;
          height: 100% !important;
          min-width: ${imgWidth}px !important;
          max-width: ${imgWidth}px !important;
          min-height: ${imgHeight}px !important;
          max-height: ${imgHeight}px !important;
          object-fit: cover !important;
          display: block !important;
        }
        .empty {
          color: var(--secondary-text-color, #666);
          text-align: center;
          padding: 30px 20px;
        }
      </style>
      <div class="card">
        <div class="header">
          <span>${this._escapeHtml(this._config.title)}</span>
          <span class="count">${articles.length} нов.</span>
        </div>
        <div class="articles-container">
    `;

    if (articles.length === 0) {
      html += `<div class="empty">Нет новостей. Проверьте подключение к интернету.</div>`;
    } else {
      const sortedArticles = [...articles].sort((a, b) => {
        const dateA = new Date(a.pubDate || a.updated || 0);
        const dateB = new Date(b.pubDate || b.updated || 0);
        return dateB - dateA;
      });

      sortedArticles.slice(0, this._config.max_articles).forEach((article, index) => {
        const resizedImageUrl = this._getResizedImageUrl(article.image);
        
        const imageHtml = resizedImageUrl && this._config.show_image
          ? `<div class="article-image-wrapper">
               <img 
                 src="${resizedImageUrl}" 
                 alt=""
                 loading="lazy"
                 onerror="this.parentElement.style.display='none'"
                 style="width:${imgWidth}px;height:${imgHeight}px;object-fit:cover;"
               >
             </div>`
          : '';

        const sourceLabel = article._source && this._config.show_source
          ? `<span class="article-source">${this._escapeHtml(article._source)}</span>`
          : '';

        const dateHtml = article.pubDate && this._config.show_date
          ? `<span>${this._formatDate(article.pubDate)}</span>`
          : '';

        const link = article.link || '#';
        const clickHandler = this._config.clickable && link !== '#'
          ? `window.open('${link}', '_blank')`
          : '';

        html += `
          <div class="article" onclick="${clickHandler}">
            <div class="article-content">
              <div class="article-title">${this._escapeHtml(article.title || 'Без названия')}</div>
              <div class="article-description">${this._escapeHtml(article.description || '').slice(0, 200)}${(article.description || '').length > 200 ? '...' : ''}</div>
              <div class="article-meta">
                ${sourceLabel}
                ${dateHtml}
              </div>
            </div>
            ${imageHtml}
          </div>
        `;
      });
    }

    html += `</div></div>`;
    this.shadowRoot.innerHTML = html;
    this._lastRenderHtml = html;
  }

  getCardSize() {
    return 3;
  }
}

// Регистрируем карточку для Lovelace
window.customCards = window.customCards || [];
window.customCards.push({
  type: 'news-mchs-card',
  name: 'Сводка ЧС',
  preview: true,
  description: 'Отображение новостей МЧС из RSS-ленты'
});

if (!customElements.get('news-mchs-card')) {
  customElements.define('news-mchs-card', NewsMCHSCard);
}

console.log('✅ Карточка Новости МЧС загружена!');

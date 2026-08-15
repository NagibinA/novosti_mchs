// ============================================
// Карточка "Новости МЧС" для Home Assistant
// Версия: 1.4.6
// Двухпанельный режим - С ПОЛНЫМ ТЕКСТОМ НОВОСТИ
// ============================================

class NewsMCHSCard extends HTMLElement {
  constructor() {
    super();
    this.attachShadow({ mode: 'open' });
    this._config = {};
    this._hass = null;
    this._entities = [];
    this._imageCache = new Map();
    this._selectedIndex = 0;
    this._articles = [];
    this._lastRenderHash = '';
    this._isRendering = false;
    this._scrollPosition = 0;
    this._listScrollPosition = 0;
  }

  static getConfigElement() {
    return document.createElement('news-mchs-card-editor');
  }

  static getStubConfig() {
    return {
      entity: "",
      title: "📰 Сводка ЧС",
      max_articles: 10,
      show_date: true,
      show_image: true,
      card_height: 500,
      image_width: 80,
      image_height: 60,
      source_color: '#e63946'
    };
  }

  setConfig(config) {
    this._config = {
      entity: config.entity || "",
      title: config.title || '📰 Сводка ЧС',
      max_articles: config.max_articles || 10,
      show_date: config.show_date !== false,
      show_image: config.show_image !== false,
      show_source: config.show_source !== false,
      image_width: config.image_width || 80,
      image_height: config.image_height || 60,
      card_height: config.card_height || 500,
      source_color: config.source_color || '#e63946',
    };
    this._selectedIndex = 0;
    this._scrollPosition = 0;
    this._listScrollPosition = 0;
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

  // === ОСНОВНАЯ ФУНКЦИЯ: ПОЛУЧЕНИЕ ТЕКСТА НОВОСТИ ===
  _getFullText(article) {
    if (!article) return 'Описание отсутствует';
    
    // Приоритет: full_text > text > description
    if (article.full_text && article.full_text.length > 10) {
      return this._cleanText(article.full_text);
    }
    if (article.text && article.text.length > 10) {
      return this._cleanText(article.text);
    }
    if (article.description && article.description.length > 10) {
      return this._cleanText(article.description);
    }
    return 'Полный текст новости отсутствует';
  }

  _cleanText(html) {
    if (!html) return 'Описание отсутствует';
    
    // Если текст уже очищен (не содержит HTML)
    if (!html.includes('<') && !html.includes('>')) {
      return html.trim() || 'Описание отсутствует';
    }
    
    let text = html
      .replace(/<br\s*\/?>/gi, '\n')
      .replace(/<\/p>/gi, '\n\n')
      .replace(/<[^>]+>/g, ' ')
      .replace(/\s+/g, ' ')
      .trim();
    
    return text || 'Описание отсутствует';
  }

  _getResizedImageUrl(url) {
    if (!url) return null;
    if (this._imageCache.has(url)) {
      return this._imageCache.get(url);
    }
    this._imageCache.set(url, url);
    return url;
  }

  _hasDataChanged(articles, selectedIndex) {
    const hash = JSON.stringify({
      titles: articles.map(a => a.title + a.pubDate),
      selected: selectedIndex
    });
    if (hash === this._lastRenderHash) {
      return false;
    }
    this._lastRenderHash = hash;
    return true;
  }

  _saveScrollPosition() {
    const listPanel = this.shadowRoot?.querySelector('.list-panel');
    if (listPanel) {
      this._listScrollPosition = listPanel.scrollTop;
    }
  }

  _restoreScrollPosition() {
    const listPanel = this.shadowRoot?.querySelector('.list-panel');
    if (listPanel && this._listScrollPosition > 0) {
      setTimeout(() => {
        listPanel.scrollTop = this._listScrollPosition;
      }, 50);
    }
  }

  _render() {
    if (this._isRendering) return;
    
    this._saveScrollPosition();
    
    if (!this._hass) {
      this.shadowRoot.innerHTML = `<div style="padding:16px;">Загрузка...</div>`;
      return;
    }

    if (this._entities.length === 0 && !this._config.entity) {
      this.shadowRoot.innerHTML = `
        <div style="padding:16px;text-align:center;color:var(--secondary-text-color,#666);">
          ⚠️ Сенсоры Новости МЧС не найдены
        </div>
      `;
      return;
    }

    const articles = this._getArticles();
    const sorted = [...articles].sort((a, b) => {
      const dateA = new Date(a.pubDate || a.updated || 0);
      const dateB = new Date(b.pubDate || b.updated || 0);
      return dateB - dateA;
    }).slice(0, this._config.max_articles);

    if (this._selectedIndex >= sorted.length) {
      this._selectedIndex = 0;
    }

    if (!this._hasDataChanged(sorted, this._selectedIndex)) {
      setTimeout(() => {
        this._restoreScrollPosition();
      }, 50);
      return;
    }

    this._isRendering = true;
    this._articles = sorted;
    const selected = this._articles[this._selectedIndex] || null;
    const cardHeight = this._config.card_height;

    // === ПОЛУЧАЕМ ПОЛНЫЙ ТЕКСТ НОВОСТИ ===
    const fullText = selected ? this._getFullText(selected) : '';

    let html = `
      <style>
        * { box-sizing: border-box; }
        .card {
          background: var(--ha-card-background, white);
          border-radius: 12px;
          box-shadow: var(--ha-card-box-shadow, 0 2px 4px rgba(0,0,0,0.1));
          height: ${cardHeight}px;
          display: flex;
          flex-direction: column;
          font-family: var(--paper-font-common-base, sans-serif);
          overflow: hidden;
        }
        .header {
          font-size: 18px;
          font-weight: bold;
          padding: 12px 16px;
          border-bottom: 2px solid var(--divider-color, #e0e0e0);
          flex-shrink: 0;
          display: flex;
          justify-content: space-between;
          align-items: center;
        }
        .header .count {
          font-size: 13px;
          font-weight: normal;
          color: var(--secondary-text-color, #666);
        }
        .main-layout {
          display: flex;
          flex: 1;
          overflow: hidden;
          min-height: 0;
        }
        .content-panel {
          flex: 3;
          overflow-y: auto;
          padding: 12px 16px;
          background: var(--primary-background-color, #fafafa);
        }
        .content-panel::-webkit-scrollbar { width: 6px; }
        .content-panel::-webkit-scrollbar-track { background: var(--divider-color, #e0e0e0); border-radius: 3px; }
        .content-panel::-webkit-scrollbar-thumb { background: var(--secondary-text-color, #999); border-radius: 3px; }
        
        .content-title {
          font-size: 20px;
          font-weight: 700;
          color: var(--primary-text-color, #333);
          margin-bottom: 8px;
          line-height: 1.3;
        }
        .content-meta {
          display: flex;
          gap: 12px;
          font-size: 13px;
          color: var(--secondary-text-color, #999);
          margin-bottom: 12px;
          flex-wrap: wrap;
          align-items: center;
          padding-bottom: 10px;
          border-bottom: 1px solid var(--divider-color, #e0e0e0);
        }
        .content-image {
          width: 100%;
          max-height: 300px;
          object-fit: cover;
          border-radius: 8px;
          margin-bottom: 14px;
        }
        .content-text {
          font-size: 15px;
          line-height: 1.8;
          color: var(--primary-text-color, #333);
          white-space: pre-wrap;
          word-break: break-word;
        }
        .content-placeholder {
          color: var(--secondary-text-color, #999);
          text-align: center;
          padding: 60px 20px;
          font-size: 16px;
        }
        .content-link {
          display: inline-block;
          margin-top: 14px;
          color: var(--primary-color, #03a9f4);
          text-decoration: none;
          font-weight: 500;
          padding: 6px 16px;
          border: 1px solid var(--primary-color, #03a9f4);
          border-radius: 6px;
          transition: background 0.2s;
        }
        .content-link:hover { 
          background: var(--primary-color, #03a9f4);
          color: white;
        }
        
        .list-panel {
          flex: 2;
          min-width: 200px;
          border-left: 1px solid var(--divider-color, #e0e0e0);
          overflow-y: auto;
          background: var(--ha-card-background, white);
        }
        .list-panel::-webkit-scrollbar { width: 6px; }
        .list-panel::-webkit-scrollbar-track { background: var(--divider-color, #e0e0e0); border-radius: 3px; }
        .list-panel::-webkit-scrollbar-thumb { background: var(--secondary-text-color, #999); border-radius: 3px; }
        
        .list-header {
          font-size: 13px;
          font-weight: 600;
          color: var(--secondary-text-color, #777);
          padding: 8px 12px;
          border-bottom: 1px solid var(--divider-color, #e0e0e0);
          position: sticky;
          top: 0;
          background: var(--ha-card-background, white);
          z-index: 1;
        }
        .list-item {
          padding: 8px 12px;
          border-bottom: 1px solid var(--divider-color, #e0e0e0);
          cursor: pointer;
          transition: background 0.15s;
        }
        .list-item:hover { background: var(--hover-color, rgba(0,0,0,0.05)); }
        .list-item.active {
          background: var(--primary-color, #03a9f4);
          color: white;
        }
        .list-item.active .list-title { color: white; }
        .list-item.active .list-meta { color: rgba(255,255,255,0.8); }
        
        .list-title {
          font-weight: 500;
          color: var(--primary-text-color, #333);
          font-size: 13px;
          line-height: 1.3;
          margin-bottom: 2px;
        }
        .list-meta {
          display: flex;
          gap: 6px;
          font-size: 10px;
          color: var(--secondary-text-color, #999);
          flex-wrap: wrap;
          align-items: center;
        }
        .list-empty {
          color: var(--secondary-text-color, #999);
          text-align: center;
          padding: 30px 20px;
          font-size: 14px;
        }
        @media (max-width: 700px) {
          .main-layout { flex-direction: column-reverse; }
          .list-panel { flex: none; height: 200px; border-left: none; border-top: 1px solid var(--divider-color, #e0e0e0); }
          .content-panel { flex: 1; min-height: 0; }
          .content-title { font-size: 17px; }
        }
      </style>
      
      <div class="card">
        <div class="header">
          <span>${this._escapeHtml(this._config.title)}</span>
          <span class="count">${this._articles.length} нов.</span>
        </div>
        
        <div class="main-layout">
          <div class="content-panel">
    `;

    if (this._articles.length === 0) {
      html += `<div class="content-placeholder">Нет новостей</div>`;
    } else if (selected) {
      const imageUrl = this._getResizedImageUrl(selected.image);
      
      html += `
        <div class="content-title">${this._escapeHtml(selected.title || 'Без названия')}</div>
        <div class="content-meta">
          ${selected.pubDate && this._config.show_date ? `<span>📅 ${this._formatDate(selected.pubDate)}</span>` : ''}
          ${selected.link && selected.link !== '#' ? `<span>🔗 <a href="${selected.link}" target="_blank" style="color:var(--primary-color);text-decoration:none;">Источник</a></span>` : ''}
        </div>
        ${imageUrl && this._config.show_image ? `<img class="content-image" src="${imageUrl}" onerror="this.style.display='none'">` : ''}
        <div class="content-text">${this._escapeHtml(fullText)}</div>
        ${selected.link && selected.link !== '#' ? `<a class="content-link" href="${selected.link}" target="_blank">📖 Читать на сайте МЧС</a>` : ''}
      `;
    }

    html += `
          </div>
          
          <div class="list-panel">
            <div class="list-header">📋 Список новостей</div>
    `;

    if (this._articles.length === 0) {
      html += `<div class="list-empty">Нет новостей</div>`;
    } else {
      this._articles.forEach((article, index) => {
        const isActive = index === this._selectedIndex;
        
        html += `
          <div class="list-item ${isActive ? 'active' : ''}" data-index="${index}">
            <div>
              <div class="list-title">${this._escapeHtml(article.title || 'Без названия')}</div>
              <div class="list-meta">
                ${article.pubDate && this._config.show_date ? `<span>${this._formatDate(article.pubDate)}</span>` : ''}
              </div>
            </div>
          </div>
        `;
      });
    }

    html += `
          </div>
        </div>
      </div>
    `;

    this.shadowRoot.innerHTML = html;

    this._restoreScrollPosition();

    const items = this.shadowRoot.querySelectorAll('.list-item');
    items.forEach((item) => {
      item.addEventListener('click', (event) => {
        const listPanel = this.shadowRoot?.querySelector('.list-panel');
        if (listPanel) {
          this._listScrollPosition = listPanel.scrollTop;
        }
        
        const index = parseInt(event.currentTarget.dataset.index, 10);
        if (!isNaN(index) && index !== this._selectedIndex) {
          this._selectedIndex = index;
          this._lastRenderHash = '';
          this._render();
        }
      });
    });

    this._isRendering = false;
  }

  getCardSize() {
    return 5;
  }
}

window.customCards = window.customCards || [];
window.customCards.push({
  type: 'news-mchs-card',
  name: 'Сводка ЧС (двухпанельная)',
  preview: true,
  description: 'Двухпанельный просмотр новостей МЧС с полным текстом'
});

if (!customElements.get('news-mchs-card')) {
  customElements.define('news-mchs-card', NewsMCHSCard);
}

console.log('✅ Карточка Новости МЧС загружена!');
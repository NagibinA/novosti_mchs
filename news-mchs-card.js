// ============================================
// Карточка "Новости МЧС" для Home Assistant
// Версия: 1.0.0
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
      throw new Error('Укажите entity (сенсор с новостями)');
    }
    this._config = {
      title: config.title || '📰 Новости МЧС',
      max_articles: config.max_articles || 15,
      show_description: config.show_description !== undefined ? config.show_description : true,
      show_date: config.show_date !== undefined ? config.show_date : true,
      show_image: config.show_image !== undefined ? config.show_image : true,
      show_source: config.show_source !== undefined ? config.show_source : true,
      image_width: config.image_width || 100,
      image_height: config.image_height || 70,
      card_height: config.card_height || 400,
      clickable: config.clickable !== undefined ? config.clickable : true,
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
    if (!state || !state.attributes || !state.attributes.articles) {
      return [];
    }
    
    const articles = state.attributes.articles.map(a => ({
      ...a,
      _source: state.attributes.source_name || this._config.entity
    }));

    // Сортируем по дате (новые сверху)
    articles.sort((a, b) => {
      const dateA = new Date(a.pubDate || a.updated || 0);
      const dateB = new Date(b.pubDate || b.updated || 0);
      return dateB - dateA;
    });

    return articles.slice(0, this._config.max_articles);
  }

  _render() {
    if (!this._hass) {
      this.shadowRoot.innerHTML = `<div style="padding: 16px; text-align: center; color: var(--secondary-text-color);">Загрузка...</div>`;
      return;
    }

    const articles = this._getArticles();

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
          font-family: var(--paper-font-common-base, -apple-system, BlinkMacSystemFont, sans-serif);
          max-height: ${this._config.card_height}px;
          display: flex;
          flex-direction: column;
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
        }
        .article:hover {
          background: var(--hover-color, rgba(0,0,0,0.04));
        }
        .article-content {
          flex: 1;
          min-width: 0;
        }
        .article-title {
          font-weight: 500;
          color: var(--primary-text-color, #333);
          margin-bottom: 4px;
          font-size: 15px;
          line-height: 1.3;
        }
        .article-description {
          font-size: 13px;
          color: var(--secondary-text-color, #666);
          line-height: 1.4;
          display: ${this._config.show_description ? 'block' : 'none'};
        }
        .article-meta {
          display: flex;
          gap: 12px;
          margin-top: 4px;
          font-size: 12px;
          color: var(--secondary-text-color, #999);
          flex-wrap: wrap;
        }
        .article-source {
          background: var(--source-color, #e63946);
          color: white;
          padding: 0 8px;
          border-radius: 4px;
          font-size: 11px;
          line-height: 20px;
          display: ${this._config.show_source ? 'inline-block' : 'none'};
        }
        .article-image {
          width: ${this._config.image_width}px;
          height: ${this._config.image_height}px;
          object-fit: cover;
          border-radius: 6px;
          flex-shrink: 0;
          background: var(--divider-color, #e0e0e0);
          display: ${this._config.show_image ? 'block' : 'none'};
        }
        .empty {
          color: var(--secondary-text-color, #666);
          text-align: center;
          padding: 30px 20px;
        }
        .source-badge {
          display: inline-block;
          background: var(--source-color, #e63946);
          color: white;
          padding: 0 10px;
          border-radius: 4px;
          font-size: 11px;
          line-height: 20px;
        }
      </style>
      <div class="card">
        <div class="header">
          <span>${this._config.title}</span>
          <span class="count">${articles.length} нов.</span>
        </div>
        <div class="articles-container">
    `;

    if (articles.length === 0) {
      html += `<div class="empty">Нет новостей. Проверьте подключение к интернету.</div>`;
    } else {
      articles.forEach(article => {
        const imageHtml = article.image && this._config.show_image
          ? `<img class="article-image" src="${article.image}" alt="" loading="lazy" onerror="this.style.display='none'">`
          : '';

        const sourceLabel = article._source && this._config.show_source
          ? `<span class="article-source">${article._source}</span>`
          : '';

        const dateHtml = article.pubDate && this._config.show_date
          ? `<span>${this._formatDate(article.pubDate)}</span>`
          : '';

        const link = article.link || '#';

        html += `
          <div class="article" onclick="${this._config.clickable ? `window.open('${link}', '_blank')` : ''}">
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
  }

  _formatDate(dateStr) {
    if (!dateStr) return '';
    try {
      const date = new Date(dateStr);
      if (isNaN(date)) return dateStr;
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

  getCardSize() {
    return 3;
  }
}

customElements.define('news-mchs-card', NewsMCHSCard);

// ============================================
// Редактор карточки (визуальный)
// ============================================

class NewsMCHSCardEditor extends HTMLElement {
  constructor() {
    super();
    this._config = {};
    this._hass = null;
  }

  setConfig(config) {
    this._config = { ...config };
    this._render();
  }

  set hass(hass) {
    this._hass = hass;
    this._render();
  }

  _getAvailableEntities() {
    if (!this._hass) return [];
    return Object.keys(this._hass.states)
      .filter(key => key.startsWith('sensor.novosti_mchs_'))
      .map(key => ({
        value: key,
        label: `${key} (${this._hass.states[key].attributes.source_name || 'МЧС'})`
      }));
  }

  _render() {
    if (!this._hass) {
      this.innerHTML = `<div>Загрузка...</div>`;
      return;
    }

    const entities = this._getAvailableEntities();
    const config = this._config;

    if (!config.entity && entities.length > 0) {
      config.entity = entities[0].value;
    }

    const currentEntity = config.entity || '';

    this.innerHTML = `
      <div style="padding: 12px; font-family: var(--paper-font-common-base, sans-serif);">
        <h3 style="margin: 0 0 12px 0; font-size: 16px;">⚙️ Настройка карточки Новости МЧС</h3>
        
        <div style="margin-bottom: 12px;">
          <label style="display: block; margin-bottom: 4px; font-weight: 500; font-size: 14px;">Сенсор новостей:</label>
          <select id="entity" style="width: 100%; padding: 8px; border-radius: 4px; border: 1px solid var(--divider-color, #ccc); background: var(--card-background-color, white);">
            ${entities.map(e => 
              `<option value="${e.value}" ${currentEntity === e.value ? 'selected' : ''}>${e.label}</option>`
            ).join('')}
            ${entities.length === 0 ? '<option value="">Нет сенсоров. Установите интеграцию.</option>' : ''}
          </select>
        </div>

        <div style="margin-bottom: 12px;">
          <label style="display: block; margin-bottom: 4px; font-weight: 500; font-size: 14px;">Заголовок карточки:</label>
          <input id="title" type="text" value="${config.title || ''}" style="width: 100%; padding: 8px; border-radius: 4px; border: 1px solid var(--divider-color, #ccc); background: var(--card-background-color, white);" placeholder="📰 Новости МЧС">
        </div>

        <div style="margin-bottom: 12px;">
          <label style="display: block; margin-bottom: 4px; font-weight: 500; font-size: 14px;">Максимум новостей:</label>
          <input id="max_articles" type="number" value="${config.max_articles || 15}" min="1" max="50" style="width: 100%; padding: 8px; border-radius: 4px; border: 1px solid var(--divider-color, #ccc); background: var(--card-background-color, white);">
        </div>

        <div style="margin-bottom: 12px;">
          <label style="display: block; margin-bottom: 4px; font-weight: 500; font-size: 14px;">Высота карточки (px):</label>
          <input id="card_height" type="number" value="${config.card_height || 400}" min="200" max="800" style="width: 100%; padding: 8px; border-radius: 4px; border: 1px solid var(--divider-color, #ccc); background: var(--card-background-color, white);">
        </div>

        <div style="display: grid; grid-template-columns: 1fr 1fr; gap: 8px; margin-bottom: 12px;">
          <div>
            <label style="display: block; margin-bottom: 4px; font-weight: 500; font-size: 13px;">Ширина картинки:</label>
            <input id="image_width" type="number" value="${config.image_width || 100}" min="50" max="200" style="width: 100%; padding: 8px; border-radius: 4px; border: 1px solid var(--divider-color, #ccc); background: var(--card-background-color, white);">
          </div>
          <div>
            <label style="display: block; margin-bottom: 4px; font-weight: 500; font-size: 13px;">Высота картинки:</label>
            <input id="image_height" type="number" value="${config.image_height || 70}" min="50" max="200" style="width: 100%; padding: 8px; border-radius: 4px; border: 1px solid var(--divider-color, #ccc); background: var(--card-background-color, white);">
          </div>
        </div>

        <div style="display: grid; grid-template-columns: 1fr 1fr; gap: 8px; margin-bottom: 16px;">
          <label style="display: flex; align-items: center; gap: 6px; font-size: 14px;">
            <input id="show_description" type="checkbox" ${config.show_description !== false ? 'checked' : ''}>
            Показывать описание
          </label>
          <label style="display: flex; align-items: center; gap: 6px; font-size: 14px;">
            <input id="show_date" type="checkbox" ${config.show_date !== false ? 'checked' : ''}>
            Показывать дату
          </label>
          <label style="display: flex; align-items: center; gap: 6px; font-size: 14px;">
            <input id="show_image" type="checkbox" ${config.show_image !== false ? 'checked' : ''}>
            Показывать картинки
          </label>
          <label style="display: flex; align-items: center; gap: 6px; font-size: 14px;">
            <input id="show_source" type="checkbox" ${config.show_source !== false ? 'checked' : ''}>
            Показывать источник
          </label>
        </div>

        <button id="apply" style="width: 100%; padding: 10px; background: #03a9f4; color: white; border: none; border-radius: 4px; cursor: pointer; font-size: 14px; font-weight: 500;">
          ✅ Применить настройки
        </button>
      </div>
    `;

    this.querySelector('#apply').addEventListener('click', () => {
      const newConfig = {
        entity: this.querySelector('#entity').value,
        title: this.querySelector('#title').value || '📰 Новости МЧС',
        max_articles: parseInt(this.querySelector('#max_articles').value) || 15,
        card_height: parseInt(this.querySelector('#card_height').value) || 400,
        image_width: parseInt(this.querySelector('#image_width').value) || 100,
        image_height: parseInt(this.querySelector('#image_height').value) || 70,
        show_description: this.querySelector('#show_description').checked,
        show_date: this.querySelector('#show_date').checked,
        show_image: this.querySelector('#show_image').checked,
        show_source: this.querySelector('#show_source').checked,
      };

      this._config = newConfig;
      this.dispatchEvent(new CustomEvent('config-changed', {
        detail: { config: newConfig }
      }));
    });
  }
}

customElements.define('news-mchs-card-editor', NewsMCHSCardEditor);

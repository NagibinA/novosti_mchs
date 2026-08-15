import feedparser
import async_timeout
from datetime import timedelta
import logging
import re

from homeassistant.helpers.entity import Entity
from homeassistant.helpers.update_coordinator import (
    DataUpdateCoordinator,
    CoordinatorEntity,
)
from homeassistant.const import CONF_NAME

from .const import DOMAIN, DEFAULT_SCAN_INTERVAL, CONF_RSS_URL, CONF_SOURCES_COUNT, ATTR_ARTICLES

_LOGGER = logging.getLogger(__name__)

async def async_setup_entry(hass, config_entry, async_add_entities):
    """Настройка сенсоров"""
    rss_url = config_entry.data.get(CONF_RSS_URL)
    sources_count = config_entry.data.get(CONF_SOURCES_COUNT, 1)
    base_name = config_entry.data.get(CONF_NAME, "Новости МЧС")
    scan_interval = config_entry.options.get(CONF_SCAN_INTERVAL, DEFAULT_SCAN_INTERVAL)

    coordinator = RSSDataUpdateCoordinator(
        hass,
        rss_url=rss_url,
        update_interval=timedelta(seconds=scan_interval),
    )

    await coordinator.async_refresh()

    entities = []
    for i in range(sources_count):
        entities.append(
            RSSNewsSensor(
                coordinator,
                base_name,
                i + 1,
                sources_count
            )
        )

    async_add_entities(entities)


class RSSDataUpdateCoordinator(DataUpdateCoordinator):
    def __init__(self, hass, rss_url, update_interval):
        super().__init__(
            hass,
            _LOGGER,
            name="RSS MCHS",
            update_interval=update_interval,
        )
        self.rss_url = rss_url
        self.articles = []

    async def _async_update_data(self):
        try:
            async with async_timeout.timeout(30):
                feed = await self.hass.async_add_executor_job(
                    feedparser.parse, self.rss_url
                )

                articles = []
                for entry in feed.entries[:10]:
                    article = {
                        "title": entry.get("title", "Без названия"),
                        "link": entry.get("link", ""),
                        "description": self._clean_description(entry.get("description", "")),
                        "pubDate": self._format_date(entry.get("published", entry.get("updated", ""))),
                        "image": self._extract_image(entry),
                        "source": self.rss_url,
                    }
                    articles.append(article)

                self.articles = articles
                return {"articles": articles}

        except Exception as e:
            _LOGGER.error(f"Ошибка загрузки RSS: {e}")
            return {"articles": []}

    def _clean_description(self, description):
        if not description:
            return ""
        clean = re.sub(r'<[^>]+>', '', description)
        clean = re.sub(r'\s+', ' ', clean).strip()
        return clean[:250] + "..." if len(clean) > 250 else clean

    def _extract_image(self, entry):
        if hasattr(entry, 'media_content') and entry.media_content:
            for media in entry.media_content:
                if 'url' in media:
                    return media['url']
        
        if hasattr(entry, 'links'):
            for link in entry.links:
                if link.get('type', '').startswith('image/'):
                    return link.get('href')
        
        if hasattr(entry, 'description'):
            img_match = re.search(r'<img[^>]+src=["\']([^"\']+)["\']', entry.description)
            if img_match:
                return img_match.group(1)
        
        return None

    def _format_date(self, date_str):
        if not date_str:
            return ""
        return date_str


class RSSNewsSensor(CoordinatorEntity, Entity):
    def __init__(self, coordinator, base_name, source_number, total_sources):
        super().__init__(coordinator)
        self._name = f"{base_name} {source_number}" if total_sources > 1 else base_name
        self._source_number = source_number
        self._unique_id = f"{DOMAIN}_{source_number}"

    @property
    def name(self):
        return self._name

    @property
    def unique_id(self):
        return self._unique_id

    @property
    def state(self):
        articles = self.coordinator.data.get("articles", []) if self.coordinator.data else []
        return len(articles)

    @property
    def extra_state_attributes(self):
        articles = self.coordinator.data.get("articles", []) if self.coordinator.data else []
        
        if articles:
            return {
                ATTR_ARTICLES: articles[:10],
                "source_name": self._name,
                "count": len(articles),
                "updated": self.coordinator.last_update_success,
            }
        return {
            ATTR_ARTICLES: [],
            "source_name": self._name,
            "count": 0,
            "updated": self.coordinator.last_update_success,
        }

    @property
    def icon(self):
        return "mdi:rss"

    @property
    def unit_of_measurement(self):
        return "нов."

    @property
    def available(self):
        return self.coordinator.last_update_success

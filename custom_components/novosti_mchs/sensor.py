"""Сенсоры для интеграции Новости МЧС."""
from datetime import timedelta
import logging
import re
import xml.etree.ElementTree as ET

import aiohttp
import async_timeout

from homeassistant.helpers.entity import Entity
from homeassistant.helpers.update_coordinator import (
    DataUpdateCoordinator,
    CoordinatorEntity,
)
from homeassistant.const import CONF_NAME

from .const import (
    DOMAIN,
    DEFAULT_SCAN_INTERVAL,
    CONF_RSS_URL,
    CONF_SOURCES_COUNT,
    ATTR_ARTICLES,
)

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(hass, config_entry, async_add_entities):
    """Настройка сенсоров."""
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
                sources_count,
            )
        )

    async_add_entities(entities)


class RSSDataUpdateCoordinator(DataUpdateCoordinator):
    """Координатор для загрузки данных из RSS."""

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
        """Загрузка данных из RSS."""
        try:
            async with async_timeout.timeout(30):
                async with aiohttp.ClientSession() as session:
                    async with session.get(self.rss_url) as response:
                        if response.status != 200:
                            _LOGGER.error(
                                "Ошибка загрузки RSS: статус %s", response.status
                            )
                            return {"articles": []}
                        xml_text = await response.text()

            # Парсим XML
            articles = await self.hass.async_add_executor_job(
                self._parse_rss, xml_text
            )

            self.articles = articles
            return {"articles": articles}

        except aiohttp.ClientError as e:
            _LOGGER.error("Ошибка подключения к RSS: %s", e)
            return {"articles": []}
        except Exception as e:
            _LOGGER.error("Ошибка загрузки RSS: %s", e)
            return {"articles": []}

    def _parse_rss(self, xml_text):
        """Парсинг RSS ленты."""
        articles = []
        try:
            root = ET.fromstring(xml_text)

            # Ищем все элементы <item>
            for item in root.findall(".//item")[:10]:
                # Извлекаем данные
                title = item.find("title")
                link = item.find("link")
                description = item.find("description")
                pub_date = item.find("pubDate")

                # Пытаемся найти картинку
                image = self._extract_image_from_item(item)

                article = {
                    "title": title.text if title is not None and title.text else "Без названия",
                    "link": link.text if link is not None and link.text else "",
                    "description": self._clean_description(
                        description.text if description is not None else ""
                    ),
                    "pubDate": pub_date.text if pub_date is not None and pub_date.text else "",
                    "image": image,
                }
                articles.append(article)

        except ET.ParseError as e:
            _LOGGER.error("Ошибка парсинга XML: %s", e)
        except Exception as e:
            _LOGGER.error("Ошибка обработки RSS: %s", e)

        return articles

    def _clean_description(self, description):
        """Очистка описания от HTML."""
        if not description:
            return ""
        clean = re.sub(r"<[^>]+>", "", description)
        clean = re.sub(r"\s+", " ", clean).strip()
        return clean[:250] + "..." if len(clean) > 250 else clean

    def _extract_image_from_item(self, item):
        """Извлечение изображения из элемента item."""
        # Проверяем <enclosure>
        enclosure = item.find("enclosure")
        if enclosure is not None:
            url = enclosure.get("url")
            if url:
                return url

        # Проверяем <media:content>
        media_content = item.find("media:content")
        if media_content is not None:
            url = media_content.get("url")
            if url:
                return url

        # Ищем картинку в описании
        description = item.find("description")
        if description is not None and description.text:
            img_match = re.search(r'<img[^>]+src=["\']([^"\']+)["\']', description.text)
            if img_match:
                return img_match.group(1)

        return None


class RSSNewsSensor(CoordinatorEntity, Entity):
    """Сенсор с новостями."""

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
        """Количество новостей."""
        articles = self.coordinator.data.get("articles", []) if self.coordinator.data else []
        return len(articles)

    @property
    def extra_state_attributes(self):
        """Атрибуты с новостями."""
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

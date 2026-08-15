"""Сенсоры для интеграции Новости МЧС."""
import logging
import re
import xml.etree.ElementTree as ET
from datetime import timedelta
from typing import Any, Dict, List, Optional

import aiohttp
import async_timeout

from homeassistant.components.sensor import SensorEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import (
    CoordinatorEntity,
    DataUpdateCoordinator,
    UpdateFailed,
)
from homeassistant.const import CONF_NAME

from .const import (
    DOMAIN,
    DEFAULT_SCAN_INTERVAL,
    CONF_RSS_URL,
    CONF_SCAN_INTERVAL,
    ATTR_ARTICLES,
)

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Настройка сенсоров из конфигурации."""
    _LOGGER.debug("🔄 Настройка сенсоров Новости МЧС")
    
    rss_url = config_entry.data.get(CONF_RSS_URL)
    base_name = config_entry.data.get(CONF_NAME, "Новости МЧС")
    scan_interval = config_entry.options.get(CONF_SCAN_INTERVAL, config_entry.data.get(CONF_SCAN_INTERVAL, DEFAULT_SCAN_INTERVAL))

    _LOGGER.debug("   URL: %s", rss_url)
    _LOGGER.debug("   Интервал обновления: %d сек", scan_interval)

    # Создаём координатор
    coordinator = RSSDataUpdateCoordinator(
        hass,
        rss_url=rss_url,
        update_interval=timedelta(seconds=scan_interval),
    )

    # Выполняем первый запрос
    await coordinator.async_refresh()

    # Создаём ОДИН сенсор с фильтрацией
    entities = [
        RSSNewsSensor(
            coordinator,
            base_name,
        )
    ]

    _LOGGER.info("✅ Создан 1 сенсор Новости МЧС (только сводка ЧС)")
    async_add_entities(entities)


class RSSDataUpdateCoordinator(DataUpdateCoordinator[Dict[str, Any]]):
    """Координатор для загрузки данных из RSS."""

    def __init__(
        self,
        hass: HomeAssistant,
        rss_url: str,
        update_interval: timedelta,
    ) -> None:
        """Инициализация координатора."""
        super().__init__(
            hass,
            _LOGGER,
            name=DOMAIN,
            update_interval=update_interval,
        )
        self.rss_url = rss_url
        self._last_error: Optional[str] = None

    async def _async_update_data(self) -> Dict[str, Any]:
        """Загрузка данных из RSS."""
        _LOGGER.debug("📡 Загрузка RSS: %s", self.rss_url)
        
        try:
            async with async_timeout.timeout(30):
                async with aiohttp.ClientSession() as session:
                    async with session.get(
                        self.rss_url,
                        headers={"User-Agent": "Home Assistant/2024.1"}
                    ) as response:
                        if response.status != 200:
                            _LOGGER.error(
                                "❌ Ошибка RSS: статус %s, URL: %s",
                                response.status,
                                self.rss_url
                            )
                            raise UpdateFailed(f"HTTP ошибка {response.status}")
                        
                        xml_text = await response.text()
                        _LOGGER.debug("   Загружено %d байт", len(xml_text))

            # Парсим XML в отдельном потоке
            articles = await self.hass.async_add_executor_job(
                self._parse_rss, xml_text
            )
            
            # ФИЛЬТРУЕМ: оставляем только новости со сводкой ЧС
            filtered_articles = self._filter_emergency_news(articles)
            
            _LOGGER.debug("✅ Загружено %d новостей, отфильтровано %d (сводка ЧС)", 
                         len(articles), len(filtered_articles))
            self._last_error = None
            return {"articles": filtered_articles}

        except aiohttp.ClientError as e:
            _LOGGER.error("❌ Ошибка подключения: %s", e)
            self._last_error = str(e)
            raise UpdateFailed(f"Ошибка подключения: {e}") from e
        
        except ET.ParseError as e:
            _LOGGER.error("❌ Ошибка парсинга XML: %s", e)
            self._last_error = str(e)
            raise UpdateFailed(f"Ошибка парсинга XML: {e}") from e
        
        except Exception as e:
            _LOGGER.error("❌ Неизвестная ошибка: %s", e)
            self._last_error = str(e)
            raise UpdateFailed(f"Неизвестная ошибка: {e}") from e

    def _filter_emergency_news(self, articles: List[Dict[str, str]]) -> List[Dict[str, str]]:
        """Фильтрует новости, оставляя только сводку ЧС и происшествий."""
        if not articles:
            return []
        
        # Ключевые слова для фильтрации
        keywords = [
            "сводка",
            "происшествие",
            "чс",
            "чрезвычайная",
            "пожар",
            "спасение",
            "пострадал",
            "эвакуация",
            "авария",
            "обрушение",
            "затопление",
            "взрыв",
            "дтп",
            "авиакатастрофа",
            "землетрясение",
            "наводнение",
            "ураган",
            "шторм",
        ]
        
        filtered = []
        for article in articles:
            title = (article.get("title", "") or "").lower()
            description = (article.get("description", "") or "").lower()
            text = title + " " + description
            
            # Проверяем наличие ключевых слов
            for keyword in keywords:
                if keyword in text:
                    filtered.append(article)
                    break
        
        # Если ничего не найдено, показываем первые 3 новости
        if not filtered:
            _LOGGER.debug("⚠️ Новостей со сводкой ЧС не найдено, показываем первые 3")
            return articles[:3]
        
        return filtered

    def _parse_rss(self, xml_text: str) -> List[Dict[str, str]]:
        """Парсинг RSS ленты."""
        articles: List[Dict[str, str]] = []
        
        try:
            root = ET.fromstring(xml_text)
            
            # Находим все элементы <item>
            items = root.findall(".//item")
            _LOGGER.debug("   Найдено элементов <item>: %d", len(items))
            
            for idx, item in enumerate(items[:20]):
                try:
                    title_elem = item.find("title")
                    link_elem = item.find("link")
                    description_elem = item.find("description")
                    pub_date_elem = item.find("pubDate")
                    
                    title = title_elem.text if title_elem is not None and title_elem.text else "Без названия"
                    link = link_elem.text if link_elem is not None and link_elem.text else ""
                    description = description_elem.text if description_elem is not None else ""
                    pub_date = pub_date_elem.text if pub_date_elem is not None and pub_date_elem.text else ""
                    
                    description_clean = self._clean_description(description)
                    image = self._extract_image(item)
                    
                    article = {
                        "title": title,
                        "link": link,
                        "description": description_clean,
                        "pubDate": pub_date,
                        "image": image,
                    }
                    articles.append(article)
                    
                except Exception as e:
                    _LOGGER.warning("⚠️ Ошибка обработки элемента #%d: %s", idx + 1, e)
                    continue
                    
        except ET.ParseError as e:
            _LOGGER.error("❌ Ошибка парсинга XML: %s", e)
            raise
        
        except Exception as e:
            _LOGGER.error("❌ Ошибка обработки RSS: %s", e)
            raise
        
        return articles

    def _clean_description(self, description: str) -> str:
        """Очистка описания от HTML-тегов."""
        if not description:
            return ""
        
        clean = re.sub(r"<[^>]+>", "", description)
        clean = re.sub(r"\s+", " ", clean).strip()
        if len(clean) > 500:
            clean = clean[:500] + "..."
        return clean

    def _extract_image(self, item: ET.Element) -> Optional[str]:
        """Извлечение изображения из элемента."""
        try:
            enclosure = item.find("enclosure")
            if enclosure is not None:
                url = enclosure.get("url")
                if url:
                    return url
            
            media = item.find("media:content")
            if media is not None:
                url = media.get("url")
                if url:
                    return url
            
            thumbnail = item.find("media:thumbnail")
            if thumbnail is not None:
                url = thumbnail.get("url")
                if url:
                    return url
            
            description = item.find("description")
            if description is not None and description.text:
                img_match = re.search(
                    r'<img[^>]+src=["\']([^"\']+)["\']',
                    description.text
                )
                if img_match:
                    return img_match.group(1)
            
            return None
            
        except Exception as e:
            _LOGGER.debug("Ошибка извлечения картинки: %s", e)
            return None

    @property
    def last_error(self) -> Optional[str]:
        """Возвращает последнюю ошибку."""
        return self._last_error


class RSSNewsSensor(CoordinatorEntity[RSSDataUpdateCoordinator], SensorEntity):
    """Сенсор с новостями (только сводка ЧС)."""

    def __init__(
        self,
        coordinator: RSSDataUpdateCoordinator,
        base_name: str,
    ) -> None:
        """Инициализация сенсора."""
        super().__init__(coordinator)
        
        self._base_name = base_name
        
        self._attr_name = "Новости МЧС"
        self._attr_unique_id = f"{DOMAIN}_1"
        self._attr_icon = "mdi:alert-circle"
        self._attr_native_unit_of_measurement = "нов."

    @property
    def native_value(self) -> int:
        """Количество новостей."""
        if not self.coordinator.data:
            return 0
        articles = self.coordinator.data.get(ATTR_ARTICLES, [])
        return len(articles)

    @property
    def extra_state_attributes(self) -> Dict[str, Any]:
        """Атрибуты с новостями."""
        if not self.coordinator.data:
            return {
                ATTR_ARTICLES: [],
                "source_name": self._attr_name,
                "count": 0,
                "last_update": None,
                "error": self.coordinator.last_error,
            }
        
        articles = self.coordinator.data.get(ATTR_ARTICLES, [])
        
        return {
            ATTR_ARTICLES: articles,
            "source_name": "Сводка ЧС и происшествий",
            "count": len(articles),
            "last_update": self.coordinator.last_update_success,
            "error": self.coordinator.last_error,
            "filter": "только сводка ЧС и происшествий",
        }

    @property
    def available(self) -> bool:
        """Доступность сенсора."""
        return self.coordinator.last_update_success

    @property
    def device_info(self):
        """Информация об устройстве."""
        return {
            "identifiers": {(DOMAIN, self._attr_unique_id)},
            "name": self._attr_name,
            "manufacturer": "МЧС России",
            "model": "RSS Сводка ЧС",
            "sw_version": "1.1.1",
        }

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
    CONF_SOURCES_COUNT,
    CONF_SCAN_INTERVAL,  # ← ДОБАВЛЕН ИМПОРТ
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
    sources_count = config_entry.data.get(CONF_SOURCES_COUNT, 1)
    base_name = config_entry.data.get(CONF_NAME, "Новости МЧС")
    scan_interval = config_entry.options.get(CONF_SCAN_INTERVAL, DEFAULT_SCAN_INTERVAL)

    _LOGGER.debug("   URL: %s", rss_url)
    _LOGGER.debug("   Количество сенсоров: %d", sources_count)
    _LOGGER.debug("   Интервал обновления: %d сек", scan_interval)

    # Создаём координатор
    coordinator = RSSDataUpdateCoordinator(
        hass,
        rss_url=rss_url,
        update_interval=timedelta(seconds=scan_interval),
    )

    # Выполняем первый запрос
    await coordinator.async_refresh()

    # Создаём сенсоры
    entities: List[SensorEntity] = []
    for i in range(sources_count):
        entities.append(
            RSSNewsSensor(
                coordinator,
                base_name,
                i + 1,
                sources_count,
            )
        )

    _LOGGER.info("✅ Создано %d сенсоров Новости МЧС", len(entities))
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
            
            _LOGGER.debug("✅ Загружено %d новостей", len(articles))
            self._last_error = None
            return {"articles": articles}

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

    def _parse_rss(self, xml_text: str) -> List[Dict[str, str]]:
        """Парсинг RSS ленты."""
        articles: List[Dict[str, str]] = []
        
        try:
            root = ET.fromstring(xml_text)
            
            # Находим все элементы <item>
            items = root.findall(".//item")
            _LOGGER.debug("   Найдено элементов <item>: %d", len(items))
            
            for idx, item in enumerate(items[:10]):
                try:
                    # Извлекаем данные с проверкой на None
                    title_elem = item.find("title")
                    link_elem = item.find("link")
                    description_elem = item.find("description")
                    pub_date_elem = item.find("pubDate")
                    
                    title = title_elem.text if title_elem is not None and title_elem.text else "Без названия"
                    link = link_elem.text if link_elem is not None and link_elem.text else ""
                    description = description_elem.text if description_elem is not None else ""
                    pub_date = pub_date_elem.text if pub_date_elem is not None and pub_date_elem.text else ""
                    
                    # Очищаем описание
                    description_clean = self._clean_description(description)
                    
                    # Ищем картинку
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
        
        # Удаляем HTML-теги
        clean = re.sub(r"<[^>]+>", "", description)
        # Удаляем лишние пробелы
        clean = re.sub(r"\s+", " ", clean).strip()
        # Обрезаем до 250 символов
        if len(clean) > 250:
            clean = clean[:250] + "..."
        return clean

    def _extract_image(self, item: ET.Element) -> Optional[str]:
        """Извлечение изображения из элемента."""
        try:
            # 1. Проверяем <enclosure>
            enclosure = item.find("enclosure")
            if enclosure is not None:
                url = enclosure.get("url")
                if url:
                    return url
            
            # 2. Проверяем <media:content>
            media = item.find("media:content")
            if media is not None:
                url = media.get("url")
                if url:
                    return url
            
            # 3. Проверяем <media:thumbnail>
            thumbnail = item.find("media:thumbnail")
            if thumbnail is not None:
                url = thumbnail.get("url")
                if url:
                    return url
            
            # 4. Ищем в <description>
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
    """Сенсор с новостями."""

    def __init__(
        self,
        coordinator: RSSDataUpdateCoordinator,
        base_name: str,
        source_number: int,
        total_sources: int,
    ) -> None:
        """Инициализация сенсора."""
        super().__init__(coordinator)
        
        self._source_number = source_number
        self._total_sources = total_sources
        self._base_name = base_name
        
        # Формируем имя
        if total_sources > 1:
            self._attr_name = f"{base_name} {source_number}"
        else:
            self._attr_name = base_name
        
        self._attr_unique_id = f"{DOMAIN}_{source_number}"
        self._attr_icon = "mdi:rss"
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
            ATTR_ARTICLES: articles[:10],
            "source_name": self._attr_name,
            "count": len(articles),
            "last_update": self.coordinator.last_update_success_time.isoformat()
            if self.coordinator.last_update_success_time else None,
            "error": self.coordinator.last_error,
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
            "model": "RSS Новости",
            "sw_version": "1.0.2",
        }

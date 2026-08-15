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

    # Создаём ОДИН сенсор
    entities = [
        RSSNewsSensor(
            coordinator,
            base_name,
        )
    ]

    _LOGGER.info("✅ Создан 1 сенсор Новости МЧС")
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
        self.session: Optional[aiohttp.ClientSession] = None

    async def _get_session(self) -> aiohttp.ClientSession:
        """Получает сессию aiohttp."""
        if self.session is None or self.session.closed:
            self.session = aiohttp.ClientSession()
        return self.session

    async def _fetch_full_article(self, url: str) -> str:
        """Загружает полный текст статьи по ссылке."""
        try:
            session = await self._get_session()
            headers = {
                "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
            }
            
            async with async_timeout.timeout(15):
                async with session.get(url, headers=headers) as response:
                    if response.status != 200:
                        return ""
                    
                    html = await response.text()
                    
                    # Пытаемся извлечь текст из различных селекторов
                    # Используем простой поиск по ключевым словам и блокам
                    
                    # Ищем блок с текстом новости на сайте МЧС
                    patterns = [
                        r'<div[^>]*class="[^"]*text[^"]*"[^>]*>(.*?)</div>',
                        r'<div[^>]*class="[^"]*content[^"]*"[^>]*>(.*?)</div>',
                        r'<div[^>]*class="[^"]*news[^"]*"[^>]*>(.*?)</div>',
                        r'<div[^>]*class="[^"]*article[^"]*"[^>]*>(.*?)</div>',
                        r'<div[^>]*class="[^"]*body[^"]*"[^>]*>(.*?)</div>',
                        r'<p>(.*?)</p>',  # Если ничего не нашли - берём все абзацы
                    ]
                    
                    full_text = ""
                    for pattern in patterns:
                        matches = re.findall(pattern, html, re.DOTALL | re.IGNORECASE)
                        if matches:
                            # Берём первый найденный блок
                            text = matches[0]
                            # Очищаем от HTML
                            text = re.sub(r'<[^>]+>', ' ', text)
                            text = re.sub(r'\s+', ' ', text).strip()
                            # Если текст достаточно длинный - используем его
                            if len(text) > 100:
                                full_text = text
                                break
                    
                    # Если текст не найден, пробуем найти все параграфы
                    if not full_text or len(full_text) < 50:
                        # Ищем все теги <p> с текстом
                        paragraphs = re.findall(r'<p>(.*?)</p>', html, re.DOTALL | re.IGNORECASE)
                        if paragraphs:
                            # Собираем все абзацы в один текст
                            full_text = ' '.join([
                                re.sub(r'<[^>]+>', ' ', p).strip()
                                for p in paragraphs
                                if len(p.strip()) > 20
                            ])
                            if full_text:
                                full_text = re.sub(r'\s+', ' ', full_text).strip()
                    
                    return full_text if full_text and len(full_text) > 20 else ""
                    
        except Exception as e:
            _LOGGER.debug("Ошибка загрузки статьи %s: %s", url, e)
            return ""

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

            # Парсим XML
            articles = await self.hass.async_add_executor_job(
                self._parse_rss, xml_text
            )
            
            # Загружаем полный текст для каждой статьи
            _LOGGER.debug("   Загрузка полного текста для %d статей", len(articles))
            
            full_articles = []
            for i, article in enumerate(articles[:5]):  # Ограничиваем 5 статьями для скорости
                if article.get("link") and article["link"] != "#":
                    try:
                        # Проверяем, есть ли уже достаточно текста
                        desc = article.get("description", "")
                        if len(desc) > 200:
                            # Если описание уже длинное - используем его
                            article["full_text"] = desc
                            full_articles.append(article)
                            continue
                        
                        full_text = await self._fetch_full_article(article["link"])
                        if full_text:
                            article["full_text"] = full_text
                            _LOGGER.debug("   ✅ Загружен текст для: %s", article["title"][:50])
                        else:
                            # Если не удалось загрузить, используем описание из RSS
                            article["full_text"] = desc or "Описание отсутствует"
                            _LOGGER.debug("   ⚠️ Используем описание из RSS: %s", article["title"][:50])
                    except Exception as e:
                        _LOGGER.debug("   ❌ Ошибка загрузки: %s", e)
                        article["full_text"] = article.get("description", "Описание отсутствует")
                else:
                    article["full_text"] = article.get("description", "Описание отсутствует")
                
                full_articles.append(article)
            
            _LOGGER.debug("✅ Загружено %d новостей", len(full_articles))
            self._last_error = None
            return {"articles": full_articles}

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
            items = root.findall(".//item")
            _LOGGER.debug("   Найдено элементов <item>: %d", len(items))
            
            for idx, item in enumerate(items[:10]):
                try:
                    title_elem = item.find("title")
                    link_elem = item.find("link")
                    description_elem = item.find("description")
                    pub_date_elem = item.find("pubDate")
                    
                    title = title_elem.text if title_elem is not None and title_elem.text else "Без названия"
                    link = link_elem.text if link_elem is not None and link_elem.text else "#"
                    description = description_elem.text if description_elem is not None else ""
                    pub_date = pub_date_elem.text if pub_date_elem is not None and pub_date_elem.text else ""
                    
                    # Очищаем описание
                    description_clean = self._clean_description(description)
                    image = self._extract_image(item)
                    
                    article = {
                        "title": title,
                        "link": link,
                        "description": description_clean,
                        "pubDate": pub_date,
                        "image": image,
                        "full_text": description_clean,  # По умолчанию - описание
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
        
        # Добавляем полный текст в каждую статью
        full_articles = []
        for article in articles:
            full_article = dict(article)
            # Если есть full_text - используем его, иначе description
            if "full_text" in full_article and full_article["full_text"]:
                full_article["text"] = full_article["full_text"]
            else:
                full_article["text"] = full_article.get("description", "Описание отсутствует")
            full_articles.append(full_article)
        
        return {
            ATTR_ARTICLES: full_articles,
            "source_name": self._attr_name,
            "count": len(full_articles),
            "last_update": self.coordinator.last_update_success,
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
            "sw_version": "1.0.0",
        }

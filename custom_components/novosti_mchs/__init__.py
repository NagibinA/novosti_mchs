"""Интеграция Новости МЧС для Home Assistant."""
import os
import shutil
import logging
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.const import Platform
from homeassistant.components.lovelace.resources import ResourceStorageCollection

from .const import DOMAIN

PLATFORMS = [Platform.SENSOR]
_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Настройка интеграции из конфигурации."""
    # Сохраняем данные конфигурации
    hass.data.setdefault(DOMAIN, {})
    hass.data[DOMAIN][entry.entry_id] = entry.data

    # 1. Настраиваем сенсоры
    try:
        await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
        _LOGGER.info("✅ Сенсоры Новости МЧС настроены")
    except Exception as e:
        _LOGGER.error("❌ Ошибка настройки сенсоров: %s", e)
        return False

    # 2. Копируем карточку в www/community/
    try:
        await hass.async_add_executor_job(_copy_lovelace_files, hass)
    except Exception as e:
        _LOGGER.error("❌ Ошибка копирования карточки: %s", e)

    # 3. Регистрируем карточку как ресурс Lovelace
    await _register_lovelace_resource(hass)

    return True


def _copy_lovelace_files(hass):
    """Копирует файлы карточки в www/community/."""
    source_file = hass.config.path("custom_components/novosti_mchs/news-mchs-card.js")
    target_dir = hass.config.path("www/community/novosti_mchs/")
    target_file = hass.config.path("www/community/novosti_mchs/news-mchs-card.js")

    if not os.path.exists(source_file):
        _LOGGER.error("❌ Файл карточки не найден: %s", source_file)
        return

    os.makedirs(target_dir, exist_ok=True)
    shutil.copy2(source_file, target_file)
    _LOGGER.info("✅ Карточка скопирована: %s", target_file)


async def _register_lovelace_resource(hass: HomeAssistant) -> None:
    """Регистрирует карточку в ресурсах Lovelace."""
    card_url = "/local/community/novosti_mchs/news-mchs-card.js"
    
    try:
        # Получаем объект Lovelace
        lovelace_data = hass.data.get("lovelace")
        if lovelace_data is None:
            _LOGGER.warning("⚠️ Lovelace не загружен")
            _LOGGER.warning(
                "   Добавьте ресурс вручную:\n"
                "   1. Настройки → Панели → Ресурсы → Добавить ресурс\n"
                "   URL: %s\n"
                "   Тип: JavaScript Module",
                card_url
            )
            return
        
        # Получаем ресурсы через атрибут
        resources = getattr(lovelace_data, "resources", None)
        if resources is None:
            _LOGGER.warning("⚠️ Ресурсы Lovelace не найдены")
            _LOGGER.warning(
                "   Добавьте ресурс вручную:\n"
                "   1. Настройки → Панели → Ресурсы → Добавить ресурс\n"
                "   URL: %s\n"
                "   Тип: JavaScript Module",
                card_url
            )
            return
        
        # Проверяем тип ресурсов
        if not isinstance(resources, ResourceStorageCollection):
            _LOGGER.warning("⚠️ Неверный тип ресурсов: %s", type(resources))
            _LOGGER.warning(
                "   Добавьте ресурс вручную:\n"
                "   1. Настройки → Панели → Ресурсы → Добавить ресурс\n"
                "   URL: %s\n"
                "   Тип: JavaScript Module",
                card_url
            )
            return
        
        # Проверяем, не зарегистрирован ли уже ресурс
        for item in resources.async_items():
            if item.get("url") == card_url:
                _LOGGER.info("✅ Карточка уже зарегистрирована в Lovelace")
                return
        
        # Регистрируем новый ресурс
        await resources.async_create_item({
            "res_type": "module",
            "url": card_url,
        })
        _LOGGER.info("✅ Карточка Новости МЧС зарегистрирована в Lovelace")
                
    except Exception as e:
        _LOGGER.error("❌ Ошибка регистрации карточки: %s", e)
        _LOGGER.warning(
            "   Добавьте ресурс вручную:\n"
            "   1. Настройки → Панели → Ресурсы → Добавить ресурс\n"
            "   URL: %s\n"
            "   Тип: JavaScript Module",
            card_url
        )


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Выгрузка интеграции."""
    unload_ok = await hass.config_entries.async_forward_entry_unload(entry, "sensor")
    
    if unload_ok:
        hass.data[DOMAIN].pop(entry.entry_id, None)
        _LOGGER.info("✅ Интеграция Новости МЧС выгружена")
    else:
        _LOGGER.warning("⚠️ Проблема при выгрузке интеграции")
    
    return unload_ok


async def async_reload_entry(hass: HomeAssistant, entry: ConfigEntry) -> None:
    """Перезагрузка интеграции."""
    _LOGGER.debug("🔄 Перезагрузка интеграции Новости МЧС")
    await async_unload_entry(hass, entry)
    await async_setup_entry(hass, entry)

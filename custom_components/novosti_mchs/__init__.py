"""Интеграция Новости МЧС для Home Assistant."""
import os
import shutil
import logging
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.const import Platform

from .const import DOMAIN

PLATFORMS = [Platform.SENSOR]
_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Настройка интеграции из конфигурации."""
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

    # 3. Регистрируем карточку через ресурсы Lovelace
    await _register_lovelace_resource(hass)

    return True


def _copy_lovelace_files(hass):
    """Копирует файлы карточки в www/community/."""
    # Карточка лежит ВНУТРИ папки интеграции (скопирована HACS)
    source_file = hass.config.path("custom_components/novosti_mchs/news-mchs-card.js")
    target_dir = hass.config.path("www/community/novosti_mchs/lovelace/")
    target_file = hass.config.path("www/community/novosti_mchs/lovelace/news-mchs-card.js")

    _LOGGER.debug("📁 Копирование карточки:")
    _LOGGER.debug("   Источник: %s", source_file)
    _LOGGER.debug("   Назначение: %s", target_file)

    if not os.path.exists(source_file):
        _LOGGER.error("❌ Файл карточки не найден: %s", source_file)
        _LOGGER.error("   news-mchs-card.js должен лежать в custom_components/novosti_mchs/")
        return

    # Создаём папку
    os.makedirs(target_dir, exist_ok=True)
    
    # Копируем
    shutil.copy2(source_file, target_file)
    _LOGGER.info("✅ Карточка скопирована: %s", target_file)


async def _register_lovelace_resource(hass: HomeAssistant) -> None:
    """Регистрирует карточку в ресурсах Lovelace."""
    card_url = "/local/community/novosti_mchs/lovelace/news-mchs-card.js"
    
    try:
        # Получаем объект ресурсов Lovelace
        resources = hass.data.get("lovelace", {}).get("resources")
        
        if resources is None:
            _LOGGER.warning("⚠️ Объект ресурсов Lovelace не найден")
            _LOGGER.warning(
                "   Добавьте ресурс вручную:\n"
                "   1. Настройки → Панели → Ресурсы → Добавить ресурс\n"
                "   URL: %s\n"
                "   Тип: JavaScript Module",
                card_url
            )
            return
        
        # Проверяем, не зарегистрирован ли уже ресурс
        existing_items = resources.async_items() if hasattr(resources, "async_items") else []
        for resource in existing_items:
            if resource.get("url") == card_url:
                _LOGGER.info("✅ Карточка уже зарегистрирована в Lovelace")
                return
        
        # Регистрируем новый ресурс
        if hasattr(resources, "async_create_item"):
            await resources.async_create_item(
                {
                    "res_type": "module",
                    "url": card_url,
                }
            )
            _LOGGER.info("✅ Карточка Новости МЧС зарегистрирована в Lovelace")
        else:
            _LOGGER.warning("⚠️ Не удалось зарегистрировать карточку")
            _LOGGER.warning(
                "   Добавьте ресурс вручную:\n"
                "   1. Настройки → Панели → Ресурсы → Добавить ресурс\n"
                "   URL: %s\n"
                "   Тип: JavaScript Module",
                card_url
            )
                
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
    _LOGGER.debug("🔄 Выгрузка интеграции Новости МЧС")
    
    unload_ok = await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    
    if unload_ok:
        hass.data[DOMAIN].pop(entry.entry_id)
        _LOGGER.info("✅ Интеграция Новости МЧС выгружена")
    else:
        _LOGGER.warning("⚠️ Проблема при выгрузке интеграции")
    
    return unload_ok


async def async_reload_entry(hass: HomeAssistant, entry: ConfigEntry) -> None:
    """Перезагрузка интеграции."""
    _LOGGER.debug("🔄 Перезагрузка интеграции Новости МЧС")
    await async_unload_entry(hass, entry)
    await async_setup_entry(hass, entry)

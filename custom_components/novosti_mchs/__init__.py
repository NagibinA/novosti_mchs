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
    card_url = "/local/community/novosti_mchs/lovelace/news-mchs-card.js"
    try:
        await hass.services.async_call(
            "lovelace",
            "resources",
            {"url": card_url, "type": "module"},
            blocking=True,
        )
        _LOGGER.info("✅ Карточка Новости МЧС зарегистрирована в Lovelace")
    except Exception as e:
        _LOGGER.warning(
            "⚠️ Не удалось автоматически зарегистрировать карточку: %s\n"
            "   Добавьте ресурс вручную: Settings → Dashboards → Resources → Add Resource\n"
            "   URL: %s\n"
            "   Type: JavaScript Module",
            e, card_url
        )

    return True


def _copy_lovelace_files(hass):
    """Копирует файлы карточки в www/community/."""
    # Карточка лежит в корне custom_components/novosti_mchs/
    source_file = hass.config.path("custom_components/novosti_mchs/news-mchs-card.js")
    target_dir = hass.config.path("www/community/novosti_mchs/lovelace/")
    target_file = hass.config.path("www/community/novosti_mchs/lovelace/news-mchs-card.js")

    _LOGGER.debug("📁 Копирование карточки:")
    _LOGGER.debug("   Источник: %s", source_file)
    _LOGGER.debug("   Назначение: %s", target_file)

    # Проверяем, существует ли файл
    if not os.path.exists(source_file):
        _LOGGER.error("❌ Файл карточки не найден: %s", source_file)
        _LOGGER.error("   Поместите news-mchs-card.js в корень custom_components/novosti_mchs/")
        return

    # Создаём целевую папку
    try:
        os.makedirs(target_dir, exist_ok=True)
        _LOGGER.debug("   Папка создана: %s", target_dir)
    except Exception as e:
        _LOGGER.error("❌ Не удалось создать папку %s: %s", target_dir, e)
        return

    # Копируем файл
    try:
        shutil.copy2(source_file, target_file)
        _LOGGER.info("✅ Карточка скопирована: %s", target_file)
    except Exception as e:
        _LOGGER.error("❌ Ошибка копирования: %s", e)


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

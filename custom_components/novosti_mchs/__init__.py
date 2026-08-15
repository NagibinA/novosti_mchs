"""Интеграция Новости МЧС."""
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
    """Настройка интеграции."""
    hass.data.setdefault(DOMAIN, {})
    hass.data[DOMAIN][entry.entry_id] = entry.data

    # Настраиваем сенсоры
    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)

    # 🔥 Копируем карточку (исправленный путь)
    await hass.async_add_executor_job(_copy_lovelace_files, hass)

    # Регистрируем карточку
    card_url = "/local/community/novosti_mchs/lovelace/news-mchs-card.js"
    try:
        await hass.services.async_call(
            "lovelace",
            "resources",
            {"url": card_url, "type": "module"},
            blocking=True,
        )
        _LOGGER.info("✅ Карточка Новости МЧС зарегистрирована")
    except Exception as e:
        _LOGGER.warning(
            "⚠️ Не удалось зарегистрировать карточку: %s\n"
            "   Добавьте ресурс вручную: Настройки → Панели → Ресурсы → Добавить ресурс\n"
            "   URL: %s\n"
            "   Тип: JavaScript Module",
            e, card_url
        )

    return True


def _copy_lovelace_files(hass):
    """Копирует файлы карточки в www/community."""
    # 🔥 Ищем карточку в корне интеграции (не в lovelace/ внутри custom_components)
    # HACS копирует файлы из корня репозитория в custom_components/novosti_mchs/
    # но папка lovelace/ остаётся в корне репозитория, а не копируется
    
    # Пробуем найти карточку в нескольких местах
    possible_paths = [
        hass.config.path("custom_components/novosti_mchs/news-mchs-card.js"),  # если файл в корне
        hass.config.path("custom_components/novosti_mchs/lovelace/news-mchs-card.js"),  # если папка скопировалась
        hass.config.path("lovelace/news-mchs-card.js"),  # если в корне конфига
    ]
    
    source_file = None
    for path in possible_paths:
        if os.path.exists(path):
            source_file = path
            _LOGGER.debug("   Карточка найдена: %s", path)
            break
    
    if source_file is None:
        _LOGGER.error("❌ Файл карточки не найден ни в одном из путей")
        _LOGGER.error("   Проверенные пути: %s", possible_paths)
        return

    target_dir = hass.config.path("www/community/novosti_mchs/lovelace/")
    target_file = hass.config.path("www/community/novosti_mchs/lovelace/news-mchs-card.js")

    _LOGGER.debug("📁 Копирование карточки:")
    _LOGGER.debug("   Источник: %s", source_file)
    _LOGGER.debug("   Назначение: %s", target_file)

    # Создаём целевую папку
    try:
        os.makedirs(target_dir, exist_ok=True)
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

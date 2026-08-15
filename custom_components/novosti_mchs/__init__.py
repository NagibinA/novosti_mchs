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

    # Копируем карточку
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
        _LOGGER.info("Карточка Новости МЧС успешно зарегистрирована")
    except Exception as e:
        _LOGGER.warning("Не удалось зарегистрировать карточку: %s", e)

    return True


def _copy_lovelace_files(hass):
    """Копирует файлы карточки в www/community."""
    source_dir = hass.config.path("custom_components/novosti_mchs/lovelace")
    target_dir = hass.config.path("www/community/novosti_mchs/lovelace")

    if not os.path.exists(source_dir):
        _LOGGER.warning("Папка с карточкой не найдена: %s", source_dir)
        return

    # Создаём целевую папку
    os.makedirs(target_dir, exist_ok=True)

    # Копируем все файлы
    for filename in os.listdir(source_dir):
        source_file = os.path.join(source_dir, filename)
        target_file = os.path.join(target_dir, filename)
        if os.path.isfile(source_file):
            shutil.copy2(source_file, target_file)
            _LOGGER.debug("Скопирован файл: %s", filename)

    _LOGGER.info("Карточка скопирована в /local/community/novosti_mchs/lovelace/")


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Выгрузка интеграции."""
    unload_ok = await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    if unload_ok:
        hass.data[DOMAIN].pop(entry.entry_id)
    return unload_ok

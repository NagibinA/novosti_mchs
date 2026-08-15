"""Настройка интеграции Новости МЧС."""
import voluptuous as vol
from homeassistant import config_entries
from homeassistant.core import callback
from homeassistant.const import CONF_NAME

from .const import DOMAIN, DEFAULT_NAME, CONF_RSS_URL, CONF_SCAN_INTERVAL, DEFAULT_SCAN_INTERVAL


class NovostiMCHSConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """Конфигурационный поток для интеграции Новости МЧС."""

    VERSION = 1

    async def async_step_user(self, user_input=None):
        """Первый шаг настройки."""
        errors = {}
        
        if user_input is not None:
            # Проверяем URL
            if not user_input[CONF_RSS_URL].startswith(("http://", "https://")):
                errors["base"] = "invalid_url"
            else:
                # Проверяем, не настроена ли уже такая лента
                await self.async_set_unique_id(user_input[CONF_RSS_URL])
                self._abort_if_unique_id_configured()
                
                return self.async_create_entry(
                    title=user_input.get(CONF_NAME, DEFAULT_NAME),
                    data=user_input
                )

        data_schema = vol.Schema({
            vol.Required(CONF_NAME, default=DEFAULT_NAME): str,
            vol.Required(CONF_RSS_URL, default="https://78.mchs.gov.ru/deyatelnost/press-centr/operativnaya-informaciya/rss"): str,
            vol.Optional(CONF_SCAN_INTERVAL, default=DEFAULT_SCAN_INTERVAL): vol.All(
                vol.Coerce(int), vol.Range(min=60, max=3600)
            ),
        })

        return self.async_show_form(
            step_id="user",
            data_schema=data_schema,
            errors=errors,
            description_placeholders={
                "example_url": "https://78.mchs.gov.ru/deyatelnost/press-centr/operativnaya-informaciya/rss"
            }
        )

    @staticmethod
    @callback
    def async_get_options_flow(config_entry):
        """Возвращает поток опций."""
        return NovostiMCHSOptionsFlow(config_entry)


class NovostiMCHSOptionsFlow(config_entries.OptionsFlow):
    """Поток опций для интеграции Новости МЧС."""

    def __init__(self, config_entry):
        self.config_entry = config_entry

    async def async_step_init(self, user_input=None):
        """Шаг настройки опций."""
        errors = {}
        
        if user_input is not None:
            # Проверяем URL
            if not user_input[CONF_RSS_URL].startswith(("http://", "https://")):
                errors["base"] = "invalid_url"
            else:
                # Обновляем данные
                new_data = {**self.config_entry.data}
                new_data[CONF_RSS_URL] = user_input[CONF_RSS_URL]
                new_data[CONF_SCAN_INTERVAL] = user_input[CONF_SCAN_INTERVAL]
                
                self.hass.config_entries.async_update_entry(
                    self.config_entry,
                    data=new_data
                )
                
                # Перезагружаем интеграцию
                await self.hass.config_entries.async_reload(self.config_entry.entry_id)
                
                return self.async_create_entry(title="", data={})

        # Получаем текущие значения
        current_rss = self.config_entry.data.get(CONF_RSS_URL, "")
        current_interval = self.config_entry.data.get(CONF_SCAN_INTERVAL, DEFAULT_SCAN_INTERVAL)

        return self.async_show_form(
            step_id="init",
            data_schema=vol.Schema({
                vol.Required(CONF_RSS_URL, default=current_rss): str,
                vol.Optional(CONF_SCAN_INTERVAL, default=current_interval): vol.All(
                    vol.Coerce(int), vol.Range(min=60, max=3600)
                ),
            }),
            errors=errors,
            description_placeholders={
                "example_url": "https://78.mchs.gov.ru/deyatelnost/press-centr/operativnaya-informaciya/rss"
            }
        )

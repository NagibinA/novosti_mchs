import voluptuous as vol
from homeassistant import config_entries
from homeassistant.core import callback
from homeassistant.const import CONF_NAME
from .const import DOMAIN, DEFAULT_NAME, CONF_RSS_URL, CONF_SOURCES_COUNT

class NovostiMCHSConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    VERSION = 1

    async def async_step_user(self, user_input=None):
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
            vol.Optional(CONF_SOURCES_COUNT, default=1): vol.All(
                vol.Coerce(int), vol.Range(min=1, max=5, msg="Можно от 1 до 5 сенсоров")
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
        return NovostiMCHSOptionsFlow(config_entry)


class NovostiMCHSOptionsFlow(config_entries.OptionsFlow):
    def __init__(self, config_entry):
        self.config_entry = config_entry

    async def async_step_init(self, user_input=None):
        if user_input is not None:
            return self.async_create_entry(title="", data=user_input)

        return self.async_show_form(
            step_id="init",
            data_schema=vol.Schema({
                vol.Required(CONF_RSS_URL, default=self.config_entry.data.get(CONF_RSS_URL)): str,
                vol.Optional(CONF_SOURCES_COUNT, default=self.config_entry.data.get(CONF_SOURCES_COUNT, 1)): vol.All(
                    vol.Coerce(int), vol.Range(min=1, max=5)
                ),
            })
        )

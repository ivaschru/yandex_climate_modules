DOMAIN = "yandex_climate_modules"
PLATFORMS = ["sensor"]

CONF_TOKEN = "token"
CONF_DEVICE_IDS = "device_ids"

DEFAULT_UPDATE_INTERVAL = 120  # seconds

YANDEX_IOT_BASE = "https://api.iot.yandex.net/v1.0"

# Property instances we care about
INST_TEMPERATURE = "temperature"
INST_HUMIDITY = "humidity"
INST_CO2 = "co2_level"

CLIMATE_INSTANCES = {INST_TEMPERATURE, INST_HUMIDITY, INST_CO2}


# Options
CONF_UPDATE_INTERVAL = "update_interval"
CONF_ENABLE_LAST_UPDATED = "enable_last_updated"
DEFAULT_ENABLE_LAST_UPDATED = True

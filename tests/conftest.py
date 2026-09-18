import os

# Never read deployment credentials from the developer's .env during tests.
for name, value in {
    "POSTGRES_USER": "test",
    "POSTGRES_PASSWORD": "test",
    "POSTGRES_HOST": "127.0.0.1",
    "POSTGRES_PORT": "55439",
    "POSTGRES_DB": "calendar_test",
    "DOONOOK_NODE_ROLE": "primary",
    "REMOTE_WRITER_HOST": "",
    "JISU_API_KEY": "test",
    "QWEN_BASE_URL": "http://qwen.invalid/v1",
    "QWEN_LAN_API_KEY": "test-key",
    "QWEN_MODEL": "qwen3.8-lan",
    "ASTRO_EPHEMERIS_PATH": "/nonexistent/test-ephemeris.bsp",
    "QWEN_TIMEOUT_SECONDS": "2",
    "ASTRO_GENERATE_ON_REQUEST": "false",
    "TIMEZONE": "Asia/Shanghai",
}.items():
    os.environ[name] = value

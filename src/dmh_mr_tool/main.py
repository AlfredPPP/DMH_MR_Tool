# src/dmh_mr_tool/main.py
from core.logging import setup_logging
from config.config_loader import get_config, ConfigLoader

def main():
    # Load configuration
    config = get_config()

    log_level = config.get('logging', 'level')
    setup_logging(
        level="INFO",
        log_file="logs/app.log"
    )


if __name__ == "__main__":
    main()

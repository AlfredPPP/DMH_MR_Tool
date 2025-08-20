# src/dmh_mr_tool/main.py
from core.logging import setup_logging
from config.settings import config_manager, get_config

from parsers.base import Foo


def main():
    config_manager.load()

    config = get_config()
    setup_logging(
        level=config.logging.level,
        log_file=config.paths.log_path
    )
    f = Foo()
    print(f.add('0', 4))


if __name__ == "__main__":
    main()

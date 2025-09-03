# src/dmh_mr_tool/main.py
from core.logging import setup_logging
from config.settings import CONFIG

from parsers.base import Foo


def main():
    setup_logging(
        level=CONFIG.logging.level,
        log_file=CONFIG.paths.log_path
    )
    f = Foo()
    print(f.add('0', 4))


if __name__ == "__main__":
    main()

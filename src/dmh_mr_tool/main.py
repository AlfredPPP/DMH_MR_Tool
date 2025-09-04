# src/dmh_mr_tool/main.py

# from core.logging import setup_logging
# from config.settings import CONFIG
from ui.main_window import run


def main():
    # setup_logging(
    #     level=CONFIG.logging.level,
    #     log_file=CONFIG.paths.log_path
    # )
    run()

if __name__ == "__main__":
    main()
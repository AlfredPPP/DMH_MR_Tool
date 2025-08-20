from config.settings import config_manager, get_config

def main():
    config_manager.load()

    config = get_config()
    log_level = config.logging.level
    # setup_logging(
    #     level="INFO",
    #     log_file="logs/app.log"
    # )
    print(log_level)

if __name__ == "__main__":
    main()

# src/dmh_mr_tool/config/settings.py
"""Configuration management with validation and environment support"""

import os
from pathlib import Path
from typing import Any, Dict, Optional
from configparser import ConfigParser
from dataclasses import dataclass, field
from enum import Enum

from pydantic import BaseModel, Field, validator
import structlog

logger = structlog.get_logger()


class Environment(str, Enum):
    """Application environments"""
    DEVELOPMENT = "development"
    TESTING = "testing"
    STAGING = "staging"
    PRODUCTION = "production"


class DatabaseConfig(BaseModel):
    """Database configuration"""
    path: Path
    backup_path: Path
    pool_size: int = Field(default=5, ge=1, le=20)
    echo: bool = False

    @validator('path', 'backup_path')
    def validate_path(cls, v):
        if not v.parent.exists():
            raise ValueError(f"Directory {v.parent} does not exist")
        return v


class ScraperConfig(BaseModel):
    """Web scraper configuration"""
    asx_base_url: str = "https://www.asx.com.au"
    asx_announcement_url: str = "/markets/trade-our-cash-market/todays-announcements"
    betashares_base_url: str = "https://www.betashares.com.au"
    vanguard_api_url: str = "https://api.vanguard.com/rs/gre/gra/1.7.0/datasets/auw-retail/funds"

    max_retries: int = Field(default=3, ge=1, le=10)
    timeout: int = Field(default=30, ge=5, le=120)
    rate_limit_delay: float = Field(default=1.0, ge=0.1, le=10.0)
    concurrent_downloads: int = Field(default=3, ge=1, le=10)


class PathConfig(BaseModel):
    """File path configuration"""
    download_path: Path
    backup_path: Path
    log_path: Path
    temp_path: Path
    shared_config_path: Path  # Network drive config location

    @validator('download_path', 'backup_path', 'log_path', 'temp_path')
    def ensure_directory_exists(cls, v):
        v.mkdir(parents=True, exist_ok=True)
        return v


class LogConfig(BaseModel):
    """Logging configuration"""
    level: str = Field(default="INFO", regex="^(DEBUG|INFO|WARNING|ERROR|CRITICAL)$")
    format: str = "json"
    max_file_size: int = Field(default=5_242_880, ge=1_048_576)  # 5MB default, min 1MB
    backup_count: int = Field(default=5, ge=1, le=20)
    enable_console: bool = True
    enable_file: bool = True


@dataclass
class AppConfig:
    """Main application configuration"""
    environment: Environment = Environment.DEVELOPMENT
    database: DatabaseConfig = field(default_factory=DatabaseConfig)
    scraper: ScraperConfig = field(default_factory=ScraperConfig)
    paths: PathConfig = field(default_factory=PathConfig)
    logging: LogConfig = field(default_factory=LogConfig)

    # Runtime settings
    debug: bool = False
    dry_run: bool = False
    user: Optional[str] = None

    @classmethod
    def from_ini(cls, config_path: Path) -> "AppConfig":
        """Load configuration from INI file"""
        if not config_path.exists():
            raise FileNotFoundError(f"Configuration file not found: {config_path}")

        parser = ConfigParser()
        parser.read(config_path)

        config_dict = {}
        for section in parser.sections():
            config_dict[section] = dict(parser.items(section))

        return cls.from_dict(config_dict)

    @classmethod
    def from_dict(cls, config_dict: Dict[str, Any]) -> "AppConfig":
        """Create configuration from dictionary"""
        # Convert string paths to Path objects
        if 'paths' in config_dict:
            for key in ['download_path', 'backup_path', 'log_path', 'temp_path', 'shared_config_path']:
                if key in config_dict['paths']:
                    config_dict['paths'][key] = Path(config_dict['paths'][key])

        if 'database' in config_dict:
            if 'path' in config_dict['database']:
                config_dict['database']['path'] = Path(config_dict['database']['path'])
            if 'backup_path' in config_dict['database']:
                config_dict['database']['backup_path'] = Path(config_dict['database']['backup_path'])

        # Create nested configs
        database = DatabaseConfig(**config_dict.get('database', {}))
        scraper = ScraperConfig(**config_dict.get('scraper', {}))
        paths = PathConfig(**config_dict.get('paths', {}))
        logging = LogConfig(**config_dict.get('logging', {}))

        return cls(
            environment=Environment(config_dict.get('environment', 'development')),
            database=database,
            scraper=scraper,
            paths=paths,
            logging=logging,
            debug=config_dict.get('debug', False),
            dry_run=config_dict.get('dry_run', False),
            user=config_dict.get('user')
        )


class ConfigManager:
    """Configuration manager singleton"""
    _instance: Optional["ConfigManager"] = None
    _config: Optional[AppConfig] = None

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
        return cls._instance

    def load(self, config_path: Optional[Path] = None) -> AppConfig:
        """Load configuration from file or environment"""
        if config_path is None:
            # Try to load from environment variable
            config_path_str = os.getenv("DMH_CONFIG_PATH")
            if config_path_str:
                config_path = Path(config_path_str)
            else:
                # Default to shared drive location
                config_path = Path("//shared/configs/dmh_mr_tool/config.ini")

        if config_path.exists():
            self._config = AppConfig.from_ini(config_path)
            logger.info("Configuration loaded", path=str(config_path))
        else:
            # Use default configuration
            self._config = AppConfig()
            logger.warning("Using default configuration",
                           attempted_path=str(config_path))

        return self._config

    @property
    def config(self) -> AppConfig:
        """Get current configuration"""
        if self._config is None:
            self.load()
        return self._config


# Global config instance
config_manager = ConfigManager()
get_config = lambda: config_manager.config
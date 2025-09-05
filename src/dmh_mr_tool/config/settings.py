# src/dmh_mr_tool/config/settings.py
"""Configuration management with validation and environment support"""

import os
from pathlib import Path
from typing import Any, Dict, Optional
from configparser import ConfigParser
from dataclasses import dataclass, field
from enum import Enum

from pydantic import BaseModel, Field, validator, field_validator
import structlog

logger = structlog.get_logger()


class Environment(str, Enum):
    """Application environments"""
    TESTING = "testing"
    PRODUCTION = "production"


class DatabaseConfig(BaseModel):
    """Database configuration"""
    path: Path
    backup_path: Optional[Path] = None
    echo: bool = False

    @field_validator('path', 'backup_path')
    def validate_path(cls, v):
        if v is None:
            return v
        if not v.exists():
            raise ValueError(f"Directory {v} does not exist")
        return v


class SpiderConfig(BaseModel):
    """Web spider configuration"""
    asx_base_url: str = "https://www.asx.com.au"
    asx_announcement_url: str = "/markets/trade-our-cash-market/todays-announcements"
    betashares_base_url: str = "https://www.betashares.com.au"
    vanguard_api_url: str = "https://api.vanguard.com/rs/gre/gra/1.7.0/datasets/auw-retail/funds"

    max_retries: int = Field(default=3, ge=1, le=10)
    timeout: int = Field(default=30, ge=5, le=120)
    rate_limit_delay: float = Field(default=1.0, ge=0.1, le=10.0)
    concurrent_downloads: int = Field(default=3, ge=1, le=10)


class DMHConfig(BaseModel):
    """DMH System configuration"""
    login_url: str
    post_url: str
    concurrent_limit: int = Field(default=5, ge=1, le=10)


class PathConfig(BaseModel):
    """File path configuration"""
    download_path: Path
    backup_path: Path
    log_path: Path
    temp_path: Path

    @field_validator('download_path', 'backup_path', 'temp_path')
    def ensure_directory_exists(cls, v):
        if not v.exists():
            raise ValueError(f"Directory {v} does not exist")
        return v


class LogConfig(BaseModel):
    """Logging configuration"""
    level: str = Field(default="INFO", pattern="^(DEBUG|INFO|WARNING|ERROR|CRITICAL)$")
    format: str = "json"
    max_file_size: int = Field(default=5_242_880, ge=1_048_576)  # 5MB default, min 1MB
    backup_count: int = Field(default=5, ge=1, le=20)
    enable_console: bool = True
    enable_file: bool = True


@dataclass
class AppConfig:
    """Main application configuration"""
    environment: Environment = Environment.TESTING
    database: DatabaseConfig = field(default_factory=DatabaseConfig)
    spider: SpiderConfig = field(default_factory=SpiderConfig)
    paths: PathConfig = field(default_factory=PathConfig)
    logging: LogConfig = field(default_factory=LogConfig)
    dmh: DMHConfig = field(default_factory=DMHConfig)

    # Runtime settings
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

        env_value = config_dict.get('environment', {}).get('environment', 'development').lower()

        def get_env_value(section: str, key_base: str):
            """load prod_* or test_* config"""
            if section not in config_dict:
                return None
            if env_value == "testing":
                return config_dict[section].get(f"test_{key_base}")
            else:
                return config_dict[section].get(f"prod_{key_base}")

        # Database
        database_cfg = {
            "path": Path(get_env_value("database", "path")),
            "backup_path": Path(get_env_value("database", "backup_path")),
            "echo": config_dict["database"].get("echo", "false") == "true"
        }

        # Paths
        paths_cfg = {
            "download_path": Path(get_env_value("paths", "download_path")),
            "backup_path": Path(get_env_value("paths", "backup_path")),
            "log_path": Path(get_env_value("paths", "log_path")),
            "temp_path": Path(get_env_value("paths", "temp_path"))
        }

        # Spider
        spider_cfg = config_dict.get('spider', {})
        for key in ['max_retries', 'timeout', 'concurrent_downloads']:
            if key in spider_cfg:
                spider_cfg[key] = int(spider_cfg[key])
        if 'rate_limit_delay' in spider_cfg:
            spider_cfg['rate_limit_delay'] = float(spider_cfg['rate_limit_delay'])

        # DMH
        dmh_cfg = {
            "login_url": get_env_value("dmh", "login_url"),
            "post_url": get_env_value("dmh", "post_url")
        }
        if "concurrent_limit" in config_dict["dmh"]:
            dmh_cfg["concurrent_limit"] = int(config_dict["dmh"].get("concurrent_limit"))

        # Logging
        logging_cfg = config_dict.get('logging', {})
        if 'max_file_size' in logging_cfg:
            logging_cfg['max_file_size'] = int(logging_cfg['max_file_size'])
        if 'backup_count' in logging_cfg:
            logging_cfg['backup_count'] = int(logging_cfg['backup_count'])
        if 'enable_console' in logging_cfg:
            logging_cfg['enable_console'] = logging_cfg['enable_console'] == 'true'
        if 'enable_file' in logging_cfg:
            logging_cfg['enable_file'] = logging_cfg['enable_file'] == 'true'

        return cls(
            environment=Environment(env_value),
            database=DatabaseConfig(**database_cfg),
            spider=SpiderConfig(**spider_cfg),
            dmh = DMHConfig(**dmh_cfg),
            paths=PathConfig(**paths_cfg),
            logging=LogConfig(**logging_cfg),
            user=config_dict.get('user', {}).get('default_user')
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
            # Try to load from config_path.ini
            config_path_ini = Path("config/config_path.ini")
            if config_path_ini.exists():
                parser = ConfigParser()
                parser.read(config_path_ini)
                config_path = Path(parser.get("config", "path"))

        if not config_path.exists():
            raise FileNotFoundError(f"Configuration file not found: {config_path}")

        self._config = AppConfig.from_ini(config_path)
        logger.info("Configuration loaded", path=str(config_path))
        return self._config

    @property
    def config(self) -> AppConfig:
        """Get current configuration"""
        if self._config is None:
            raise RuntimeError("Configuration not loaded. Call load() first.")
        return self._config


# Global config instance
config_manager = ConfigManager()
CONFIG = config_manager.load()

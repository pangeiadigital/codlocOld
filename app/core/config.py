"""Application configuration settings."""

from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    """Global application settings."""

    # grid config
    GRID_BASE: int = 6
    MAX_PRECISION: int = 9

    # area of interest - brazil albers
    X_MIN: float = 607_919.0
    Y_MIN: float = 4_528_175.0
    X_MAX: float = 10_685_615.0
    Y_MAX: float = 14_605_871.0

    # limits - max tiles to process in a single request
    MAX_NEIGHBOR_TILES: int = 2500

    class Config:
        env_file = ".env"


settings = Settings()
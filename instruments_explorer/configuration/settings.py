"""The settings of instruments_explorer, read from INSTRUMENTS_EXPLORER_* environment variables.

The values come from the process environment first and then from the `.env` file in the working directory. `bin/instruments-explorer` changes into the project directory before starting, so the relative paths below resolve against the project root.

Typical usage example:

  explorer_settings = Settings()
  explorer_settings.require_security_values()
"""

import urllib.parse
from pathlib import Path
from typing import Literal

import pydantic
import pydantic_settings


class Settings(pydantic_settings.BaseSettings):
    """The settings of instruments_explorer.

    Attributes:
        host: The address the web server listens on.
        port: The port the web server listens on.
        password_hash: The argon2 hash of the login password, produced by bin/set-password.
        session_secret: The secret that signs the session cookie.
        session_max_age_seconds: How long a login lasts, in seconds.
        frontend_directory: The directory holding the built React application.
        data_directory: The directory holding the project's own files, such as the instrument index and uploaded documents.
        unified_broker_interface_directory: The directory of the unified_broker_interface project.
        mongodb_host: The host of the project's own MongoDB.
        mongodb_port: The port of the project's own MongoDB.
        mongodb_username: The MongoDB user name.
        mongodb_password: The MongoDB password.
        mongodb_database: The MongoDB database that holds the project's collections.
        chromadb_host: The host of the project's own ChromaDB.
        chromadb_port: The port of the project's own ChromaDB.
        store_timeout_seconds: How long a request to MongoDB or ChromaDB may take, in seconds.
        ubi_request_timeout_seconds: How long a request to UBI's REST API, Redis or MongoDB may take, in seconds.
        ubi_may_connect: Whether this process may call UBI's connect route when no usable token is stored.
        ubi_connect_cooldown_seconds: The shortest time between two connects to UBI, in seconds.
        index_check_interval_seconds: How often UBI's mapping date is checked for a new catalogue, in seconds.
        live_quote_interval_seconds: How often the watched instruments' quotes are read from UBI's Redis, in seconds.
        risk_free_rate: The yearly rate options are discounted at when working out implied volatility and the Greeks, such as 0.065 for 6.5%.
        knowledge_contact: Contact details sent to Wikipedia in the user agent, as its robot policy asks; the Wikipedia fetcher is off while empty.
        google_search_api_key: The Google Programmable Search API key; web search is off while empty.
        google_search_engine_id: The Google Programmable Search engine id.
        knowledge_host_interval_seconds: The shortest wait between two requests to the same website, in seconds.
        knowledge_refresh_hours: How often news is fetched again for companies fetched before, in hours.
        anthropic_api_key: The Claude API key for the chat assistant, or an empty string while it is not configured.
        claude_model: The Claude model the chat assistant uses.
        claude_effort: How much effort the chat assistant's model spends on each turn.
        claude_daily_token_limit: The most tokens the chat assistant may use in one day.
    """

    model_config = pydantic_settings.SettingsConfigDict(
        env_prefix='INSTRUMENTS_EXPLORER_',
        env_file='.env',
        extra='ignore',
    )

    host: str = '0.0.0.0'
    port: int = 8100
    password_hash: str = ''
    session_secret: str = ''
    session_max_age_seconds: int = 43200
    frontend_directory: Path = Path('frontend/dist')
    data_directory: Path = Path('data')
    unified_broker_interface_directory: Path = Path(
        '/home/pramod/Projects/unified_broker_interface'
    )
    mongodb_host: str = '127.0.0.1'
    mongodb_port: int = 3003
    mongodb_username: str = 'instruments_explorer'
    mongodb_password: str = ''
    mongodb_database: str = 'instruments_explorer'
    chromadb_host: str = '127.0.0.1'
    chromadb_port: int = 3004
    store_timeout_seconds: float = pydantic.Field(default=5.0, gt=0)
    ubi_request_timeout_seconds: float = pydantic.Field(default=30.0, gt=0)
    ubi_may_connect: bool = True
    ubi_connect_cooldown_seconds: float = pydantic.Field(default=60.0, gt=0)
    index_check_interval_seconds: float = pydantic.Field(default=600.0, gt=0)
    live_quote_interval_seconds: float = pydantic.Field(default=0.5, gt=0)
    risk_free_rate: float = pydantic.Field(default=0.065, ge=0, lt=1)
    knowledge_contact: str = ''
    google_search_api_key: str = ''
    google_search_engine_id: str = ''
    knowledge_host_interval_seconds: float = pydantic.Field(default=2.0, ge=0)
    knowledge_refresh_hours: float = pydantic.Field(default=6.0, gt=0)
    anthropic_api_key: str = ''
    claude_model: str = 'claude-opus-5-5'
    claude_effort: Literal[
        'low',
        'medium',
        'high',
        'xhigh',
        'max',
    ] = 'high'
    claude_daily_token_limit: int = pydantic.Field(default=2_000_000, gt=0)

    def mongodb_uri(self) -> str:
        """Builds the connection string for the project's own MongoDB.

        Returns:
            str: A mongodb:// URI that authenticates against the admin database.
        """
        username = urllib.parse.quote_plus(self.mongodb_username)
        password = urllib.parse.quote_plus(self.mongodb_password)
        return f'mongodb://{username}:{password}@{self.mongodb_host}:{self.mongodb_port}/?authSource=admin'

    def chromadb_url(self) -> str:
        """Builds the base address of the project's own ChromaDB.

        Returns:
            str: An http:// address without a trailing slash.
        """
        return f'http://{self.chromadb_host}:{self.chromadb_port}'

    def assistant_configured(self) -> bool:
        """Says whether the chat assistant has an API key.

        Returns:
            bool: True when a Claude API key is set.
        """
        return self.anthropic_api_key != ''

    def require_security_values(self) -> None:
        """Checks that the password hash and session secret are set.

        Raises:
            ValueError: The password hash or the session secret is empty.
        """
        if not self.password_hash:
            raise ValueError(
                'INSTRUMENTS_EXPLORER_PASSWORD_HASH is empty; run bin/set-password and add the hash to .env.'
            )
        if not self.session_secret:
            raise ValueError(
                'INSTRUMENTS_EXPLORER_SESSION_SECRET is empty; run bin/set-password and add the secret to .env.'
            )

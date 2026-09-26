"""Builds the tradingmachine objects this project reaches UBI through, from UBI's own .env.

Typical usage example:

  components = TradingmachineComponents(ubi_configuration, 30.0, True, 60.0, clock.SystemClock())
  gateway = catalogue_gateway.CatalogueGateway(components.catalogue)
  components.close()
"""

from tradingmachine.ubi_client import client
from tradingmachine.ubi_client import instrument_catalogue
from tradingmachine.ubi_stores import live_quote_reader
from tradingmachine.ubi_stores import store_settings
from tradingmachine.ubi_stores import stored_login_reader
from tradingmachine.ubi_stores import stored_login_token_source

from instruments_explorer.configuration import (
    unified_broker_interface_configuration,
)
from instruments_explorer.utilities import clock

CONNECTION_POOL_SIZE = 16


class TradingmachineComponents:
    """tradingmachine's client, stored-token source, catalogue and live quote reader, sharing UBI's addresses.

    Attributes:
        stored_login_reader: Reads UBI's stored login and api key from UBI's Redis and MongoDB.
        token_source: Uses UBI's stored token, connecting only when there is none and connecting is allowed.
        client: Sends every request to UBI's REST API.
        catalogue: Reads instruments, quotes, candles and the instrument master by instrument id.
        live_quote_reader: Reads many instruments' live quotes at once from UBI's Redis.
    """

    def __init__(
        self,
        ubi_configuration: (
            unified_broker_interface_configuration.UnifiedBrokerInterfaceConfiguration
        ),
        timeout_seconds: float,
        may_connect: bool,
        connect_cooldown_seconds: float,
        time_source: clock.SystemClock,
    ):
        """Builds every component; nothing connects until the first request.

        Args:
            ubi_configuration (UnifiedBrokerInterfaceConfiguration): UBI's store addresses, credentials and REST address, read from UBI's .env.
            timeout_seconds (float): How long a request, Redis command or MongoDB query may take, in seconds.
            may_connect (bool): Whether this process may call UBI's connect route when no stored token is usable.
            connect_cooldown_seconds (float): The shortest time between two connect attempts, in seconds.
            time_source (clock.SystemClock): The source of the current time.
        """
        redis_settings = store_settings.RedisSettings(
            host=ubi_configuration.redis_host,
            port=ubi_configuration.redis_port,
            database=ubi_configuration.redis_database,
            username=ubi_configuration.redis_username,
            password=ubi_configuration.redis_password,
            timeout_seconds=timeout_seconds,
        )
        mongo_settings = store_settings.MongoSettings(
            host=ubi_configuration.mongodb_host,
            port=ubi_configuration.mongodb_port,
            database_name=ubi_configuration.mongodb_database,
            username=ubi_configuration.mongodb_username,
            password=ubi_configuration.mongodb_password,
            timeout_seconds=timeout_seconds,
        )
        self.stored_login_reader = stored_login_reader.StoredLoginReader(
            redis_settings,
            mongo_settings,
        )
        self.token_source = stored_login_token_source.StoredLoginTokenSource(
            self.stored_login_reader,
            time_source,
            may_connect=may_connect,
            connect_cooldown_seconds=connect_cooldown_seconds,
        )
        self.client = client.UnifiedBrokerInterface(
            base_url=ubi_configuration.rest_api_base_url,
            timeout_seconds=timeout_seconds,
            token_source=self.token_source,
            connection_pool_size=CONNECTION_POOL_SIZE,
        )
        self.catalogue = instrument_catalogue.InstrumentCatalogue(self.client)
        self.live_quote_reader = live_quote_reader.LiveQuoteReader(
            redis_settings
        )

    def close(self) -> None:
        """Closes the REST connections and the Redis and MongoDB clients."""
        self.client.close()
        self.stored_login_reader.close()
        self.live_quote_reader.close()

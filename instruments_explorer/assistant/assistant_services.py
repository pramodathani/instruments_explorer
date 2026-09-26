"""The route groups the assistant's tools call, so the assistant can do exactly what the pages can.

Typical usage example:

  services = AssistantServices(instruments, charts, derivatives, knowledge, screener)
  answer = await services.instruments.search(q='reliance')
"""

from instruments_explorer.routes import chart_routes
from instruments_explorer.routes import derivative_routes
from instruments_explorer.routes import instrument_routes
from instruments_explorer.routes import knowledge_routes
from instruments_explorer.routes import screener_routes


class AssistantServices:
    """Holds the route groups whose handlers the tools call.

    Attributes:
        instruments: Search, instrument details and quotes.
        charts: Candles and indicators.
        derivatives: Expiries and option chains.
        knowledge: Company knowledge and its search.
        screener: Screens over stored daily figures.
    """

    def __init__(
        self,
        instruments: instrument_routes.InstrumentRoutes,
        charts: chart_routes.ChartRoutes,
        derivatives: derivative_routes.DerivativeRoutes,
        knowledge: knowledge_routes.KnowledgeRoutes,
        screener: screener_routes.ScreenerRoutes,
    ):
        """Keeps the route groups.

        Args:
            instruments (instrument_routes.InstrumentRoutes): Search, instrument details and quotes.
            charts (chart_routes.ChartRoutes): Candles and indicators.
            derivatives (derivative_routes.DerivativeRoutes): Expiries and option chains.
            knowledge (knowledge_routes.KnowledgeRoutes): Company knowledge and its search.
            screener (screener_routes.ScreenerRoutes): Screens over stored daily figures.
        """
        self.instruments = instruments
        self.charts = charts
        self.derivatives = derivatives
        self.knowledge = knowledge
        self.screener = screener

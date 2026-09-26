"""The get_option_chain tool: an underlying's expiries, futures and option chain with open interest and implied volatility.

Typical usage example:

  outcome = await GetOptionChainTool(services).run({'exchange': 'nse', 'underlying': 'NIFTY'})
"""

from typing import Any, ClassVar

from instruments_explorer.assistant.tools import base

STRIKES_EACH_SIDE = 12


class GetOptionChainTool(base.BaseTool):
    """Reads the option chain the derivatives page shows, keeping the strikes nearest the money."""

    NAME = 'get_option_chain'
    DESCRIPTION = "Reads an underlying's option chain for one expiry from the derivatives page: for each strike, the call's and put's last price, change, open interest, volume, implied volatility and delta, plus the spot, forward, at-the-money strike, max pain and put-call ratio. Without an expiry it uses the nearest one and also lists every expiry and future. Returns the 12 strikes on each side of the money, unless all_strikes is true."
    INPUT_SCHEMA: ClassVar[dict[str, Any]] = {
        'type': 'object',
        'properties': {
            'exchange': {
                'type': 'string',
                'enum': [
                    'nse',
                    'bse',
                    'mcx',
                    'ncdex',
                ],
            },
            'underlying': {
                'type': 'string',
                'description': 'The underlying symbol, such as NIFTY, BANKNIFTY, RELIANCE or GOLD.',
            },
            'expiry': {
                'type': 'string',
                'description': 'The expiry as "YYYY-MM-DD". Defaults to the nearest.',
            },
            'all_strikes': {
                'type': 'boolean',
            },
        },
        'required': [
            'exchange',
            'underlying',
        ],
        'additionalProperties': False,
    }

    async def run(self, arguments: dict[str, Any]) -> base.ToolOutcome:
        """Reads the expiries and the chain.

        Args:
            arguments (dict[str, Any]): The checked input.

        Returns:
            base.ToolOutcome: The expiries, futures and the chain.

        Raises:
            base.ToolError: The underlying has no derivatives, or the expiry has no options.
        """
        exchange = arguments['exchange']
        underlying = arguments['underlying'].upper()
        expiries = await self.call_route(
            self.services.derivatives.expiries(exchange, underlying)
        )
        option_expiries = expiries.get('option_expiries', [])
        expiry = arguments.get('expiry')
        if expiry is None:
            if not option_expiries:
                raise base.ToolError(
                    f'{underlying} has futures but no options.'
                )
            expiry = option_expiries[0]['expiry_date']
        chain = await self.call_route(
            self.services.derivatives.chain(exchange, underlying, expiry)
        )
        rows = chain['rows']
        if not arguments.get('all_strikes', False):
            rows = self._near_the_money(rows, chain.get('atm_strike'))
        summary = dict(chain)
        summary['rows'] = rows
        summary['strikes_total'] = len(chain['rows'])
        summary['option_expiries'] = option_expiries
        summary['futures'] = expiries.get('futures', [])
        return base.ToolOutcome(
            summary, f'{underlying} {expiry}: {len(rows)} strikes'
        )

    def _near_the_money(
        self,
        rows: list[dict[str, Any]],
        atm_strike: float | None,
    ) -> list[dict[str, Any]]:
        """Keeps the strikes nearest the at-the-money strike.

        Args:
            rows (list[dict[str, Any]]): Every strike's row, in strike order.
            atm_strike (float | None): The at-the-money strike, or None.

        Returns:
            list[dict[str, Any]]: At most STRIKES_EACH_SIDE rows on each side of the money.
        """
        if atm_strike is None:
            middle = len(rows) // 2
        else:
            middle = 0
            for position, row in enumerate(rows):
                if row['strike'] <= atm_strike:
                    middle = position
        first = max(middle - STRIKES_EACH_SIDE, 0)
        return rows[first : middle + STRIKES_EACH_SIDE + 1]

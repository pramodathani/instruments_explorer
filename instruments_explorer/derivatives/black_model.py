"""Black's 1976 model for options on a forward price, with its Greeks and implied volatility.

Indian index and stock options settle against the underlying at expiry, and the future of the same expiry is the market's own forward price for that day, so Black-76 on that forward avoids guessing dividends and financing costs.

Typical usage example:

  model = BlackModel()
  price = model.price(23200.0, 23000.0, 0.02, 0.14, 0.065, 'CE')
  volatility = ImpliedVolatilitySolver(model).solve(price, 23200.0, 23000.0, 0.02, 0.065, 'CE')
"""

import math

_SQUARE_ROOT_OF_TWO = math.sqrt(2.0)
_SQUARE_ROOT_OF_TWO_PI = math.sqrt(2.0 * math.pi)
_DAYS_PER_YEAR = 365.0


class BlackModel:
    """Prices European calls and puts on a forward and works out their Greeks."""

    def price(
        self,
        forward: float,
        strike: float,
        years: float,
        volatility: float,
        rate: float,
        option_type: str,
    ) -> float:
        """Prices an option.

        Args:
            forward (float): The forward price of the underlying for the option's expiry.
            strike (float): The strike.
            years (float): The time to expiry, in years; must be above zero.
            volatility (float): The yearly volatility, such as 0.15 for 15%; must be above zero.
            rate (float): The yearly risk-free rate used for discounting, such as 0.065.
            option_type (str): "CE" for a call or "PE" for a put.

        Returns:
            float: The option's price.
        """
        discount = math.exp(-rate * years)
        first, second = self._distances(forward, strike, years, volatility)
        if option_type == 'CE':
            return discount * (
                forward * self._cumulative(first)
                - strike * self._cumulative(second)
            )
        return discount * (
            strike * self._cumulative(-second)
            - forward * self._cumulative(-first)
        )

    def greeks(
        self,
        forward: float,
        strike: float,
        years: float,
        volatility: float,
        rate: float,
        option_type: str,
    ) -> dict[str, float]:
        """Works out how the option's price responds to the forward, volatility and time.

        Args:
            forward (float): The forward price of the underlying for the option's expiry.
            strike (float): The strike.
            years (float): The time to expiry, in years; must be above zero.
            volatility (float): The yearly volatility; must be above zero.
            rate (float): The yearly risk-free rate.
            option_type (str): "CE" for a call or "PE" for a put.

        Returns:
            dict[str, float]: "delta" (price change per unit of forward), "gamma" (delta change per unit of forward), "vega" (price change per one percentage point of volatility) and "theta" (price change per calendar day).
        """
        discount = math.exp(-rate * years)
        first, second = self._distances(forward, strike, years, volatility)
        density = self._density(first)
        root_years = math.sqrt(years)
        gamma = discount * density / (forward * volatility * root_years)
        vega = discount * forward * density * root_years / 100.0
        decay = -discount * forward * density * volatility / (2.0 * root_years)
        if option_type == 'CE':
            delta = discount * self._cumulative(first)
            carry = (
                rate
                * discount
                * (
                    forward * self._cumulative(first)
                    - strike * self._cumulative(second)
                )
            )
        else:
            delta = -discount * self._cumulative(-first)
            carry = (
                rate
                * discount
                * (
                    strike * self._cumulative(-second)
                    - forward * self._cumulative(-first)
                )
            )
        return {
            'delta': delta,
            'gamma': gamma,
            'vega': vega,
            'theta': (decay + carry) / _DAYS_PER_YEAR,
        }

    def _distances(
        self,
        forward: float,
        strike: float,
        years: float,
        volatility: float,
    ) -> tuple[float, float]:
        """Works out Black's d1 and d2.

        Args:
            forward (float): The forward price.
            strike (float): The strike.
            years (float): The time to expiry, in years.
            volatility (float): The yearly volatility.

        Returns:
            tuple[float, float]: A tuple (d1, d2).
        """
        spread = volatility * math.sqrt(years)
        first = (math.log(forward / strike) + spread * spread / 2.0) / spread
        return first, first - spread

    def _cumulative(self, value: float) -> float:
        """The standard normal cumulative distribution.

        Args:
            value (float): The point.

        Returns:
            float: The probability that a standard normal variable is below the point.
        """
        return 0.5 * (1.0 + math.erf(value / _SQUARE_ROOT_OF_TWO))

    def _density(self, value: float) -> float:
        """The standard normal density.

        Args:
            value (float): The point.

        Returns:
            float: The density at the point.
        """
        return math.exp(-value * value / 2.0) / _SQUARE_ROOT_OF_TWO_PI


class ImpliedVolatilitySolver:
    """Finds the volatility at which Black's model gives an option's market price.

    Attributes:
        lowest: The lowest volatility searched, as a fraction.
        highest: The highest volatility searched, as a fraction.
        tolerance: How close the model price must come to the market price, in rupees.
        maximum_steps: The most halvings of the search range.
    """

    def __init__(
        self,
        model: BlackModel,
        lowest: float = 0.001,
        highest: float = 5.0,
        tolerance: float = 0.0001,
        maximum_steps: int = 100,
    ):
        """Creates the solver.

        Args:
            model (BlackModel): Prices options.
            lowest (float): The lowest volatility searched, as a fraction.
            highest (float): The highest volatility searched, as a fraction.
            tolerance (float): How close the model price must come to the market price, in rupees.
            maximum_steps (int): The most halvings of the search range.
        """
        self.lowest = lowest
        self.highest = highest
        self.tolerance = tolerance
        self.maximum_steps = maximum_steps
        self._model = model

    def solve(
        self,
        market_price: float,
        forward: float,
        strike: float,
        years: float,
        rate: float,
        option_type: str,
    ) -> float | None:
        """Finds the implied volatility by bisection, which always converges because price rises with volatility.

        Args:
            market_price (float): The option's price in the market.
            forward (float): The forward price of the underlying for the option's expiry.
            strike (float): The strike.
            years (float): The time to expiry, in years.
            rate (float): The yearly risk-free rate.
            option_type (str): "CE" for a call or "PE" for a put.

        Returns:
            float | None: The volatility as a fraction, or None when the inputs cannot have one: a price at or below the option's discounted intrinsic value, a price the search range cannot reach, or no time left.
        """
        if market_price <= 0 or forward <= 0 or strike <= 0 or years <= 0:
            return None
        low = self.lowest
        high = self.highest
        low_price = self._model.price(
            forward, strike, years, low, rate, option_type
        )
        high_price = self._model.price(
            forward, strike, years, high, rate, option_type
        )
        if market_price <= low_price or market_price >= high_price:
            return None
        for _ in range(self.maximum_steps):
            middle = (low + high) / 2.0
            middle_price = self._model.price(
                forward, strike, years, middle, rate, option_type
            )
            if abs(middle_price - market_price) < self.tolerance:
                return middle
            if middle_price < market_price:
                low = middle
            else:
                high = middle
        return (low + high) / 2.0

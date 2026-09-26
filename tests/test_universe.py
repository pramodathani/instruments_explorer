from instruments_explorer.universe import universe_layout


class TestUniverseLayout:
    """Tests for UniverseLayout."""

    def _record(
        self,
        instrument_id: str,
        asset_class: str,
        shape: str,
        root: str,
        expiry: str | None = None,
        strike: float | None = None,
        option_type: str | None = None,
    ) -> tuple:
        """Makes one index record.

        Args:
            instrument_id (str): The instrument id.
            asset_class (str): The asset class.
            shape (str): The shape: security, future or option.
            root (str): The underlying's name.
            expiry (str | None): The expiry date.
            strike (float | None): The strike price.
            option_type (str | None): CE or PE.

        Returns:
            tuple: A record in the order InstrumentIndex.universe_records gives.
        """
        return (
            instrument_id,
            'nse',
            asset_class,
            shape,
            0,
            root,
            f'{root} {instrument_id}',
            expiry,
            strike,
            option_type,
            None,
        )

    def test_every_record_gets_a_position(self) -> None:
        """Checks that every record is laid out once with three coordinates."""
        records = [
            self._record('a', 'equity', 'security', 'TCS'),
            self._record('b', 'equity', 'future', 'TCS', '2026-10-27'),
            self._record(
                'c', 'equity', 'option', 'TCS', '2026-10-27', 4000.0, 'CE'
            ),
            self._record(
                'd', 'equity', 'option', 'TCS', '2026-10-27', 4000.0, 'PE'
            ),
            self._record('e', 'commodity', 'future', 'GOLD', '2026-12-05'),
            self._record('f', 'mystery', 'security', 'ODD'),
        ]
        layout = universe_layout.UniverseLayout().build(records)
        assert layout['ids'] == [
            'a',
            'b',
            'c',
            'd',
            'e',
            'f',
        ]
        assert len(layout['positions']) == 18
        assert layout['shapes'] == [
            0,
            1,
            2,
            2,
            1,
            0,
        ]
        assert layout['asset_classes'][5] == universe_layout.GALAXY_ORDER.index(
            'other'
        )

    def test_calls_sit_above_puts(self) -> None:
        """Checks that a call is placed above the put of the same strike."""
        records = [
            self._record(
                'call', 'equity', 'option', 'TCS', '2026-10-27', 4000.0, 'CE'
            ),
            self._record(
                'put', 'equity', 'option', 'TCS', '2026-10-27', 4000.0, 'PE'
            ),
        ]
        positions = universe_layout.UniverseLayout().build(records)['positions']
        assert positions[1] > positions[4]
        assert positions[0] == positions[3]

    def test_the_biggest_underlying_is_in_the_middle(self) -> None:
        """Checks that the underlying with most instruments is at its galaxy's centre and labelled first."""
        records = [
            self._record('small', 'equity', 'security', 'SMALL'),
            self._record('big-1', 'equity', 'security', 'BIG'),
            self._record('big-2', 'equity', 'future', 'BIG', '2026-10-27'),
        ]
        layout = universe_layout.UniverseLayout().build(records)
        galaxy = layout['galaxies'][0]
        assert layout['clusters'][0]['label'] == 'BIG'
        assert layout['clusters'][0]['x'] == galaxy['x']
        assert galaxy['count'] == 3

    def test_the_layout_is_repeatable(self) -> None:
        """Checks that the same records always give the same positions."""
        records = [
            self._record('a', 'equity', 'security', 'TCS'),
            self._record('b', 'currency', 'future', 'USDINR', '2026-10-27'),
        ]
        first = universe_layout.UniverseLayout().build(records)
        second = universe_layout.UniverseLayout().build(records)
        assert first['positions'] == second['positions']

    def test_derivatives_connect_to_their_underlying(self) -> None:
        """Checks that futures and options connect to the NSE cash instrument, and commodity options to the nearest future."""
        records = [
            self._record('bse-share', 'equity', 'security', 'TCS'),
            self._record('nse-share', 'equity', 'security', 'TCS'),
            self._record('future', 'equity', 'future', 'TCS', '2026-10-27'),
            self._record(
                'call', 'equity', 'option', 'TCS', '2026-10-27', 4000.0, 'CE'
            ),
            self._record(
                'gold-later', 'commodity', 'future', 'GOLD', '2026-12-05'
            ),
            self._record(
                'gold-near', 'commodity', 'future', 'GOLD', '2026-10-05'
            ),
            self._record(
                'gold-call',
                'commodity',
                'option',
                'GOLD',
                '2026-10-05',
                70000.0,
                'CE',
            ),
        ]
        records[1] = records[1][:1] + ('nse',) + records[1][2:]
        records[0] = records[0][:1] + ('bse',) + records[0][2:]
        layout = universe_layout.UniverseLayout().build(records)
        anchors = {}
        for position, instrument_id in enumerate(layout['ids']):
            anchor = layout['anchors'][position]
            anchors[instrument_id] = (
                layout['ids'][anchor] if anchor >= 0 else None
            )
        assert anchors == {
            'bse-share': None,
            'nse-share': None,
            'future': 'nse-share',
            'call': 'nse-share',
            'gold-later': None,
            'gold-near': None,
            'gold-call': 'gold-near',
        }

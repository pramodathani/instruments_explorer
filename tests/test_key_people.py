"""Tests for headquarters and key people: the postcode geocoder, the key people book, the registry fetcher, the document reader and their routes."""

import asyncio
import types
import zipfile
from pathlib import Path
from typing import Any

from instruments_explorer.knowledge import fetched_document
from instruments_explorer.knowledge import headquarters_sweep
from instruments_explorer.knowledge import key_people_book
from instruments_explorer.knowledge import key_people_extractor
from instruments_explorer.knowledge import polite_client
from instruments_explorer.knowledge import postcode_geocoder
from instruments_explorer.knowledge.fetchers import zaubacorp_directors
from tests import fakes
from tests import test_routes

_HEADERS = {
    'X-Requested-With': 'instruments-explorer',
}
_POSTCODE_LINES = [
    'IN\t400021\tNariman Point\tMaharashtra\t16\tMumbai\t518\tMumbai\t\t18.9256\t72.8242\t4',
    'IN\t400021\tMantralaya\tMaharashtra\t16\tMumbai\t518\tMumbai\t\t18.9270\t72.8260\t4',
    'IN\t560100\tElectronic City\tKarnataka\t19\tBangalore\t572\tBangalore South\t\t12.8450\t77.6600\t4',
    'IN\t302001\tJaipur G.P.O.\tRajasthan\t24\tJaipur\t110\tJaipur\t\t26.9124\t75.7873\t4',
]
_SEARCH_PAGE = """
<div id="resultsList">
  <div class="companies-list"><h2><a href="https://www.zaubacorp.com/RELIANCE-INDUSTRIES-EMPLOYEES-TRUST-U01100MH2021PTC357153">RELIANCE INDUSTRIES EMPLOYEES TRUST</a></h2></div>
  <div class="companies-list"><h2><a href="https://www.zaubacorp.com/RELIANCE-INDUSTRIES-LIMITED-L17110MH1973PLC019786">RELIANCE INDUSTRIES LIMITED</a></h2></div>
</div>
"""
_COMPANY_PAGE = """
<h4>Current Directors &amp; Key Managerial Personnel of RELIANCE INDUSTRIES LIMITED</h4>
<table>
  <tr><th>DIN</th><th>Director Name</th><th>Designation</th><th>Appointment Date</th></tr>
  <tr><td>00001695</td><td>MUKESH DHIRUBHAI AMBANI</td><td>Managing Director</td><td>1977-04-01</td></tr>
  <tr><td>02011213</td><td>ARUNDHATI  BHATTACHARYA</td><td>Director</td><td>2019-08-12</td></tr>
</table>
<h4>Past Directors</h4>
<table><tr><td>00000001</td><td>SOMEONE ELSE</td><td>Director</td><td>2001-01-01</td></tr></table>
"""


class TestPostcodeGeocoder:
    """Tests for PostcodeGeocoder."""

    def _geocoder(
        self, directory: Path, zipped: bool
    ) -> postcode_geocoder.PostcodeGeocoder:
        """Writes the sample postcode file and makes a geocoder over it.

        Args:
            directory (Path): Where to write the file.
            zipped (bool): Whether to write IN.zip instead of IN.txt.

        Returns:
            postcode_geocoder.PostcodeGeocoder: The geocoder.
        """
        text = '\n'.join(_POSTCODE_LINES) + '\n'
        if zipped:
            with zipfile.ZipFile(directory / 'IN.zip', 'w') as archive:
                archive.writestr('IN.txt', text)
        else:
            (directory / 'IN.txt').write_text(text, encoding='utf-8')
        return postcode_geocoder.PostcodeGeocoder(directory)

    def test_postcode_is_averaged(self, tmp_path: Path) -> None:
        """Checks that a postcode with two places sits between them.

        Args:
            tmp_path (Path): A temporary directory from pytest.
        """
        place = self._geocoder(tmp_path, zipped=False).locate(
            '400021', 'Mumbai', 'India'
        )
        assert place == {
            'latitude': 18.9263,
            'longitude': 72.8251,
            'precision': 'postcode',
            'place': 'Nariman Point',
        }

    def test_spaced_postcode_from_the_zip(self, tmp_path: Path) -> None:
        """Checks that a postcode written with a space is read from IN.zip.

        Args:
            tmp_path (Path): A temporary directory from pytest.
        """
        place = self._geocoder(tmp_path, zipped=True).locate(
            '56 0100', 'Bengaluru', 'India'
        )
        assert place['precision'] == 'postcode'
        assert place['latitude'] == 12.845

    def test_city_fallback_with_an_old_name(self, tmp_path: Path) -> None:
        """Checks that an unknown postcode falls back to the city, mapping Bangalore to Bengaluru both ways.

        Args:
            tmp_path (Path): A temporary directory from pytest.
        """
        place = self._geocoder(tmp_path, zipped=False).locate(
            '999999', 'Bengaluru', 'India'
        )
        assert place['precision'] == 'city'
        assert place['longitude'] == 77.66

    def test_other_countries_and_missing_file(self, tmp_path: Path) -> None:
        """Checks that addresses outside India, and any address without the file, are not placed.

        Args:
            tmp_path (Path): A temporary directory from pytest.
        """
        geocoder = self._geocoder(tmp_path, zipped=False)
        assert geocoder.locate('400021', 'Mumbai', 'Singapore') is None
        empty = postcode_geocoder.PostcodeGeocoder(tmp_path / 'missing')
        assert not empty.available()
        assert empty.locate('400021', 'Mumbai', 'India') is None


class TestKeyPeopleBook:
    """Tests for KeyPeopleBook."""

    def test_sources_are_merged_and_sorted(self) -> None:
        """Checks that the same people from Yahoo and the registry are merged, and executives and board are ordered."""
        arranged = key_people_book.KeyPeopleBook().arrange(
            {
                'zaubacorp': [
                    {
                        'name': 'ARUNDHATI  BHATTACHARYA',
                        'role': 'Director',
                        'din': '02011213',
                        'appointed_on': '2019-08-12',
                    },
                    {
                        'name': 'MADHUSUDANA SIVAPRASAD PANDA',
                        'role': 'Whole-time director',
                    },
                    {
                        'name': 'SRIKANTH VENKATACHARI',
                        'role': 'CFO(KMP)',
                    },
                ],
                'yahoo': [
                    {
                        'name': 'Mr. Srikanth  Venkatachari',
                        'role': 'Chief Financial Officer',
                        'age': 59,
                    },
                    {
                        'name': 'Mr. Mukesh Dhirubhai Ambani',
                        'role': 'Chairman & MD',
                    },
                    {
                        'name': 'Mr. Panda Madhusudana Siva Prasad',
                        'role': 'Executive Director',
                    },
                ],
            }
        )
        executives = []
        for person in arranged['executives']:
            executives.append(person['name'])
        board = []
        for person in arranged['board']:
            board.append(person['name'])
        assert executives == [
            'Mukesh Dhirubhai Ambani',
            'Srikanth Venkatachari',
            'Panda Madhusudana Siva Prasad',
        ]
        assert board == [
            'Mukesh Dhirubhai Ambani',
            'Panda Madhusudana Siva Prasad',
            'Arundhati Bhattacharya',
        ]
        assert arranged['executives'][1]['sources'] == [
            'yahoo',
            'zaubacorp',
        ]
        assert arranged['board'][2]['appointed_on'] == '2019-08-12'

    def test_relatives_are_not_merged(self) -> None:
        """Checks that people sharing a father's name and surname stay separate."""
        book = key_people_book.KeyPeopleBook()
        pairs = [
            ('Mukesh Ambani', 'Anant Mukesh Ambani', False),
            ('Anant Mukesh Ambani', 'Akash Mukesh Ambani', False),
            ('Isha Ambani', 'ISHA MUKESH AMBANI', True),
            ('Salil Parekh', 'Savithri Parekh', False),
        ]
        for first, second, same in pairs:
            assert (
                book._same_person(book._tokens(first), book._tokens(second))
                is same
            )

    def test_passage(self) -> None:
        """Checks that the searchable passage names the address and each group."""
        book = key_people_book.KeyPeopleBook()
        arranged = book.arrange(
            {
                'yahoo': [
                    {
                        'name': 'Mr. Salil Parekh',
                        'role': 'MD, CEO & Director',
                    },
                ],
            }
        )
        text = book.describe(
            'Infosys Limited',
            arranged,
            {
                'address_lines': [
                    'Plot No. 44/97 A',
                ],
                'city': 'Bengaluru',
                'postcode': '560100',
                'country': 'India',
            },
        )
        assert (
            'Headquarters (registered office): Plot No. 44/97 A, Bengaluru, 560100, India.'
            in text
        )
        assert '- Salil Parekh: MD, CEO & Director' in text
        assert 'Board of directors:' in text


class TestZaubacorpFetcher:
    """Tests for ZaubacorpDirectorsFetcher's page reading."""

    def _fetcher(self) -> zaubacorp_directors.ZaubacorpDirectorsFetcher:
        """Makes the fetcher without a network.

        Returns:
            zaubacorp_directors.ZaubacorpDirectorsFetcher: The fetcher.
        """
        return zaubacorp_directors.ZaubacorpDirectorsFetcher(None)

    def test_listed_company_is_chosen(self) -> None:
        """Checks that the listed company with the matching name is chosen over a private one."""
        url, cin = self._fetcher().choose_result(
            _SEARCH_PAGE, 'Reliance Industries Limited'
        )
        assert cin == 'L17110MH1973PLC019786'
        assert url.endswith('L17110MH1973PLC019786')

    def test_no_listed_match(self) -> None:
        """Checks that a name with no listed match is refused."""
        try:
            self._fetcher().choose_result(_SEARCH_PAGE, 'Tata Steel Limited')
        except ValueError as error:
            assert 'Tata Steel' in str(error)
        else:
            raise AssertionError('Expected a ValueError.')

    def test_current_directors_only(self) -> None:
        """Checks that only the current directors table is read."""
        people = self._fetcher().parse_directors(_COMPANY_PAGE)
        assert people == [
            {
                'name': 'MUKESH DHIRUBHAI AMBANI',
                'role': 'Managing Director',
                'din': '00001695',
                'appointed_on': '1977-04-01',
            },
            {
                'name': 'ARUNDHATI BHATTACHARYA',
                'role': 'Director',
                'din': '02011213',
                'appointed_on': '2019-08-12',
            },
        ]

    def test_fetch_through_the_polite_client(self) -> None:
        """Checks the whole fetch against prepared pages."""

        def answer(request: Any) -> Any:
            """Serves robots.txt, the search page and the company page.

            Args:
                request (Any): The httpx request.

            Returns:
                Any: The httpx response.
            """
            import httpx

            if request.url.path == '/robots.txt':
                return httpx.Response(
                    200, text='User-agent: *\nDisallow: /login\n'
                )
            if 'companysearchresults' in request.url.path:
                return httpx.Response(200, text=_SEARCH_PAGE)
            return httpx.Response(200, text=_COMPANY_PAGE)

        async def run() -> Any:
            """Runs the fetch.

            Returns:
                Any: The fetch result.
            """
            import httpx

            async with httpx.AsyncClient(
                transport=httpx.MockTransport(answer)
            ) as client:
                polite = polite_client.PoliteHttpClient(client, 'test', 0.0)
                fetcher = zaubacorp_directors.ZaubacorpDirectorsFetcher(polite)
                company = types.SimpleNamespace(
                    name='Reliance Industries Limited'
                )
                return await fetcher.fetch(company)

        result = asyncio.run(run())
        assert result.profile['cin'] == 'L17110MH1973PLC019786'
        assert len(result.profile['key_people.zaubacorp']) == 2


class FakeClaudeResponses:
    """A stand-in for client.messages with a prepared answer.

    Attributes:
        text: The answer's text.
        requests: The keyword arguments of each request.
    """

    def __init__(self, text: str):
        """Keeps the answer.

        Args:
            text (str): The answer's text.
        """
        self.text = text
        self.requests = []

    async def create(self, **request: Any) -> Any:
        """Records the request and answers.

        Args:
            **request (Any): The request's keyword arguments.

        Returns:
            Any: A message-like object with the text and some usage.
        """
        self.requests.append(request)
        return types.SimpleNamespace(
            stop_reason='end_turn',
            content=[
                types.SimpleNamespace(
                    type='text',
                    text=self.text,
                ),
            ],
            usage=types.SimpleNamespace(
                input_tokens=900,
                output_tokens=100,
                cache_read_input_tokens=0,
                cache_creation_input_tokens=0,
            ),
        )


class TestKeyPeopleExtractor:
    """Tests for KeyPeopleExtractor."""

    def test_passages_around_mentions(self) -> None:
        """Checks that only text near mentions of directors is kept."""
        extractor = key_people_extractor.KeyPeopleExtractor(
            None, None, None, None
        )
        text = (
            'x' * 5000
            + ' The Board of Directors comprises A and B. '
            + 'y' * 5000
        )
        passages = extractor.select_passages(text)
        assert 'Board of Directors' in passages
        assert len(passages) <= 2000
        assert extractor.select_passages('No people here.') == ''


class TestKeyPeopleRoutes:
    """Tests for the key people and Earth routes."""

    def _parts(self, tmp_path: Path) -> test_routes.RouteParts:
        """Builds the application with RELIANCE listed, a headquarters and people stored, and the postcode file present.

        Args:
            tmp_path (Path): A temporary directory from pytest.

        Returns:
            test_routes.RouteParts: The application.
        """
        parts = test_routes.RouteParts(tmp_path / 'dist', tmp_path / 'index')
        asyncio.run(
            parts.companies.upsert_listings(
                [
                    {
                        'company_key': 'INE002A01018',
                        'name': 'Reliance Industries Limited',
                        'isin': 'INE002A01018',
                        'exchange': 'nse',
                        'symbol': 'RELIANCE',
                    },
                ],
                1.0,
            )
        )
        asyncio.run(
            parts.companies.set_index_industries(
                [
                    {
                        'company_key': 'INE002A01018',
                        'name': 'Reliance Industries Limited',
                        'industry': 'Oil Gas & Consumable Fuels',
                        'symbol': 'RELIANCE',
                        'isin': 'INE002A01018',
                    },
                ],
                1.0,
            )
        )
        geonames = tmp_path / 'geonames'
        geonames.mkdir()
        (geonames / 'IN.txt').write_text(
            '\n'.join(_POSTCODE_LINES), encoding='utf-8'
        )
        parts.knowledge_parts.geocoder = postcode_geocoder.PostcodeGeocoder(
            geonames
        )
        return parts

    def _store_yahoo(self, parts: test_routes.RouteParts) -> None:
        """Stores a Yahoo result with a headquarters and one officer.

        Args:
            parts (test_routes.RouteParts): The application.
        """
        company = types.SimpleNamespace(
            company_key='INE002A01018',
            name='Reliance Industries Limited',
            symbol='RELIANCE',
            exchange='nse',
            isin='INE002A01018',
        )
        asyncio.run(
            parts.service.store(
                company,
                'yahoo',
                fetched_document.FetchResult(
                    {
                        'headquarters': {
                            'address_lines': [
                                'Maker Chambers IV',
                            ],
                            'city': 'Mumbai',
                            'postcode': '400021',
                            'country': 'India',
                        },
                        'key_people.yahoo': [
                            {
                                'name': 'Mr. Srikanth Venkatachari',
                                'role': 'Chief Financial Officer',
                            },
                        ],
                    },
                    [],
                    'stored',
                ),
            )
        )

    def test_company_has_people_headquarters_and_passage(
        self, tmp_path: Path
    ) -> None:
        """Checks the company route's key people and located headquarters, and the searchable passage.

        Args:
            tmp_path (Path): A temporary directory from pytest.
        """
        parts = self._parts(tmp_path)
        self._store_yahoo(parts)
        parts.log_in()
        body = parts.client.get(
            f'/api/knowledge/instruments/{fakes.RELIANCE_NSE_ID}'
        ).json()
        assert (
            body['key_people']['executives'][0]['name']
            == 'Srikanth Venkatachari'
        )
        assert body['headquarters']['location']['precision'] == 'postcode'
        assert body['can_read_people'] is False
        stored = str(parts.vector_store.chunks)
        assert 'Chief Financial Officer' in stored

    def test_earth_lists_placed_companies(self, tmp_path: Path) -> None:
        """Checks that the Earth route places the stored headquarters and links its share.

        Args:
            tmp_path (Path): A temporary directory from pytest.
        """
        parts = self._parts(tmp_path)
        self._store_yahoo(parts)
        parts.log_in()
        body = parts.client.get('/api/earth/companies').json()
        assert body['geocoder_ready'] is True
        assert body['index_companies'] == 1
        assert body['companies'][0]['symbol'] == 'RELIANCE'
        assert body['companies'][0]['latitude'] == 18.9263
        assert body['companies'][0]['instrument_id'] == fakes.RELIANCE_NSE_ID

    def test_extract_people_from_an_upload(self, tmp_path: Path) -> None:
        """Checks that an uploaded document's people are read with Claude and merged in.

        Args:
            tmp_path (Path): A temporary directory from pytest.
        """
        parts = self._parts(tmp_path)
        responses = FakeClaudeResponses(
            '{"people": [{"name": "Arundhati Bhattacharya", "role": "Independent Director"}]}'
        )
        client = types.SimpleNamespace(messages=responses)
        explorer_settings = types.SimpleNamespace(
            claude_model='claude-opus-5-5',
            claude_daily_token_limit=1000000,
        )
        parts.knowledge_parts.people_extractor = (
            key_people_extractor.KeyPeopleExtractor(
                client,
                parts.chat_usage,
                explorer_settings,
                fakes.FixedClock(fakes.TODAY_EPOCH),
            )
        )
        parts.log_in()
        uploaded = parts.client.post(
            f'/api/knowledge/instruments/{fakes.RELIANCE_NSE_ID}/documents',
            files={
                'file': (
                    'annual-report.txt',
                    b'Board of Directors: Arundhati Bhattacharya, Independent Director.',
                    'text/plain',
                ),
            },
            headers=_HEADERS,
        )
        assert uploaded.status_code == 200, uploaded.text
        uploaded = uploaded.json()
        body = parts.client.post(
            f'/api/knowledge/instruments/{fakes.RELIANCE_NSE_ID}/key-people/extract',
            json={
                'document_id': uploaded['document_id'],
            },
            headers=_HEADERS,
        ).json()
        assert body['found'] == 1
        assert (
            body['key_people']['board'][0]['name'] == 'Arundhati Bhattacharya'
        )
        request = responses.requests[0]
        assert request['output_config']['effort'] == 'low'
        assert request['output_config']['format']['type'] == 'json_schema'
        usage = asyncio.run(parts.chat_usage.day('2026-09-26'))
        assert usage['input_tokens'] == 900

    def test_extract_without_a_key(self, tmp_path: Path) -> None:
        """Checks that reading people without an API key answers 503.

        Args:
            tmp_path (Path): A temporary directory from pytest.
        """
        parts = self._parts(tmp_path)
        parts.log_in()
        response = parts.client.post(
            f'/api/knowledge/instruments/{fakes.RELIANCE_NSE_ID}/key-people/extract',
            json={
                'document_id': 'anything',
            },
            headers=_HEADERS,
        )
        assert response.status_code == 503

    def test_sweep_locates_index_companies(self, tmp_path: Path) -> None:
        """Checks that the sweep fetches companies without a headquarters and counts them.

        Args:
            tmp_path (Path): A temporary directory from pytest.
        """
        parts = self._parts(tmp_path)
        yahoo = fakes.FakeFetcher(
            'yahoo',
            fetched_document.FetchResult(
                {
                    'headquarters': {
                        'city': 'Mumbai',
                        'postcode': '400021',
                        'country': 'India',
                    },
                },
                [],
                'found',
            ),
        )
        announced = []
        sweep = headquarters_sweep.HeadquartersSweep(
            yahoo,
            parts.service,
            parts.companies,
            announced.append,
            fakes.FixedClock(fakes.TODAY_EPOCH),
            0.0,
        )

        async def run() -> dict[str, Any]:
            """Starts the sweep and waits for it.

            Returns:
                dict[str, Any]: The final state.
            """
            await sweep.start()
            await sweep._task
            return sweep.state

        state = asyncio.run(run())
        assert state['status'] == 'done'
        assert state['located'] == 1
        assert announced[-1]['type'] == 'locate_job'
        assert (
            asyncio.run(parts.companies.with_headquarters())[0]['symbol']
            == 'RELIANCE'
        )

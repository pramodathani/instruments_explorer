"""Tests for the knowledge pipeline: storage, text handling, fetchers, the listing, the resolver and the job runner."""

import asyncio
from pathlib import Path

import httpx
import pytest

from instruments_explorer.instruments import instrument_index
from instruments_explorer.instruments import instrument_index_builder
from instruments_explorer.instruments import instrument_index_maintainer
from instruments_explorer.knowledge import chunker
from instruments_explorer.knowledge import company_identity
from instruments_explorer.knowledge import company_resolver
from instruments_explorer.knowledge import feed_parser
from instruments_explorer.knowledge import fetch_job_runner
from instruments_explorer.knowledge import fetched_document
from instruments_explorer.knowledge import knowledge_service
from instruments_explorer.knowledge import listing_importer
from instruments_explorer.knowledge import polite_client
from instruments_explorer.knowledge import text_extractor
from instruments_explorer.knowledge.fetchers import nse_announcements
from instruments_explorer.knowledge.fetchers import rss_news
from instruments_explorer.knowledge.fetchers import screener_in
from instruments_explorer.storage import company_repository
from instruments_explorer.storage import document_repository
from instruments_explorer.storage import fetch_job_repository
from tests import fakes

_RELIANCE = company_identity.CompanyIdentity(
    'INE002A01018',
    'Reliance Industries Limited',
    'INE002A01018',
    'nse',
    'RELIANCE',
)
_RSS = """<?xml version="1.0"?>
<rss version="2.0"><channel>
<item><title>Reliance shares rise on Jio news</title><link>https://example.com/a</link>
<description>&lt;p&gt;RIL gains 2%&lt;/p&gt;</description><pubDate>Fri, 25 Sep 2026 10:00:00 GMT</pubDate></item>
<item><title>Infosys wins a contract</title><link>https://example.com/b</link><description>IT deal</description></item>
</channel></rss>"""
_SCREENER_PAGE = """<html><body>
<ul id="top-ratios">
<li><span class="name">Market Cap</span><span class="value">₹ 16,59,089 Cr.</span></li>
<li><span class="name">Stock P/E</span><span class="value">22.2</span></li>
</ul>
<div class="company-profile"><div class="about"><p>Reliance runs refineries and Jio.</p></div>
<div class="commentary">Holds 66% of Jio Platforms.</div></div>
<div class="pros"><ul><li>Strong cash flows</li></ul></div>
<div class="cons"><ul><li>Low return on equity</li></ul></div>
<section id="peers"><a href="/market/IN01/">Energy</a><a href="/market/IN01/IN0101/">Oil, Gas &amp; Consumable Fuels</a></section>
</body></html>"""


class Transport:
    """Serves prepared answers by address for httpx's mock transport.

    Attributes:
        answers: Response bodies and statuses by path.
        requests: The paths asked for, in order.
    """

    def __init__(self, answers: dict[str, tuple[int, str]]):
        """Creates the transport.

        Args:
            answers (dict[str, tuple[int, str]]): A tuple (status, body) by URL path; robots.txt paths not listed answer 404.
        """
        self.answers = answers
        self.requests = []

    def client(self, interval: float = 0.0) -> polite_client.PoliteHttpClient:
        """Builds a polite client over the prepared answers.

        Args:
            interval (float): The wait between requests to one site, in seconds.

        Returns:
            polite_client.PoliteHttpClient: The client.
        """
        http_client = httpx.AsyncClient(
            transport=httpx.MockTransport(self._answer),
        )
        return polite_client.PoliteHttpClient(
            http_client,
            'instruments_explorer',
            interval,
        )

    def _answer(self, request: httpx.Request) -> httpx.Response:
        """Answers one request.

        Args:
            request (httpx.Request): The request.

        Returns:
            httpx.Response: The prepared answer, or 404.
        """
        self.requests.append(request.url.path)
        status, body = self.answers.get(request.url.path, (404, ''))
        return httpx.Response(status, text=body)


class TestRepositories:
    """Tests for the company and document repositories over a fake database."""

    def test_merge_keeps_other_sources_fields(self) -> None:
        """Checks that merging one source never removes another's fields."""
        companies = company_repository.CompanyRepository(fakes.FakeDatabase())
        asyncio.run(companies.merge('K', {'sector': 'Energy'}, 'yahoo', 1.0))
        asyncio.run(companies.merge('K', {'pros': ['cash']}, 'screener', 2.0))
        company = asyncio.run(companies.find('K'))
        assert company['sector'] == 'Energy'
        assert company['pros'] == [
            'cash',
        ]
        assert set(company['sources']) == {
            'yahoo',
            'screener',
        }
        assert company['updated_at'] == 2.0

    def test_names_and_search(self) -> None:
        """Checks names by symbol and prefix search by name."""
        companies = company_repository.CompanyRepository(fakes.FakeDatabase())
        asyncio.run(
            companies.upsert_listings(
                [
                    {
                        'company_key': 'A',
                        'name': 'Reliance Industries Limited',
                        'symbol': 'RELIANCE',
                    },
                    {
                        'company_key': 'B',
                        'name': 'Infosys Limited',
                        'symbol': 'INFY',
                    },
                ],
                1.0,
            )
        )
        assert asyncio.run(companies.names_by_symbol()) == {
            'RELIANCE': 'Reliance Industries Limited',
            'INFY': 'Infosys Limited',
        }
        found = asyncio.run(companies.search('relia', 10))
        assert [company['symbol'] for company in found] == [
            'RELIANCE',
        ]

    def test_document_upsert_reports_new(self) -> None:
        """Checks that storing a document twice replaces it."""
        documents = document_repository.DocumentRepository(fakes.FakeDatabase())
        document = fetched_document.FetchedDocument('s', 'T', 'u', None, 'text')
        record = document.to_record('K', 1.0)
        assert asyncio.run(documents.upsert(record)) is True
        assert asyncio.run(documents.upsert(record)) is False
        assert asyncio.run(documents.count()) == 1
        listed = asyncio.run(documents.for_company('K', 10))
        assert 'text' not in listed[0]


class TestText:
    """Tests for identities, documents, chunking, extraction and feeds."""

    def test_short_name(self) -> None:
        """Checks that legal suffixes are removed."""
        assert _RELIANCE.short_name() == 'Reliance Industries'

    def test_document_id_is_stable(self) -> None:
        """Checks that the same address gives the same id, and a different source another."""
        first = fetched_document.FetchedDocument(
            'a', 'x', 'https://u', None, 'one'
        )
        again = fetched_document.FetchedDocument(
            'a', 'y', 'https://u', 1.0, 'two'
        )
        other = fetched_document.FetchedDocument(
            'b', 'x', 'https://u', None, 'one'
        )
        assert first.document_id == again.document_id
        assert first.document_id != other.document_id

    def test_chunker_overlaps_and_keeps_sentences(self) -> None:
        """Checks piece sizes and that each piece starts with the end of the previous."""
        sentence = 'The company refines oil. '
        pieces = chunker.Chunker(size=100, overlap=20).split(sentence * 20)
        assert len(pieces) > 1
        for piece in pieces:
            assert len(piece) <= 100
        assert pieces[1].startswith(pieces[0][-20:].strip()[:5])

    def test_chunker_on_empty_text(self) -> None:
        """Checks that empty text gives no pieces."""
        assert chunker.Chunker().split('  \n\n ') == []

    def test_extractor(self) -> None:
        """Checks HTML, text and an unsupported type."""
        extractor = text_extractor.TextExtractor()
        html = b'<html><script>x()</script><p>Hello</p><li>World</li></html>'
        assert extractor.extract('page.html', html) == 'Hello\n\nWorld'
        assert extractor.extract('notes.md', b'# Notes') == '# Notes'
        with pytest.raises(text_extractor.UnsupportedFileError):
            extractor.extract('sheet.xlsx', b'x')

    def test_feed_parser(self) -> None:
        """Checks RSS items, HTML removal and dates."""
        items = feed_parser.FeedParser().parse(_RSS)
        assert len(items) == 2
        assert items[0].summary == 'RIL gains 2%'
        assert items[0].published_at == 1790330400.0
        assert items[1].published_at is None

    def test_feed_parser_survives_bad_xml(self) -> None:
        """Checks that broken XML gives no items."""
        assert feed_parser.FeedParser().parse('<rss><item>') == []


class TestPoliteClient:
    """Tests for PoliteHttpClient."""

    def test_robots_disallowed(self) -> None:
        """Checks that a disallowed address is refused without being requested."""
        transport = Transport(
            {
                '/robots.txt': (
                    200,
                    'User-agent: *\nDisallow: /private',
                ),
                '/public': (
                    200,
                    'ok',
                ),
            }
        )
        client = transport.client()
        response = asyncio.run(client.get('https://site.example/public'))
        assert response.text == 'ok'
        with pytest.raises(polite_client.RobotsDisallowedError):
            asyncio.run(client.get('https://site.example/private/page'))
        assert '/private/page' not in transport.requests

    def test_robots_read_once(self) -> None:
        """Checks that robots.txt is read once per site."""
        transport = Transport({})
        client = transport.client()

        async def twice() -> None:
            """Fetches two addresses on one site."""
            await client.get('https://site.example/a')
            await client.get('https://site.example/b')

        asyncio.run(twice())
        assert transport.requests.count('/robots.txt') == 1


class TestFetchers:
    """Tests for the fetchers that read pages and feeds."""

    def test_nse_announcements(self) -> None:
        """Checks that announcements become dated documents."""
        body = '[{"desc": "Credit Rating", "attchmntText": "Rated AAA", "attchmntFile": "https://x/a.pdf", "an_dt": "25-Sep-2026 22:49:03"}]'
        transport = Transport(
            {
                '/api/corporate-announcements': (
                    200,
                    body,
                ),
            }
        )
        fetcher = nse_announcements.NseAnnouncementsFetcher(transport.client())
        result = asyncio.run(fetcher.fetch(_RELIANCE))
        document = result.documents[0]
        assert document.title == 'Credit Rating'
        assert document.text == 'Credit Rating. Rated AAA'
        assert document.published_at == 1790356743.0

    def test_screener(self) -> None:
        """Checks ratios, classification, pros, cons and the page document."""
        transport = Transport(
            {
                '/company/RELIANCE/consolidated/': (
                    200,
                    _SCREENER_PAGE,
                ),
            }
        )
        result = asyncio.run(
            screener_in.ScreenerFetcher(transport.client()).fetch(_RELIANCE)
        )
        assert result.profile['screener_ratios']['Stock P/E'] == '22.2'
        assert result.profile['classification'] == [
            'Energy',
            'Oil, Gas & Consumable Fuels',
        ]
        assert result.profile['cons'] == [
            'Low return on equity',
        ]
        assert 'Strengths: Strong cash flows' in result.documents[0].text

    def test_screener_falls_back_to_standalone(self) -> None:
        """Checks that a missing consolidated page leads to the standalone one."""
        transport = Transport(
            {
                '/company/RELIANCE/': (
                    200,
                    _SCREENER_PAGE,
                ),
            }
        )
        result = asyncio.run(
            screener_in.ScreenerFetcher(transport.client()).fetch(_RELIANCE)
        )
        assert result.documents[0].url.endswith('/company/RELIANCE/')

    def test_rss_news_matches_name_or_symbol(self) -> None:
        """Checks that only headlines mentioning the company are kept."""
        answers = {}
        for url in rss_news.FEEDS.values():
            answers[httpx.URL(url).path] = (
                200,
                _RSS,
            )
        transport = Transport(answers)
        result = asyncio.run(
            rss_news.RssNewsFetcher(transport.client()).fetch(_RELIANCE)
        )
        titles = set()
        for document in result.documents:
            titles.add(document.title.split(': ', 1)[1])
        assert titles == {
            'Reliance shares rise on Jio news',
        }


class TestListingImporter:
    """Tests for ListingImporter.parse."""

    def test_parse_strips_header_spaces(self) -> None:
        """Checks that NSE's padded headers and dates are read."""
        text = 'SYMBOL,NAME OF COMPANY, SERIES, DATE OF LISTING, PAID UP VALUE, MARKET LOT, ISIN NUMBER, FACE VALUE\nRELIANCE,Reliance Industries Limited,EQ,29-NOV-1995,10,1,INE002A01018,10\nBAD,,EQ,,,,,\n'
        importer = listing_importer.ListingImporter(
            Transport({}).client(),
            company_repository.CompanyRepository(fakes.FakeDatabase()),
            fakes.FixedClock(0.0),
        )
        listings = importer.parse(text)
        assert listings == [
            {
                'company_key': 'INE002A01018',
                'name': 'Reliance Industries Limited',
                'isin': 'INE002A01018',
                'exchange': 'nse',
                'symbol': 'RELIANCE',
                'series': 'EQ',
                'listed_on': '1995-11-29',
                'face_value': 10.0,
            },
        ]


class ResolverMaker:
    """Builds a company resolver over the made-up catalogue."""

    def build(
        self,
        directory: Path,
        listed: bool,
    ) -> company_resolver.CompanyResolver:
        """Builds the index and the resolver.

        Args:
            directory (Path): Where to build the index.
            listed (bool): Whether RELIANCE is in the imported listing.

        Returns:
            company_resolver.CompanyResolver: The resolver.
        """
        client = fakes.FakeCatalogueClient(fakes.CatalogueMaker().catalogue())
        client.additional_by_id[fakes.RELIANCE_NSE_ID] = {
            'carried_by': [
                {
                    'isin': 'INE002A01018',
                    'display_name': 'Reliance Inds',
                },
            ],
        }
        time_source = fakes.FixedClock(fakes.TODAY_EPOCH)
        maintainer = instrument_index_maintainer.InstrumentIndexMaintainer(
            client,
            instrument_index_builder.InstrumentIndexBuilder(
                client,
                directory,
                time_source,
            ),
            time_source,
        )
        asyncio.run(maintainer.refresh())
        companies = company_repository.CompanyRepository(fakes.FakeDatabase())
        if listed:
            asyncio.run(
                companies.upsert_listings(
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
        return company_resolver.CompanyResolver(maintainer, client, companies)


class TestCompanyResolver:
    """Tests for CompanyResolver."""

    def test_future_resolves_to_the_listed_company(
        self, tmp_path: Path
    ) -> None:
        """Checks that a future on a share resolves to its company.

        Args:
            tmp_path (Path): A temporary directory from pytest.
        """
        resolver = ResolverMaker().build(tmp_path, listed=True)
        company = asyncio.run(resolver.resolve('id-reliance-future'))
        assert company.company_key == 'INE002A01018'
        assert company.name == 'Reliance Industries Limited'

    def test_unlisted_share_uses_broker_attributes(
        self, tmp_path: Path
    ) -> None:
        """Checks the fallback to UBI's broker attributes.

        Args:
            tmp_path (Path): A temporary directory from pytest.
        """
        resolver = ResolverMaker().build(tmp_path, listed=False)
        company = asyncio.run(resolver.resolve(fakes.RELIANCE_NSE_ID))
        assert company.company_key == 'INE002A01018'
        assert company.name == 'Reliance Inds'

    def test_commodity_is_not_a_company(self, tmp_path: Path) -> None:
        """Checks that a gold future is refused.

        Args:
            tmp_path (Path): A temporary directory from pytest.
        """
        resolver = ResolverMaker().build(tmp_path, listed=True)
        with pytest.raises(company_resolver.NotACompanyError):
            asyncio.run(resolver.resolve('id-gold-future'))


class TestCompanyNamesInTheIndex:
    """Tests for company names in the instrument search index."""

    def test_company_name_is_searchable(self, tmp_path: Path) -> None:
        """Checks that a share and its future are found by the company's name.

        Args:
            tmp_path (Path): A temporary directory from pytest.
        """
        client = fakes.FakeCatalogueClient(fakes.CatalogueMaker().catalogue())
        builder = instrument_index_builder.InstrumentIndexBuilder(
            client,
            tmp_path,
            fakes.FixedClock(fakes.TODAY_EPOCH),
        )
        path, _ = asyncio.run(
            builder.build(
                {
                    'RELIANCE': 'Reliance Industries Limited',
                    'NIFTY': 'Should Not Be Used',
                }
            )
        )
        index = instrument_index.InstrumentIndex.open(path)
        page = index.search(instrument_index.SearchRequest(text='industries'))
        names = set()
        for result in page['results']:
            names.add(result['display_name'])
        assert names == {
            'RELIANCE',
            'RELIANCE 27 OCT 2026 FUT',
        }
        assert index.instrument(fakes.NIFTY_ID)['company_name'] is None


class TestFetchJobRunner:
    """Tests for FetchJobRunner and KnowledgeService working together."""

    def _runner(
        self,
        fetchers: list[fakes.FakeFetcher],
    ) -> tuple[fetch_job_runner.FetchJobRunner, list, fakes.FakeVectorStore]:
        """Builds a runner over fake storage.

        Args:
            fetchers (list[fakes.FakeFetcher]): The fetchers.

        Returns:
            tuple[fetch_job_runner.FetchJobRunner, list, fakes.FakeVectorStore]: A tuple (the runner, the announced messages, the vector store).
        """
        database = fakes.FakeDatabase()
        store = fakes.FakeVectorStore()
        service = knowledge_service.KnowledgeService(
            company_repository.CompanyRepository(database),
            document_repository.DocumentRepository(database),
            store,
            fakes.FixedClock(5.0),
        )
        announced = []
        runner = fetch_job_runner.FetchJobRunner(
            fetchers,
            service,
            fetch_job_repository.FetchJobRepository(database),
            announced.append,
            fakes.FixedClock(5.0),
        )
        return runner, announced, store

    def test_steps_succeed_fail_and_skip(self) -> None:
        """Checks that a failing source does not stop the others, and unavailable ones are skipped."""
        good = fakes.FakeFetcher(
            'good',
            fetched_document.FetchResult(
                {
                    'sector': 'Energy',
                },
                [
                    fetched_document.FetchedDocument(
                        'good',
                        'Profile',
                        'https://x',
                        None,
                        'Refines oil.',
                    ),
                ],
                'one document',
            ),
        )
        bad = fakes.FakeFetcher('bad', None, error=httpx.ConnectError('down'))
        off = fakes.FakeFetcher('off', None, is_available=False)
        runner, announced, store = self._runner(
            [
                bad,
                good,
                off,
            ]
        )

        async def run_one() -> dict:
            """Submits a job and runs it to the end.

            Returns:
                dict: The finished job.
            """
            task = asyncio.create_task(runner.run())
            job = await runner.submit(
                _RELIANCE,
                [
                    'bad',
                    'good',
                    'off',
                ],
                'test',
            )
            while job['status'] in ('queued', 'running'):
                await asyncio.sleep(0.01)
            task.cancel()
            return job

        job = asyncio.run(run_one())
        statuses = {}
        for step in job['steps']:
            statuses[step['source']] = step['status']
        assert statuses == {
            'bad': 'failed',
            'good': 'done',
            'off': 'skipped',
        }
        assert job['status'] == 'done'
        assert store.count() == 1
        assert announced[-1]['type'] == 'fetch_job'
        assert off.calls == []

    def test_second_submit_returns_the_active_job(self) -> None:
        """Checks that a company is not queued twice."""
        runner, _, _ = self._runner(
            [
                fakes.FakeFetcher(
                    'good',
                    fetched_document.FetchResult({}, [], ''),
                ),
            ]
        )

        async def submit_twice() -> tuple[dict, dict]:
            """Submits two jobs for the same company without running them.

            Returns:
                tuple[dict, dict]: The two answers.
            """
            first = await runner.submit(_RELIANCE, None, 'one')
            second = await runner.submit(_RELIANCE, None, 'two')
            return first, second

        first, second = asyncio.run(submit_twice())
        assert first['job_id'] == second['job_id']

    def test_unknown_source(self) -> None:
        """Checks that an unknown source key is refused."""
        runner, _, _ = self._runner([])
        with pytest.raises(ValueError, match='Unknown knowledge source'):
            asyncio.run(runner.submit(_RELIANCE, ['nope'], 'test'))

"""Reads the text out of an uploaded file.

Typical usage example:

  text = TextExtractor().extract('annual-report.pdf', data)
"""

import io

import bs4
import pypdf

MAXIMUM_PAGES = 400


class UnsupportedFileError(ValueError):
    """The file's type cannot be read."""


class TextExtractor:
    """Pulls plain text out of PDF, HTML, Markdown and text files."""

    def extract(self, filename: str, data: bytes) -> str:
        """Reads a file's text.

        Args:
            filename (str): The file's name, whose extension decides how it is read.
            data (bytes): The file's content.

        Returns:
            str: The text, with paragraphs separated by blank lines.

        Raises:
            UnsupportedFileError: The extension is not .pdf, .html, .htm, .md or .txt, or the file cannot be read.
        """
        extension = (
            filename.lower().rsplit('.', 1)[-1] if '.' in filename else ''
        )
        if extension == 'pdf':
            return self._pdf(data)
        if extension in ('html', 'htm'):
            return self.html(data.decode('utf-8', errors='replace'))
        if extension in ('md', 'txt'):
            return data.decode('utf-8', errors='replace')
        raise UnsupportedFileError(
            f'Only PDF, HTML, Markdown and text files can be read, not {filename!r}.'
        )

    def html(self, markup: str) -> str:
        """Reads the visible text of an HTML page.

        Args:
            markup (str): The HTML.

        Returns:
            str: The text of its paragraphs, headings and list items, without scripts, styles or navigation.
        """
        soup = bs4.BeautifulSoup(markup, 'html.parser')
        for element in soup(
            [
                'script',
                'style',
                'nav',
                'header',
                'footer',
                'noscript',
            ]
        ):
            element.decompose()
        blocks = []
        for element in soup.find_all(
            [
                'h1',
                'h2',
                'h3',
                'p',
                'li',
            ]
        ):
            text = element.get_text(' ', strip=True)
            if text:
                blocks.append(text)
        if not blocks:
            return soup.get_text('\n', strip=True)
        return '\n\n'.join(blocks)

    def _pdf(self, data: bytes) -> str:
        """Reads a PDF's text, page by page.

        Args:
            data (bytes): The PDF.

        Returns:
            str: The text of up to MAXIMUM_PAGES pages.

        Raises:
            UnsupportedFileError: The PDF cannot be read.
        """
        try:
            reader = pypdf.PdfReader(io.BytesIO(data))
            pages = []
            for page in reader.pages[:MAXIMUM_PAGES]:
                pages.append(page.extract_text() or '')
        except pypdf.errors.PyPdfError as error:
            raise UnsupportedFileError(
                f'The PDF could not be read: {error}'
            ) from error
        return '\n\n'.join(pages)

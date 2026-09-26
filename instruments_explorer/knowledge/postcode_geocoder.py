"""Places an Indian address on the map from its postcode, using GeoNames' postal code file, without any online lookup.

GeoNames publishes every Indian postcode with the coordinates of its area (download.geonames.org/export/zip/IN.zip). Its download site's robots.txt disallows automated downloads, so the person using the application downloads the file once into data/geonames/; this class reads either IN.zip or the IN.txt inside it. A postcode is usually placed within one or two kilometres. When the postcode is unknown, the address is placed at the centre of its city's postcodes instead.

Typical usage example:

  geocoder = PostcodeGeocoder(Path('data/geonames'))
  place = geocoder.locate('400021', 'Mumbai', 'India')
"""

import io
import re
import threading
import zipfile
from pathlib import Path
from typing import Any

DOWNLOAD_URL = 'https://download.geonames.org/export/zip/IN.zip'
TEXT_NAME = 'IN.txt'
ZIP_NAME = 'IN.zip'
CITY_ALIASES = {
    'bangalore': 'bengaluru',
    'bombay': 'mumbai',
    'madras': 'chennai',
    'calcutta': 'kolkata',
    'gurgaon': 'gurugram',
    'poona': 'pune',
    'baroda': 'vadodara',
    'mysore': 'mysuru',
    'trivandrum': 'thiruvananthapuram',
    'cochin': 'kochi',
    'new delhi': 'delhi',
}


class PostcodeGeocoder:
    """Looks up coordinates for Indian postcodes and cities from GeoNames' postal code file."""

    def __init__(self, directory: Path):
        """Remembers where the file is; it is read on first use.

        Args:
            directory (Path): The folder holding IN.zip or IN.txt.
        """
        self._directory = directory
        self._lock = threading.Lock()
        self._postcodes: dict[str, tuple[float, float, str]] | None = None
        self._cities: dict[str, tuple[float, float]] | None = None

    def available(self) -> bool:
        """Says whether the postcode file has been downloaded.

        Returns:
            bool: True when IN.txt or IN.zip is in the folder.
        """
        return (self._directory / TEXT_NAME).exists() or (
            self._directory / ZIP_NAME
        ).exists()

    def locate(
        self,
        postcode: str | None,
        city: str | None,
        country: str | None,
    ) -> dict[str, Any] | None:
        """Finds coordinates for an address.

        Args:
            postcode (str | None): The postcode, possibly with spaces, such as "56 0100".
            city (str | None): The city, used when the postcode is unknown.
            country (str | None): The country; only India is covered.

        Returns:
            dict[str, Any] | None: "latitude", "longitude", "precision" ("postcode" or "city") and "place", or None when the address cannot be placed or the file is missing.
        """
        if country and country.strip().lower() != 'india':
            return None
        if not self.available():
            return None
        self._load()
        digits = re.sub(r'\D', '', postcode or '')
        if len(digits) == 6 and self._postcodes is not None:
            found = self._postcodes.get(digits)
            if found is not None:
                return {
                    'latitude': found[0],
                    'longitude': found[1],
                    'precision': 'postcode',
                    'place': found[2],
                }
        city_key = self._city_key(city or '')
        if city_key and self._cities is not None:
            found_city = self._cities.get(city_key)
            if found_city is not None:
                return {
                    'latitude': found_city[0],
                    'longitude': found_city[1],
                    'precision': 'city',
                    'place': city,
                }
        return None

    def _load(self) -> None:
        """Reads the file once, averaging the coordinates of each postcode's places and each city's postcodes."""
        with self._lock:
            if self._postcodes is not None:
                return
            postcode_sums: dict[str, list[Any]] = {}
            city_sums: dict[str, list[float]] = {}
            for line in self._lines():
                fields = line.rstrip('\n').split('\t')
                if len(fields) < 11:
                    continue
                try:
                    latitude = float(fields[9])
                    longitude = float(fields[10])
                except ValueError:
                    continue
                code = fields[1].strip()
                entry = postcode_sums.setdefault(
                    code,
                    [
                        0.0,
                        0.0,
                        0,
                        fields[2].strip(),
                    ],
                )
                entry[0] += latitude
                entry[1] += longitude
                entry[2] += 1
                for name in (
                    fields[2],
                    fields[5],
                    fields[7],
                ):
                    key = self._city_key(name)
                    if key:
                        total = city_sums.setdefault(
                            key,
                            [
                                0.0,
                                0.0,
                                0.0,
                            ],
                        )
                        total[0] += latitude
                        total[1] += longitude
                        total[2] += 1
            postcodes = {}
            for code, entry in postcode_sums.items():
                postcodes[code] = (
                    round(entry[0] / entry[2], 5),
                    round(entry[1] / entry[2], 5),
                    entry[3],
                )
            cities = {}
            for key, total in city_sums.items():
                cities[key] = (
                    round(total[0] / total[2], 5),
                    round(total[1] / total[2], 5),
                )
            self._cities = cities
            self._postcodes = postcodes

    def _lines(self) -> list[str]:
        """Reads the file's lines from IN.txt, or from inside IN.zip.

        Returns:
            list[str]: The lines.
        """
        text_path = self._directory / TEXT_NAME
        if text_path.exists():
            return text_path.read_text(encoding='utf-8').splitlines()
        with (
            zipfile.ZipFile(self._directory / ZIP_NAME) as archive,
            archive.open(TEXT_NAME) as member,
        ):
            text = io.TextIOWrapper(member, encoding='utf-8').read()
        return text.splitlines()

    def _city_key(self, name: str) -> str:
        """Normalises a city name, mapping old names to current ones.

        Args:
            name (str): The name, such as "Bangalore" or "Mumbai City".

        Returns:
            str: A lower-case key, such as "bengaluru" or "mumbai".
        """
        key = re.sub(r'[^a-z ]', ' ', name.lower())
        key = re.sub(r'\b(city|district|urban|rural|suburban)\b', ' ', key)
        key = ' '.join(key.split())
        return CITY_ALIASES.get(key, key)

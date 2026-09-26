"""Merges the key people each source reports into one list of executives and one of board members.

Sources name people differently: Yahoo writes "Mr. Panda Madhusudana Siva Prasad", the company registry writes "MADHUSUDANA SIVAPRASAD PANDA". People are matched by the words of their names, ignoring honorifics, order, case and a space inside a name, and each merged person keeps every role and every source.

Typical usage example:

  arranged = KeyPeopleBook().arrange(company['key_people'])
  text = KeyPeopleBook().describe('Reliance Industries Limited', arranged, company.get('headquarters'))
"""

import re
from collections.abc import Mapping, Sequence
from typing import Any

HONORIFICS = {
    'mr',
    'mrs',
    'ms',
    'miss',
    'dr',
    'shri',
    'smt',
    'sri',
    'prof',
    'capt',
    'justice',
}
SOURCE_ORDER = [
    'yahoo',
    'zaubacorp',
    'upload',
]


class KeyPeopleBook:
    """Arranges key people from several sources and describes them in plain text."""

    def arrange(
        self, sources: Mapping[str, Sequence[Mapping[str, Any]]]
    ) -> dict[str, Any]:
        """Merges the sources' people and sorts them into executives and board members.

        Args:
            sources (Mapping[str, Sequence[Mapping[str, Any]]]): People per source key, each with "name" and "role", and optionally "age", "din" and "appointed_on".

        Returns:
            dict[str, Any]: "executives" and "board", each a list of people with "name", "roles" (each with "role" and "source"), "sources", and "age", "din" and "appointed_on" where known; a person with both kinds of role appears in both lists.
        """
        people: list[dict[str, Any]] = []
        for source in self._ordered_sources(sources):
            for entry in sources[source]:
                name = str(entry.get('name') or '').strip()
                role = str(entry.get('role') or '').strip()
                if not name:
                    continue
                person = self._find(people, name)
                if person is None:
                    person = {
                        'name': self._display_name(name),
                        'tokens': self._tokens(name),
                        'roles': [],
                        'sources': [],
                    }
                    people.append(person)
                if role and not self._has_role(person, role):
                    person['roles'].append(
                        {
                            'role': role,
                            'source': source,
                        }
                    )
                if source not in person['sources']:
                    person['sources'].append(source)
                for field in (
                    'age',
                    'din',
                    'appointed_on',
                ):
                    if entry.get(field) and not person.get(field):
                        person[field] = entry[field]
        executives = []
        board = []
        for person in people:
            del person['tokens']
            roles = []
            for role in person['roles']:
                roles.append(role['role'].lower())
            if self._board_rank(roles) is not None:
                board.append(person)
            if self._executive_rank(roles) is not None:
                executives.append(person)
        executives.sort(
            key=lambda person: (
                self._executive_rank(self._lowered(person)),
                person['name'],
            )
        )
        board.sort(
            key=lambda person: (
                self._board_rank(self._lowered(person)),
                person['name'],
            )
        )
        return {
            'executives': executives,
            'board': board,
        }

    def describe(
        self,
        company_name: str,
        arranged: Mapping[str, Any],
        headquarters: Mapping[str, Any] | None,
    ) -> str:
        """Writes the key people and headquarters as a short passage for semantic search.

        Args:
            company_name (str): The company's name.
            arranged (Mapping[str, Any]): The result of arrange().
            headquarters (Mapping[str, Any] | None): The stored headquarters address, or None.

        Returns:
            str: The passage.
        """
        lines = [
            f'Key people and headquarters of {company_name}.',
        ]
        if headquarters:
            address = ', '.join(
                part
                for part in [
                    *headquarters.get('address_lines', []),
                    headquarters.get('city'),
                    headquarters.get('state'),
                    headquarters.get('postcode'),
                    headquarters.get('country'),
                ]
                if part
            )
            lines.append(f'Headquarters (registered office): {address}.')
        if arranged.get('executives'):
            lines.append('Executives and key managerial personnel:')
            for person in arranged['executives']:
                lines.append(f'- {person["name"]}: {self._role_text(person)}')
        if arranged.get('board'):
            lines.append('Board of directors:')
            for person in arranged['board']:
                appointed = (
                    f', appointed {person["appointed_on"]}'
                    if person.get('appointed_on')
                    else ''
                )
                lines.append(
                    f'- {person["name"]}: {self._role_text(person)}{appointed}'
                )
        return '\n'.join(lines)

    def _ordered_sources(self, sources: Mapping[str, Any]) -> list[str]:
        """Orders source keys so Yahoo's readable names come first.

        Args:
            sources (Mapping[str, Any]): The sources.

        Returns:
            list[str]: The keys, known sources first.
        """
        ordered = []
        for key in SOURCE_ORDER:
            if key in sources:
                ordered.append(key)
        for key in sorted(sources):
            if key not in ordered:
                ordered.append(key)
        return ordered

    def _find(
        self, people: list[dict[str, Any]], name: str
    ) -> dict[str, Any] | None:
        """Finds an already listed person with the same name.

        Args:
            people (list[dict[str, Any]]): The people so far.
            name (str): The new name.

        Returns:
            dict[str, Any] | None: The matching person, or None.
        """
        tokens = self._tokens(name)
        for person in people:
            if self._same_person(tokens, person['tokens']):
                return person
        return None

    def _tokens(self, name: str) -> list[str]:
        """Splits a name into lower-case words, without honorifics or initials.

        Args:
            name (str): The name.

        Returns:
            list[str]: The words in order.
        """
        words = re.sub(r'[^a-z ]', ' ', name.lower()).split()
        kept = []
        for word in words:
            if word not in HONORIFICS and len(word) > 1:
                kept.append(word)
        return kept

    def _same_person(self, first: list[str], second: list[str]) -> bool:
        """Decides whether two names are the same person.

        Every word of the shorter name must appear in the longer one, where two neighbouring words may also be joined ("siva prasad" matches "sivaprasad") and order does not matter ("Panda Madhusudana" matches "Madhusudana Panda"). When the longer name has extra words, the first words must match too, because Indian names often share a father's name and surname: "Mukesh Ambani" is not "Anant Mukesh Ambani".

        Args:
            first (list[str]): One name's words.
            second (list[str]): The other name's words.

        Returns:
            bool: True when they look like the same person.
        """
        if not first or not second:
            return False
        shorter, longer = (
            (first, second) if len(first) <= len(second) else (second, first)
        )
        variants = [
            (shorter, longer),
        ]
        for position in range(len(shorter) - 1):
            variants.append(
                (
                    shorter[:position]
                    + [shorter[position] + shorter[position + 1]]
                    + shorter[position + 2 :],
                    longer,
                )
            )
        for position in range(len(longer) - 1):
            variants.append(
                (
                    shorter,
                    longer[:position]
                    + [longer[position] + longer[position + 1]]
                    + longer[position + 2 :],
                )
            )
        for words, other in variants:
            if not all(word in other for word in words):
                continue
            if len(words) < len(other) and words[0] != other[0]:
                continue
            return True
        return False

    def _display_name(self, name: str) -> str:
        """Makes a readable name: without honorifics and in title case when written in capitals.

        Args:
            name (str): The name as the source wrote it.

        Returns:
            str: The name to show.
        """
        words = []
        for word in name.replace('.', '. ').split():
            if word.lower().strip('.') in HONORIFICS:
                continue
            words.append(
                word.title() if word.isupper() and len(word) > 1 else word
            )
        return ' '.join(words)

    def _has_role(self, person: Mapping[str, Any], role: str) -> bool:
        """Says whether a person already has a role, ignoring case.

        Args:
            person (Mapping[str, Any]): The person.
            role (str): The role.

        Returns:
            bool: True when the same role is listed.
        """
        for existing in person['roles']:
            if existing['role'].lower() == role.lower():
                return True
        return False

    def _lowered(self, person: Mapping[str, Any]) -> list[str]:
        """Gives a person's roles in lower case.

        Args:
            person (Mapping[str, Any]): The person.

        Returns:
            list[str]: The roles.
        """
        roles = []
        for role in person['roles']:
            roles.append(role['role'].lower())
        return roles

    def _board_rank(self, roles: Sequence[str]) -> int | None:
        """Ranks a board member: chair first, then managing director or chief executive, executive directors, independent, other directors.

        Args:
            roles (Sequence[str]): The person's roles in lower case.

        Returns:
            int | None: The rank, or None when no role is a board role.
        """
        text = ' | '.join(roles)
        if 'chair' in text:
            return 0
        if not re.search(r'director|board', text):
            return None
        if re.search(r'director of |director \(?kmp', text):
            return None
        if re.search(r'managing director|\bmd\b', text):
            return 1
        if re.search(r'whole.?time|(?<!non.)(?<!non )executive director', text):
            return 2
        if 'independent' in text:
            return 3
        return 4

    def _executive_rank(self, roles: Sequence[str]) -> int | None:
        """Ranks an executive: chief executive or managing director first, then the chief financial officer, other chief officers, executive directors, the company secretary, and other senior staff.

        Args:
            roles (Sequence[str]): The person's roles in lower case.

        Returns:
            int | None: The rank, or None when every role is a board-only role.
        """
        text = ' | '.join(roles)
        if re.search(r'chief executive|\bceo\b|managing director|\bmd\b', text):
            return 0
        if re.search(r'chief financial|\bcfo\b|director of finance', text):
            return 1
        if re.search(r'\bchief\b|\bc[a-z]{1,2}o\b', text):
            return 2
        if re.search(r'whole.?time|(?<!non.)(?<!non )executive director', text):
            return 3
        if re.search(r'secretary|compliance', text):
            return 4
        if (
            re.search(r'president|head|officer|manager|executive', text)
            and 'non-executive' not in text
            and 'non executive' not in text
        ):
            return 5
        return None

    def _role_text(self, person: Mapping[str, Any]) -> str:
        """Joins a person's roles for the passage.

        Args:
            person (Mapping[str, Any]): The person.

        Returns:
            str: The roles separated by semicolons.
        """
        roles = []
        for role in person['roles']:
            roles.append(role['role'])
        return '; '.join(roles)

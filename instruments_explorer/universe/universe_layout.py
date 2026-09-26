"""Places every instrument in 3D space so the catalogue can be flown through.

The layout has three levels:

1. Each asset class is a galaxy, and the galaxies sit evenly on a large ring.
2. Inside a galaxy, each underlying (a share, index, commodity or currency pair, with all its contracts) is a cluster, placed on a sunflower spiral with the underlyings that have the most contracts nearest the middle. Each cluster takes room in proportion to its size, and the ring is made just wide enough that neighbouring galaxies do not overlap.
3. Inside a cluster, the cash instrument sits at the centre, futures on a small ring around it, and options on shells further out, one per expiry, with calls above the plane and puts below, and strikes going round the shell.

The layout is deterministic, so a point stays in the same place from one load to the next.

Typical usage example:

  points = UniverseLayout().build(records)
"""

import math
from collections.abc import Sequence
from typing import Any

GALAXY_ORDER = [
    'equity',
    'funds',
    'fixed_income',
    'currency',
    'commodity',
    'other',
]
MINIMUM_RING_RADIUS = 300.0
GALAXY_SPACING = 1.15
CLUSTER_GAP = 1.2
CLUSTER_PACKING = 1.3
CLUSTER_LABELS = 12
FUTURE_RING = 3.0
OPTION_BASE = 5.0
OPTION_STEP = 2.2
_GOLDEN_ANGLE = math.pi * (3.0 - math.sqrt(5.0))
_EXCHANGE_OFFSETS = {
    'nse': 0.0,
    'bse': 1.2,
    'mcx': 0.6,
    'ncdex': -0.6,
}
_SHAPE_CODES = {
    'security': 0,
    'future': 1,
    'option': 2,
}


class UniverseLayout:
    """Works out a position for every instrument and labels for the galaxies and biggest clusters."""

    def build(self, records: Sequence[tuple[Any, ...]]) -> dict[str, Any]:
        """Lays out the instruments.

        Args:
            records (Sequence[tuple[Any, ...]]): Rows from InstrumentIndex.universe_records.

        Returns:
            dict[str, Any]: "ids", "names", "exchanges", "shapes" (0 cash, 1 future, 2 option), "asset_classes" (positions in GALAXY_ORDER), "positions" (x, y, z per point, flattened, rounded to one decimal), "anchors" (for each point, the index of the point its spring connects it to, or -1), "galaxies" (a label, centre, count and radius per asset class), "clusters" (the same for each galaxy's twelve biggest underlyings) and "radius" (the ring's radius).
        """
        galaxies = {}
        for record in records:
            asset_class = record[2] if record[2] in GALAXY_ORDER else 'other'
            root = record[5] or record[6]
            galaxies.setdefault(asset_class, {}).setdefault(root, []).append(
                record
            )
        ids = []
        names = []
        exchanges = []
        shapes = []
        asset_classes = []
        positions = []
        anchors = []
        galaxy_labels = []
        cluster_labels = []
        placed_galaxies = []
        for asset_class in GALAXY_ORDER:
            roots = galaxies.get(asset_class)
            if roots:
                placed_galaxies.append(
                    (
                        asset_class,
                        self._place_clusters(roots),
                    )
                )
        ring_radius = self._ring_radius(placed_galaxies)
        for galaxy_position, (asset_class, placed) in enumerate(
            placed_galaxies
        ):
            angle = galaxy_position / len(placed_galaxies) * math.tau
            centre_x = math.cos(angle) * ring_radius
            centre_z = math.sin(angle) * ring_radius
            galaxy_radius = placed[-1][4] if placed else 0.0
            galaxy_labels.append(
                {
                    'label': asset_class,
                    'x': round(centre_x, 1),
                    'y': 0.0,
                    'z': round(centre_z, 1),
                    'count': sum(len(entry[1]) for entry in placed),
                    'radius': round(galaxy_radius, 1),
                }
            )
            class_position = GALAXY_ORDER.index(asset_class)
            for rank, (root, members, offsets, spot, _) in enumerate(placed):
                cluster_x = centre_x + spot[0]
                cluster_y = spot[1]
                cluster_z = centre_z + spot[2]
                if rank < CLUSTER_LABELS:
                    cluster_labels.append(
                        {
                            'label': root,
                            'x': round(cluster_x, 1),
                            'y': round(cluster_y, 1),
                            'z': round(cluster_z, 1),
                            'count': len(members),
                            'radius': round(self._extent(offsets), 1),
                        }
                    )
                first_index = len(ids)
                anchor_positions = self._anchor_positions(members)
                for record, offset, anchor in zip(
                    members,
                    offsets,
                    anchor_positions,
                    strict=True,
                ):
                    if anchor < 0:
                        anchors.append(-1)
                    else:
                        anchors.append(first_index + anchor)
                    ids.append(record[0])
                    names.append(record[6])
                    exchanges.append(record[1])
                    shapes.append(_SHAPE_CODES.get(record[3], 0))
                    asset_classes.append(class_position)
                    positions.append(round(cluster_x + offset[0], 1))
                    positions.append(round(cluster_y + offset[1], 1))
                    positions.append(round(cluster_z + offset[2], 1))
        return {
            'ids': ids,
            'names': names,
            'exchanges': exchanges,
            'shapes': shapes,
            'asset_classes': asset_classes,
            'asset_class_names': GALAXY_ORDER,
            'positions': positions,
            'anchors': anchors,
            'galaxies': galaxy_labels,
            'clusters': cluster_labels,
            'radius': round(ring_radius, 1),
        }

    def _place_clusters(
        self,
        roots: dict[str, list[tuple[Any, ...]]],
    ) -> list[tuple[str, list, list, tuple[float, float, float], float]]:
        """Places one galaxy's underlyings on a sunflower spiral, biggest first, giving each cluster room in proportion to its size.

        Each cluster's centre sits at the radius of a disc whose area is the room taken by every cluster placed before it, so large clusters push later ones outwards and small ones pack tightly.

        Args:
            roots (dict[str, list[tuple[Any, ...]]]): The galaxy's instruments by underlying.

        Returns:
            list[tuple[str, list, list, tuple[float, float, float], float]]: One (root, members, offsets, centre, radius reached so far) per underlying, biggest first, where centre is relative to the galaxy's centre.
        """
        ordered = sorted(
            roots.items(),
            key=lambda item: (-len(item[1]), item[0]),
        )
        placed = []
        used_area = 0.0
        for rank, (root, members) in enumerate(ordered):
            offsets = self._offsets(members)
            extent = self._extent(offsets) + CLUSTER_GAP
            radius = math.sqrt(used_area / math.pi)
            if rank > 0:
                radius += extent
            spiral_angle = rank * _GOLDEN_ANGLE
            height = math.sin(rank * 0.37) * min(radius * 0.06, 25.0)
            used_area += math.pi * extent * extent * CLUSTER_PACKING
            placed.append(
                (
                    root,
                    members,
                    offsets,
                    (
                        math.cos(spiral_angle) * radius,
                        height,
                        math.sin(spiral_angle) * radius,
                    ),
                    max(radius + extent, math.sqrt(used_area / math.pi)),
                )
            )
        return placed

    def _anchor_positions(self, members: list[tuple[Any, ...]]) -> list[int]:
        """Finds, for each instrument of one underlying, the instrument its spring connects it to.

        Futures and options connect to the underlying's cash instrument, preferring the NSE listing. An underlying without one, such as a commodity, connects its options to its nearest future instead. Cash instruments, and futures without a cash instrument, connect to nothing.

        Args:
            members (list[tuple[Any, ...]]): The underlying's instruments.

        Returns:
            list[int]: For each member, the position within members of the instrument it connects to, or -1.
        """
        cash = -1
        nearest_future = -1
        for position, record in enumerate(members):
            is_better_cash = cash < 0 or (
                record[1] == 'nse' and members[cash][1] != 'nse'
            )
            is_nearer_future = nearest_future < 0 or (
                record[7] is not None
                and record[7] < (members[nearest_future][7] or '')
            )
            if record[3] == 'security' and is_better_cash:
                cash = position
            elif record[3] == 'future' and record[7] and is_nearer_future:
                nearest_future = position
        anchors = []
        for position, record in enumerate(members):
            anchor = -1
            if record[3] in ('future', 'option') and cash >= 0:
                anchor = cash
            elif record[3] == 'option' and nearest_future >= 0:
                anchor = nearest_future
            if anchor == position:
                anchor = -1
            anchors.append(anchor)
        return anchors

    def _ring_radius(self, placed_galaxies: list[tuple[str, list]]) -> float:
        """Finds a ring radius at which neighbouring galaxies do not overlap.

        Args:
            placed_galaxies (list[tuple[str, list]]): Each galaxy's name and placed clusters, in ring order.

        Returns:
            float: The ring's radius.
        """
        count = len(placed_galaxies)
        if count < 2:
            return 0.0
        radii = []
        for _, placed in placed_galaxies:
            radii.append(placed[-1][4] if placed else 0.0)
        chord = 2.0 * math.sin(math.pi / count)
        needed = 0.0
        for position in range(count):
            pair = radii[position] + radii[(position + 1) % count]
            needed = max(needed, (pair * GALAXY_SPACING) / chord)
        return max(needed, MINIMUM_RING_RADIUS)

    def _extent(self, offsets: list[tuple[float, float, float]]) -> float:
        """Finds how far a cluster's furthest instrument sits from its centre.

        Args:
            offsets (list[tuple[float, float, float]]): The cluster's offsets.

        Returns:
            float: The largest horizontal distance, at least 1.
        """
        furthest = 1.0
        for offset in offsets:
            furthest = max(furthest, math.hypot(offset[0], offset[2]))
        return furthest

    def _offsets(
        self, members: list[tuple[Any, ...]]
    ) -> list[tuple[float, float, float]]:
        """Places one underlying's instruments around its centre.

        Args:
            members (list[tuple[Any, ...]]): The underlying's instruments.

        Returns:
            list[tuple[float, float, float]]: An (x, y, z) offset per member, in the members' order.
        """
        futures = sorted(
            {
                record[7]
                for record in members
                if record[3] == 'future' and record[7]
            }
        )
        expiries = sorted(
            {
                record[7]
                for record in members
                if record[3] == 'option' and record[7]
            }
        )
        strikes_by_expiry = {}
        for record in members:
            if record[3] == 'option' and record[7]:
                strikes_by_expiry.setdefault(record[7], set()).add(
                    record[8] or 0.0
                )
        strike_positions = {}
        for expiry, strikes in strikes_by_expiry.items():
            ordered = sorted(strikes)
            for position, strike in enumerate(ordered):
                strike_positions[(expiry, strike)] = position / max(
                    len(ordered), 1
                )
        offsets = []
        securities = 0
        for record in members:
            shape = record[3]
            exchange_shift = _EXCHANGE_OFFSETS.get(record[1], 0.0)
            if shape == 'future' and record[7] in futures:
                angle = (
                    futures.index(record[7]) / max(len(futures), 1) * math.tau
                )
                offsets.append(
                    (
                        math.cos(angle) * FUTURE_RING,
                        exchange_shift * 0.5,
                        math.sin(angle) * FUTURE_RING,
                    )
                )
            elif shape == 'option' and record[7] in strikes_by_expiry:
                shell = OPTION_BASE + expiries.index(record[7]) * OPTION_STEP
                angle = (
                    strike_positions[(record[7], record[8] or 0.0)] * math.tau
                )
                lift = 1.2 if record[9] == 'CE' else -1.2
                offsets.append(
                    (
                        math.cos(angle) * shell,
                        lift + exchange_shift * 0.3,
                        math.sin(angle) * shell,
                    )
                )
            else:
                offsets.append(
                    (
                        securities * 0.6,
                        exchange_shift,
                        0.0,
                    )
                )
                securities += 1
        return offsets

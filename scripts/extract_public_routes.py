#!/usr/bin/env python3

"""Extract normalized community routes from the DHA workbooks."""

import argparse
import re
import sys
import xml.etree.ElementTree as ElementTree
from collections import Counter
from pathlib import Path
from zipfile import ZipFile


REPOSITORY = Path(__file__).resolve().parents[1]
if str(REPOSITORY) not in sys.path:
    sys.path.insert(0, str(REPOSITORY))

from src.data import get_version_data
from src.routes import RouteAction, RoutePlan, write_route


SPREADSHEET_NAMESPACE = "{http://schemas.openxmlformats.org/spreadsheetml/2006/main}"
RELATIONSHIP_ID = (
    "{http://schemas.openxmlformats.org/officeDocument/2006/relationships}id"
)

BUILDING_TOKENS = {
    "Cursor": "Cursor",
    "Grandma": "Grandma",
    "Farm": "Farm",
    "Mine": "Mine",
    "Factory": "Factory",
    "Shipment": "Shipment",
    "Alchemy": "Alchemy Lab",
    "Portal": "Portal",
    "Time": "Time Machine",
    "Time_Machine": "Time Machine",
    "Antimatter": "Antimatter Condenser",
    "Prism": "Prism",
}

UPGRADE_TOKENS = {
    "Cursor_up": "Cursor",
    "Grandma_up": "Grandma",
    "Farm_up": "Farm",
    "Mine_up": "Mine",
    "Factory_up": "Factory",
    "Shipment_up": "Shipment",
    "Alchemy_up": "Alchemy Lab",
    "Portal_up": "Portal",
    "Time_up": "Time Machine",
    "Antimatter_up": "Antimatter Condenser",
    "Prism_up": "Prism",
    "Plastic_up": "Mouse",
    "Super_up": "Grandma synergy",
    "Cookies_up": "Cookie",
}

ONLINE_ROUTE_ALGORITHM = "singleton_errands"
ONLINE_ERRAND_DURATION = 1.0
ONLINE_PURCHASE_CLICK_RATE = 5.0


def _shared_strings(archive):
    path = "xl/sharedStrings.xml"
    if path not in archive.namelist():
        return []
    root = ElementTree.fromstring(archive.read(path))
    return [
        "".join(text.text or "" for text in item.iter(SPREADSHEET_NAMESPACE + "t"))
        for item in root.findall(SPREADSHEET_NAMESPACE + "si")
    ]


def _route_rows(path):
    with ZipFile(path) as archive:
        shared_strings = _shared_strings(archive)
        workbook = ElementTree.fromstring(archive.read("xl/workbook.xml"))
        relationships = ElementTree.fromstring(
            archive.read("xl/_rels/workbook.xml.rels")
        )
        targets = {
            relationship.attrib["Id"]: relationship.attrib["Target"]
            for relationship in relationships
        }
        sheets = workbook.find(SPREADSHEET_NAMESPACE + "sheets")
        route_sheet = next(
            sheet for sheet in sheets if sheet.attrib["name"] == "Routes"
        )
        sheet_path = "xl/" + targets[route_sheet.attrib[RELATIONSHIP_ID]]
        sheet = ElementTree.fromstring(archive.read(sheet_path))

        for row in sheet.iter(SPREADSHEET_NAMESPACE + "row"):
            values = {}
            for cell in row.findall(SPREADSHEET_NAMESPACE + "c"):
                value = cell.find(SPREADSHEET_NAMESPACE + "v")
                if value is None:
                    continue
                column = "".join(
                    character
                    for character in cell.attrib["r"]
                    if character.isalpha()
                )
                values[column] = (
                    shared_strings[int(value.text)]
                    if cell.attrib.get("t") == "s"
                    else value.text
                )
            if "B" in values and row.attrib["r"] != "1":
                yield int(row.attrib["r"]), values


def _workbook_settings(path):
    name = path.name
    if "Neverclick" in name:
        return "neverclick", "2.031", 1_000_000, "neverclick"
    if "Hardcore" in name:
        return "hardcore", "1.0466", 1_000_000_000, "fresh"
    if "Heavenly Chip" in name:
        return "heavenly_chip", "1.0466", 1_000_000_000_000, "fresh"
    return "one_million", "2.031", 1_000_000, "fresh"


def _click_rate(category, initial_state):
    if initial_state == "neverclick":
        return 0.0
    match = re.search(r"(\d+)\s*cps", category or "", re.IGNORECASE)
    if not match:
        raise ValueError(f"Could not determine click rate from category: {category}")
    return float(match.group(1))


def _normalize_actions(raw_route, initial_state, version):
    spreadsheet_upgrade_families = (
        get_version_data(version).SPREADSHEET_UPGRADE_FAMILIES
    )
    tiers = Counter()
    actions = []
    skipped_initial_cursor = initial_state != "neverclick"

    for token in (line.strip() for line in raw_route.splitlines()):
        if not token or token == "Start":
            continue
        if token in BUILDING_TOKENS:
            building = BUILDING_TOKENS[token]
            if not skipped_initial_cursor and building == "Cursor":
                skipped_initial_cursor = True
                continue
            actions.append(RouteAction("buy", building))
            continue
        if token.startswith("Sell_") and token[5:] in BUILDING_TOKENS:
            actions.append(RouteAction("sell", BUILDING_TOKENS[token[5:]]))
            continue
        if token in UPGRADE_TOKENS:
            family = UPGRADE_TOKENS[token]
            tiers[family] += 1
            try:
                upgrade_name = spreadsheet_upgrade_families[family][
                    tiers[family] - 1
                ]
            except (KeyError, IndexError) as error:
                raise ValueError(
                    f"Unknown {version} spreadsheet upgrade: "
                    f"{family} tier {tiers[family]}"
                ) from error
            actions.append(RouteAction("upgrade", upgrade_name))

    return actions


def _slug(value):
    return re.sub(r"[^a-z0-9]+", "_", value.lower()).strip("_") or "unknown"


def extract_routes(spreadsheet_directory, output_directory):
    spreadsheet_directory = Path(spreadsheet_directory)
    output_directory = Path(output_directory)
    output_directory.mkdir(parents=True, exist_ok=True)
    written = []
    sources_by_destination = {}

    for workbook in sorted(spreadsheet_directory.glob("*.xlsx")):
        category_name, version, target, initial_state = (
            _workbook_settings(workbook)
        )
        for row_number, values in _route_rows(workbook):
            actions = _normalize_actions(
                values["B"],
                initial_state,
                version,
            )
            if len(actions) < 5:
                continue

            author = values.get("C") or "unknown"
            click_category = values.get("D") or "Neverclick"
            click_rate = _click_rate(click_category, initial_state)
            filename = (
                f"{category_name}_{_slug(click_category)}_"
                f"{_slug(author)}.route"
            )
            destination = output_directory / filename
            source = (
                f"dha spreadsheet: {category_name.replace('_', ' ')} "
                f"row {row_number}"
            )
            if destination in sources_by_destination:
                previous_source = sources_by_destination[destination]
                raise ValueError(
                    f"Route filename collision for {destination.name}: "
                    f"{previous_source} and {source}"
                )
            sources_by_destination[destination] = source
            route_name = f"{category_name}: {author} ({click_category})"
            plan = RoutePlan(
                name=route_name,
                source=source,
                version=version,
                target=target,
                click_rate=click_rate,
                initial_state=initial_state,
                algorithm=ONLINE_ROUTE_ALGORITHM,
                errand_duration=ONLINE_ERRAND_DURATION,
                purchase_click_rate=ONLINE_PURCHASE_CLICK_RATE,
                upgrades_enabled=category_name != "hardcore",
                errands_enabled=False,
                errands=tuple((action,) for action in actions),
            )
            write_route(
                destination,
                plan,
                comment="Extracted from the workbook's hidden Routes sheet.",
                explicit_errands=False,
                overwrite=True,
            )
            written.append(destination)

    return written


def main(argv=None):
    parser = argparse.ArgumentParser(description="Extract normalized online routes")
    parser.add_argument(
        "--source",
        default=REPOSITORY / "routes" / "dha_spreadsheets",
    )
    parser.add_argument(
        "--output",
        default=REPOSITORY / "routes" / "from_online" / "singletons",
    )
    args = parser.parse_args(argv)

    for path in extract_routes(args.source, args.output):
        print(path)


if __name__ == "__main__":
    main()

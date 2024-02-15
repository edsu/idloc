#!/usr/bin/env python3

"""
A small library and CLI to get the JSON-LD objects from the id.loc.gov service.
"""

import json
import sys
import time
from typing import List
from xml.etree import ElementTree

import click
import requests
from bs4 import BeautifulSoup
from pyld import jsonld

# cli


@click.group()
def cli() -> None:
    pass


@cli.command("get", help="Get an id.loc.gov entity by URI and print out JSON-LD")
@click.argument("uri", required=True)
def get_command(uri: str) -> None:
    uri = uri.replace("https://", "http://")
    data = get(uri)
    print(json.dumps(data, indent=2))


@cli.command("lucky", help="Return the first matching entity as JSON-LD")
@click.option(
    "--concept-scheme",
    "concept_schemes",
    multiple=True,
    help="A concept scheme to limit to (can repeat)",
)
@click.argument("query", required=True)
def lucky_command(query, concept_schemes):
    check_concept_schemes(concept_schemes, exit=True)
    try:
        result = next(search(query, concept_schemes))
        print(json.dumps(get(result["uri"]), indent=2))
    except StopIteration:
        print(f'Alas, there was no match found for "{query}"')


@cli.command("search", help="Search for entities in id.loc.gov")
@click.option(
    "--concept-scheme",
    "concept_schemes",
    multiple=True,
    help="A concept scheme to limit to (can repeat)",
)
@click.option(
    "--limit",
    type=int,
    default=20,
    help="Number of records to limit results to (0 is all)",
)
@click.argument("query", required=True)
def search_command(query: str, limit: int = 0, concept_schemes: List[str] = []) -> None:
    check_concept_schemes(concept_schemes, exit=True)
    count = 0
    for result in search(query, concept_schemes, limit):
        count += 1
        print(f"{result['title']}\n<{result['uri']}>\n")


@cli.command(
    "concept-schemes", help="list available concept scheme names and their URIs"
)
def concept_schemes_command() -> None:
    for schema_name, schema_id in CONCEPT_SCHEMES.items():
        print(f"{schema_name}: <{schema_id}>")


@cli.command(
    "guess",
    help="Return the first entity when searching for a particular word or phrase",
)
@click.option(
    "--concept-scheme",
    "concept_schemes",
    multiple=True,
    help="A concept scheme to limit to (can repeat)",
)
@click.argument("query", required=True)
def guess(query: str, concept_scheme: List[str]) -> None:
    check_concept_schemes(concept_schemes, exit=True)
    result = next(search(query, concept_scheme))
    if result:
        print(result["uri"])


# library functions


def get(uri: str) -> dict:
    """
    Lookup the given string as an exact match in id.loc.gov and return it as a
    JSON-LD object.
    """
    doc = requests.get(uri, headers={"Accept": "application/ld+json"}).json()

    # use this context to parse the JSONLD into something more usable
    context = {
        "mads": "http://www.loc.gov/mads/rdf/v1#",
        "skos": "http://www.w3.org/2004/02/skos/core#",
        "skosxl": "http://www.w3.org/2008/05/skos-xl#",
        "recordinfo": "http://id.loc.gov/ontologies/RecordInfo#",
        "identifiers": "http://id.loc.gov/vocabulary/identifiers/",
        "bflc": "http://id.loc.gov/ontologies/bflc/",
        "iso6392": "http://id.loc.gov/vocabulary/iso639-2/",
        "changeset": "http://purl.org/vocab/changeset/schema#",
        "bibframe": "http://id.loc.gov/ontologies/bibframe/",
    }

    return jsonld.frame(
        doc,
        {
            "@context": context,
            "@id": uri,
            # so we get linked SKOS Concepts in addition to linked MADS Authorities
            "@embed": "@always",
        },
    )


def search(q: str, concept_schemes: List[str] = [], limit=0, sleep=1) -> List:
    """
    Searches the id.loc.gov site for a given query. The result is a generator
    that will page through all results. So you may want to provide a limit to
    stop at a particular point. By default all results will be returned.

    You can optionally pass in one or more concept scheme names. To see what
    valid names are use the mapping in idloc.CONCEPT_SCHEMES (there are quite
    a few!). By default all will be searched.

    The sleep parameter is there to prevent rapid repeated querying. It is the
    number of seconds to sleep between requests for the next set of results.
    """
    # convert the concept scheme name to its equivalent uri
    concept_scheme_ids = check_concept_schemes(concept_schemes)

    # sadly the "json" format is some incomprehensible conversion of the xml
    params = {"format": "atom", "q": [q]}

    # add any relevant concept scheme uris to the query if specified
    for cs in concept_scheme_ids:
        params["q"].append(f"cs:{cs}")

    next_url = None
    count = 0
    while limit == 0 or count < limit:
        if next_url is None:
            resp = requests.get("https://id.loc.gov/search/", params)
        else:
            resp = requests.get(next_url)

        resp.raise_for_status()

        doc = ElementTree.fromstring(resp.content)
        ns = {"atom": "http://www.w3.org/2005/Atom"}

        for entry in doc.findall("atom:entry", ns):
            yield {
                "title": entry.find("atom:title", ns).text,
                "uri": entry.find("atom:link", ns).attrib["href"],
            }
            count += 1
            if limit != 0 and count >= limit:
                break

        # if there's a link to the next set of results use it
        link = doc.find("atom:link[@rel='next']", ns)
        if link is None:
            break
        else:
            next_url = link.attrib["href"]

        if sleep != 0:
            time.sleep(sleep)


def concept_schemes() -> dict:
    """
    Fetches a mapping of concept scheme names to their respective identifiers from the
    search form at https://id.loc.gov/search.
    """
    resp = requests.get("https://id.loc.gov/search/")
    resp.raise_for_status()
    html = BeautifulSoup(resp.content, "html.parser")

    # concept schemes are the first facet box
    facets = html.select_one(".facet-box")

    schemes = {}
    for a in facets.select("li a"):
        scheme_id = a["href"].replace("?q=", "")
        scheme_name = (
            a.select_one("span")
            .text.lower()
            .replace(" ", "-")
            .replace("/", "-")
            .replace("---", "-")
        )

        # ignore empty facets
        if scheme_name == "":
            continue

        # ignore the concept scheme if we've already seen on with the same name
        # currently only "preservation-level"
        if scheme_name in schemes:
            continue

        schemes[scheme_name] = scheme_id

    return schemes


def check_concept_schemes(names: List[str], exit: bool = False) -> List[str]:
    ids = [CONCEPT_SCHEMES.get(name) for name in names]
    ids = list(filter(lambda id: id is not None, ids))

    missing = list(filter(lambda name: name not in CONCEPT_SCHEMES, names))
    msg = f"Concept scheme name(s) don't exist: {', '.join(missing)}"

    if len(missing) > 0:
        if exit:
            sys.exit(msg)
        else:
            raise Exception(msg)

    return ids


CONCEPT_SCHEMES = {
    "bibframe-instances": "http://id.loc.gov/resources/instances",
    "bibframe-works": "http://id.loc.gov/resources/works",
    "name-authority": "http://id.loc.gov/authorities/names",
    "lc-classification": "http://id.loc.gov/authorities/classification",
    "bibframe-hubs": "http://id.loc.gov/resources/hubs",
    "providers": "http://id.loc.gov/entities/providers",
    "subject-headings": "http://id.loc.gov/authorities/subjects",
    "cultural-heritage-orgs": "http://id.loc.gov/vocabulary/organizations",
    "ethnographic-thesaurus": "http://id.loc.gov/vocabulary/ethnographicTerms",
    "children's-subject-headings": "http://id.loc.gov/authorities/childrensSubjects",
    "thesaurus-graphic-materials": "http://id.loc.gov/vocabulary/graphicMaterials",
    "genre-form-terms": "http://id.loc.gov/authorities/genreForms",
    "roles": "http://id.loc.gov/entities/roles",
    "relationships": "http://id.loc.gov/entities/relationships",
    "demographic-groups": "http://id.loc.gov/authorities/demographicTerms",
    "rbms-controlled-vocabulary": "http://id.loc.gov/vocabulary/rbmscv",
    "music-medium-of-performance": "http://id.loc.gov/authorities/performanceMediums",
    "demographics-occupational": "http://id.loc.gov/authorities/demographicTerms/occ",
    "demographics-nationality": "http://id.loc.gov/authorities/demographicTerms/nat",
    "marc-geographic-areas": "http://id.loc.gov/vocabulary/geographicAreas",
    "iso639-2-languages": "http://id.loc.gov/vocabulary/iso639-2",
    "marc-languages": "http://id.loc.gov/vocabulary/languages",
    "subject-schemes": "http://id.loc.gov/vocabulary/subjectSchemes",
    "classification-schemes": "http://id.loc.gov/vocabulary/classSchemes",
    "marc-countries": "http://id.loc.gov/vocabulary/countries",
    "demographics-social": "http://id.loc.gov/authorities/demographicTerms/soc",
    "relators": "http://id.loc.gov/vocabulary/relators",
    "demographics-cultural": "http://id.loc.gov/authorities/demographicTerms/eth",
    "standard-identifiers": "http://id.loc.gov/vocabulary/identifiers",
    "iso639-1-languages": "http://id.loc.gov/vocabulary/iso639-1",
    "relationship": "http://id.loc.gov/vocabulary/relationship",
    "demographics-language": "http://id.loc.gov/authorities/demographicTerms/lng",
    "genre-form-schemes": "http://id.loc.gov/vocabulary/genreFormSchemes",
    "iso639-5-languages": "http://id.loc.gov/vocabulary/iso639-5",
    "marc-genre-terms": "http://id.loc.gov/vocabulary/marcgt",
    "demographics-religion": "http://id.loc.gov/authorities/demographicTerms/rel",
    "rbms-relationship-designators": "http://id.loc.gov/vocabulary/rbmsrel",
    "description-conventions": "http://id.loc.gov/vocabulary/descriptionConventions",
    "authentication-action": "http://id.loc.gov/vocabulary/marcauthen",
    "carriers": "http://id.loc.gov/vocabulary/carriers",
    "national-bibliography-number-source-codes": (
        "http://id.loc.gov/vocabulary/nationalbibschemes"
    ),
    "support-material": "http://id.loc.gov/vocabulary/mmaterial",
    "event-type": "http://id.loc.gov/vocabulary/preservation/eventType",
    "demographics-medical": "http://id.loc.gov/authorities/demographicTerms/mpd",
    "projection": "http://id.loc.gov/vocabulary/mprojection",
    "demographics-education": "http://id.loc.gov/authorities/demographicTerms/edu",
    "name-and-title-authority-source-codes": (
        "http://id.loc.gov/vocabulary/nameTitleSchemes"
    ),
    "resource-types-scheme": "http://id.loc.gov/vocabulary/resourceTypes",
    "note-type": "http://id.loc.gov/vocabulary/mnotetype",
    "relationship-subtype": (
        "http://id.loc.gov/vocabulary/preservation/relationshipSubType"
    ),
    "content-types": "http://id.loc.gov/vocabulary/contentTypes",
    "playback-characteristics": "http://id.loc.gov/vocabulary/mspecplayback",
    "encoding-format": "http://id.loc.gov/vocabulary/mencformat",
    "generation": "http://id.loc.gov/vocabulary/mgeneration",
    "production-method": "http://id.loc.gov/vocabulary/mproduction",
    "status-codes": "http://id.loc.gov/vocabulary/mstatus",
    "publication-frequencies": "http://id.loc.gov/vocabulary/frequencies",
    "layout": "http://id.loc.gov/vocabulary/mlayout",
    "video-format": "http://id.loc.gov/vocabulary/mvidformat",
    "environment-type": (
        "http://id.loc.gov/vocabulary/preservation/environmentFunctionType"
    ),
    "resource-components": "http://id.loc.gov/vocabulary/resourceComponents",
    "demographics-age": "http://id.loc.gov/authorities/demographicTerms/age",
    "book-format": "http://id.loc.gov/vocabulary/bookformat",
    "illustrative-content": "http://id.loc.gov/vocabulary/millus",
    "regional-encoding": "http://id.loc.gov/vocabulary/mregencoding",
    "supplementary-content": "http://id.loc.gov/vocabulary/msupplcont",
    "playing-speed": "http://id.loc.gov/vocabulary/mplayspeed",
    "notated-music-form": "http://id.loc.gov/vocabulary/mmusicformat",
    "cryptographic": (
        "http://id.loc.gov/vocabulary/preservation/cryptographicHashFunctions"
    ),
    "media-types": "http://id.loc.gov/vocabulary/mediaTypes",
    "presentation-format": "http://id.loc.gov/vocabulary/mpresformat",
    "script": "http://id.loc.gov/vocabulary/mscript",
    "serial-publication-type": "http://id.loc.gov/vocabulary/mserialpubtype",
    "language-code-and-term-source-codes": (
        "http://id.loc.gov/vocabulary/languageschemes"
    ),
    "relief": "http://id.loc.gov/vocabulary/mrelief",
    "music-notation": "http://id.loc.gov/vocabulary/mmusnotation",
    "aspect-ratio": "http://id.loc.gov/vocabulary/maspect",
    "intended-audience": "http://id.loc.gov/vocabulary/maudience",
    "government-publication-type": "http://id.loc.gov/vocabulary/mgovtpubtype",
    "content-location": "http://id.loc.gov/vocabulary/preservation/contentLocationType",
    "encoding-level": "http://id.loc.gov/vocabulary/menclvl",
    "tactile-notation": "http://id.loc.gov/vocabulary/mtactile",
    "musical-instrumentation-and-voice-code-source-codes": (
        "http://id.loc.gov/vocabulary/musiccodeschemes"
    ),
    "color-content": "http://id.loc.gov/vocabulary/mcolor",
    "file-type": "http://id.loc.gov/vocabulary/mfiletype",
    "groove-width-pitch-cutting": "http://id.loc.gov/vocabulary/mgroove",
    "scale": "http://id.loc.gov/vocabulary/mscale",
    "tape-configuration": "http://id.loc.gov/vocabulary/mtapeconfig",
    "actions-granted": "http://id.loc.gov/vocabulary/preservation/actionsGranted",
    "relationship-type": "http://id.loc.gov/vocabulary/preservation/relationshipType",
    "code-datatypes": "http://id.loc.gov/datatypes/codes",
    "sound-capture-and-storage": "http://id.loc.gov/vocabulary/mcapturestorage",
    "reduction-ratio": "http://id.loc.gov/vocabulary/mreductionratio",
    "environment-purpose": (
        "http://id.loc.gov/vocabulary/preservation/environmentPurpose"
    ),
    "linking-agent-role-event": (
        "http://id.loc.gov/vocabulary/preservation/linkingAgentRoleEvent"
    ),
    "rights-basis": "http://id.loc.gov/vocabulary/preservation/rightsBasis",
    "extended-date-time-format-datatypes-scheme": (
        "http://id.loc.gov/datatypes/EDTFScheme"
    ),
    "identifier-datatypes": "http://id.loc.gov/datatypes/identifiers",
    "issuance": "http://id.loc.gov/vocabulary/issuance",
    "broadcast-standard": "http://id.loc.gov/vocabulary/mbroadstd",
    "playback": "http://id.loc.gov/vocabulary/mplayback",
    "technique": "http://id.loc.gov/vocabulary/mtechnique",
    "agent-type": "http://id.loc.gov/vocabulary/preservation/agentType",
    "environment-characteristic": (
        "http://id.loc.gov/vocabulary/preservation/environmentCharacteristic"
    ),
    "environment-registry": (
        "http://id.loc.gov/vocabulary/preservation/environmentRegistryRole"
    ),
    "event-related-agent": (
        "http://id.loc.gov/vocabulary/preservation/eventRelatedAgentRole"
    ),
    "hardware-type": "http://id.loc.gov/vocabulary/preservation/hardwareType",
    "inhibitor-type": "http://id.loc.gov/vocabulary/preservation/inhibitorType",
    "object-category": "http://id.loc.gov/vocabulary/preservation/objectCategory",
    "rights-related-agent": (
        "http://id.loc.gov/vocabulary/preservation/rightsRelatedAgentRole"
    ),
    "software-type": "http://id.loc.gov/vocabulary/preservation/softwareType",
    "font-sizes": "http://id.loc.gov/entities/fontsizes",
    "font-size": "http://id.loc.gov/vocabulary/mfont",
    "polarity": "http://id.loc.gov/vocabulary/mpolarity",
    "recording-medium": "http://id.loc.gov/vocabulary/mrecmedium",
    "copyright": "http://id.loc.gov/vocabulary/preservation/copyrightStatus",
    "event-outcome": "http://id.loc.gov/vocabulary/preservation/eventOutcome",
    "inhibitor-target": "http://id.loc.gov/vocabulary/preservation/inhibitorTarget",
    "linking-environment": (
        "http://id.loc.gov/vocabulary/preservation/linkingEnvironmentRole"
    ),
    "preservation-level": (
        "http://id.loc.gov/vocabulary/preservation/preservationLevelRole"
    ),
    "storage-medium": "http://id.loc.gov/vocabulary/preservation/storageMedium",
    "fingerprint-scheme-source-codes": (
        "http://id.loc.gov/vocabulary/fingerprintschemes"
    ),
    "musical-composition-form-code-source-codes": "http://id.loc.gov/vocabulary/mcfcsc",
    "recording-type": "http://id.loc.gov/vocabulary/mrectype",
    "sound-content": "http://id.loc.gov/vocabulary/msoundcontent",
    "event-related-object": (
        "http://id.loc.gov/vocabulary/preservation/eventRelatedObjectRole"
    ),
    "format-registry": "http://id.loc.gov/vocabulary/preservation/formatRegistryRole",
    "signature-encoding": "http://id.loc.gov/vocabulary/preservation/signatureEncoding",
    "signature-method": "http://id.loc.gov/vocabulary/preservation/signatureMethod",
    "accessibility-content-source-codes": (
        "http://id.loc.gov/vocabulary/accesscontentschemes"
    ),
}

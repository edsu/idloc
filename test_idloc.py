import idloc
import pytest


def test_search() -> None:
    results = list(idloc.search("Food", limit=50))
    assert len(results) == 50


def test_get() -> None:
    subject = idloc.get("http://id.loc.gov/authorities/subjects/sh85050184")
    assert subject["skos:prefLabel"]["@value"] == "Food"


def test_rdfs_curie() -> None:
    work = idloc.get("http://id.loc.gov/resources/works/988230")
    assert (
        work["bibframe:tableOfContents"]["rdfs:label"]
        == "Rocket power / Richard Poirier -- The ritual of military memory / Paul Fussell -- Gravity's encyclopedia / Edward Mendelson -- Paranoia, Pynchon, and preterition / Louis Mackey --Gravity's rainbow / Tony Tanner -- Recognizing reality, realizing responsibility / Craig Hansen Werner -- Creative paranoia and frost patterns of white words / Gabriele Schwab."
    )


def test_concept_schemes() -> None:
    schemes = idloc.concept_schemes()
    assert len(schemes) > 0
    assert schemes["bibframe-instances"] == "cs:http://id.loc.gov/resources/instances"
    assert schemes["genre-form-terms"] == "cs:http://id.loc.gov/authorities/genreForms"


def test_check_concept_schemes() -> None:
    assert idloc.check_concept_schemes(["name-authority", "subject-headings"]) == [
        "http://id.loc.gov/authorities/names",
        "http://id.loc.gov/authorities/subjects",
    ]

    with pytest.raises(Exception):
        idloc.check_concept_schemes(["foo"])

import locid
import pytest


def test_search() -> None:
    results = list(locid.search("Food", limit=50))
    assert len(results) == 50


def test_get() -> None:
    subject = locid.locid('http://id.loc.gov/authorities/subjects/sh85050184')
    assert subject["skos:prefLabel"]["@value"] == "Food"


def test_concept_schemes() -> None:
    schemes = locid.concept_schemes()
    assert len(schemes) > 0
    assert schemes['bibframe-instances'] == 'cs:http://id.loc.gov/resources/instances'
    assert schemes['genre-form-terms'] == 'cs:http://id.loc.gov/authorities/genreForms'
    assert schemes['demographics-age'] == 'cs:http://id.loc.gov/authorities/demographicTerms/age'


def test_check_concept_schemes() -> None:
    assert (
        locid.check_concept_schemes(['name-authority', 'subject-headings'])

        ==

        [
            'http://id.loc.gov/authorities/names',
            'http://id.loc.gov/authorities/subjects'
        ]
    )

    with pytest.raises(Exception):
        locid.check_concept_schemes(['foo'])

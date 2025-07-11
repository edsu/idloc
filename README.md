# idloc 

[![Build Status](https://github.com/edsu/idloc/actions/workflows/test.yml/badge.svg)](https://github.com/edsu/idloc/actions/workflows/test.yml)


*idloc* is a command line utility and small function library for getting JSON-LD from the Library of Congress Linked Data service at https://id.loc.gov.

Ideally *idloc* would not be needed at all because you could just use [curl](https://curl.se/) or whatever HTTP library you want to fetch the JSON-LD directly. But at the moment the JSON-LD that is returned, while valid, isn't exactly usable and needs to be [framed](https://www.w3.org/TR/json-ld11-framing/). *idloc* uses [pyld] internally to do the framing that makes the JSON usable by someone who just wants to use the data as JSON without the cognitive overhead of using RDF processing tools.

## Install

This will install *idloc* and its dependencies:

```bash
pip install idloc
```

## CLI

Once installed you should also have a *idloc* command line utility available. There are four commands get, lucky, search, concept-schemes.

### Get

Get will fetch the id.loc.gov entity by URI and print out the framed JSON-LD:

```bash
$ idloc get https://id.loc.gov/authorities/subjects/sh2002000569
```

To see the output of this command see [this file](https://raw.githubusercontent.com/edsu/idloc/refs/heads/main/examples/sh2002000569.json) since it's really too long to include inline here in the docs.

Compare that to the JSON that is being made available at https://id.loc.gov/authorities/subjects/sh85021262.json and you will probably see why *framing* the JSON-LD is currently needed if you want to work with the data as JSON.

### Lucky

If you want to roll the dice and see the JSON-LD for first entity that matches a given string:

```
$ idloc lucky "Semantic Web"
```

If you want to limit to particular concept schemes like `subject-headings` you can:

```
$idloc lucky --concept-scheme subject-headings "Semantic Web"
```

### Search

You can search for entities:

```
$ idloc search "Semantic Web" --limit 5

International Semantic Web Conference (6th : 2007 : Pusan, Korea) Semantic Web : 6th International Semantic Web Conference, 2nd Asian Semantic Web Conference, ISWC 2007 + ASWC 2007, Busan, Korea, November 11-15, 2007 : proceedings
<http://id.loc.gov/resources/works/15024802>

International Semantic Web Conference (6th : 2007 : Pusan, Korea) The Semantic Web : 6th International Semantic Web Conference, 2nd Asian Semantic Web Conference, ISWC 2007 + ASWC 2007, Busan, Korea, November 11-15, 2007 : proceedings Berlin ; New York : Springer, 2007.
<http://id.loc.gov/resources/instances/15024802>

IFIP WG 12.5 Working Conference on Industrial Applications of Semantic Web (1st : 2005 : Jyväskylä, Finland) Industrial applications of semantic Web : proceedings of the 1st IFIP WG12.5 Working Conference on Industrial Applications of Semantic Web, August 25-27, 2005, Jyväskylä, Finland New York : Springer, c2005.
<http://id.loc.gov/resources/instances/14054943>

International Semantic Web Conference (1st : 2002 : Sardinia, Italy) semantic Web-ISWC 2002 : First International Semantic Web Conference, Sardinia, Italy, June 9-12, 2002 : proceedings
<http://id.loc.gov/resources/works/12761651>

International Semantic Web Conference (1st : 2002 : Sardinia, Italy) The semantic Web-ISWC 2002 : First International Semantic Web Conference, Sardinia, Italy, June 9-12, 2002 : proceedings Berlin ; New York : Springer, c2002.
<http://id.loc.gov/resources/instances/12761651>
```

Notice how the top 5 were taken up with bibframe instances? Similar to `get` you can limit a search to one or more concept schemes. For example if we want to search for "Semantic Web" only in the `subject-headings` and `name-authority` concept schemes:

```
$ idloc search --concept-scheme subject-headings --concept-scheme name-authority "Semantic Web" 
```

### Concept Schemes

You may be wondering what concept schemes are available. To see a list of them:

```
$ idloc concept-schemes
```

## Use as a Library

The idloc Python library can be used in your Python programs.


### Get

You can get the JSON-LD for a given id.loc.gov URI:

```
import idloc

concept = idloc.get('http://id.loc.gov/authorities/subjects/sh2002000569')
```

### Search

You can search for entities:

```python
for result in idloc.search('Semantic Web'):
    print(result['title'], result['uri']
```

Similarly you can limit to particular concept schemes:

```python
for result in idloc.search('Semantic Web', concept_schemes=['subject-headings', 'name-authority']):
    print(result['title'], result['uri'])
```

By default you get the first 20 results, but you can use the `limit` parameter to get more. If you set `limit` to `0` it will page through all the results.

### Concept Schemes

A mapping of concept scheme names and their corresponding URIs is available in:

```python
idloc.CONCEPT_SCHEMES
```

There are 130 of them! There is also a function `idloc.concept_schemes()` which will scrape the search interface at https://id.loc.gov/search to determine what the latest group of concept schemes is.

[pyld]: https://github.com/digitalbazaar/pyld

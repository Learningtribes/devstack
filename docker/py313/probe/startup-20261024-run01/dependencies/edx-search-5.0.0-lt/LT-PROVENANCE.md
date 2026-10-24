# LT search adaptation

Base: official edx-search 5.0.0 source archive retained in Goal B evidence.
LT API and filter generators: Learningtribes/edx-search 86ca377c34492ffac4633f342bd0c95c099b8398.
`upstream_elastic.py` preserves the genuine upstream engine. `elastic.py` extends it for LT typed documents, filters, targeting gates and facets using current Elasticsearch APIs. Python 2 names in the selected LT files are removed. No production indices are used.

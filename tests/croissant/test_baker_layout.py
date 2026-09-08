"""Regression: baker-shaped Croissants (FileSet @id = <rs>-fileset; field source links).

Mirrors what `biotope add <directory>` produces via croissant-baker: each
record set in a directory has a FileSet whose @id is ``<rs.name>-fileset``,
referenced from each field's ``source.fileSet.@id``. The Croissant JSON-LD
lives under ``.biotope/datasets/<rel>.jsonld`` and ``includes`` paths are
relative to the data directory at ``<project>/<rel>/``.
"""

from __future__ import annotations

import json

from biotope.croissant.spec import load_from_path


def test_spec_accepts_compressed_encoding_formats(tmp_path):
    """A wrapped file carries both media types, and includes gains a glob per
    compression. Typed as bare strings, these made every manifest over
    compressed data unreadable by `map inspect`."""
    manifest = tmp_path / "wrapped.jsonld"
    manifest.write_text(
        json.dumps(
            {
                "@context": {"@vocab": "https://schema.org/"},
                "@type": "sc:Dataset",
                "name": "wrapped",
                "distribution": [
                    {
                        "@id": "cells-fileset",
                        "@type": "cr:FileSet",
                        "name": "cells",
                        "includes": ["**/*.parquet", "**/*.parquet.gz"],
                        "encodingFormat": [
                            "application/vnd.apache.parquet",
                            "application/gzip",
                        ],
                    },
                    {
                        "@id": "file_0",
                        "@type": "cr:FileObject",
                        "name": "cells.parquet.gz",
                        "contentUrl": "cells.parquet.gz",
                        "encodingFormat": [
                            "application/vnd.apache.parquet",
                            "application/gzip",
                        ],
                    },
                    {
                        "@id": "file_1",
                        "@type": "cr:FileObject",
                        "name": "notes.csv",
                        "contentUrl": "notes.csv",
                        "encodingFormat": "text/csv",
                    },
                ],
                "recordSet": [],
            }
        )
    )

    dataset = load_from_path(manifest)

    file_set, wrapped, plain = dataset.distribution
    assert file_set.includes == ["**/*.parquet", "**/*.parquet.gz"]
    assert wrapped.encoding_format == [
        "application/vnd.apache.parquet",
        "application/gzip",
    ]
    assert plain.encoding_format == "text/csv"

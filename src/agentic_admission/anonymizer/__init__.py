"""PII anonymization pipeline for applicant data.

Modules
-------
strip_passports
    Record passport/ID document presence per candidate and delete the files.
recognizers
    Custom Presidio recognizers for Swiss/EPFL-specific PII (AVS/AHV, SCIPER).
presidio_pipeline
    PII detection and anonymization using Presidio with GLiNER NER backend.
allow_lists
    Domain-specific allow-lists for false-positive prevention.
thresholds
    Per-entity-type minimum confidence scores.
post_filters
    Post-analysis filters to reduce false positives (word boundary, length,
    excluded entities, etc.).
dob_operator
    Custom Presidio operator preserving birth year in DOB placeholders.
"""

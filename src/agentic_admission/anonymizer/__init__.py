"""PII anonymization pipeline for applicant data.

Modules
-------
strip_passports
    Record passport/ID document presence per candidate and delete the files.
recognizers
    Custom Presidio recognizers for Swiss/EPFL-specific PII (AVS/AHV, SCIPER).
presidio_pipeline
    PII detection and anonymization using Presidio with GLiNER NER backend.
"""

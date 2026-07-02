"""Project-specific half of the DAE acceptance pipeline for the analyst project.

- ``generator``: reads the fixed IR (``.build/spec.json``) and emits runnable
  pytest files under ``features/NNN-slug/.build/generated/``.
- ``handlers``: binds each Gherkin step's exact text to the real system
  (IngestionService / DatasetStore) via an in-process seam.

The portable front end (``dae_gherkin.py`` parser + JSON IR) is shipped
separately and is NOT part of this package.
"""

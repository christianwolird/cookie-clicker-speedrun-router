"""Shared output location for reusable experiment entry points."""
import os
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
EXPERIMENT = Path(__file__).resolve().parent.parent
DOCS = EXPERIMENT / 'docs'
FILE_RELOCATION = dict(
    original_experiment_directory='experiments/trained_250cps_search',
    current_experiment_directory=str(EXPERIMENT.relative_to(ROOT)),
    current_scripts_directory=str((EXPERIMENT / 'scripts').relative_to(ROOT)),
    current_docs_directory=str(DOCS.relative_to(ROOT)),
    note='Archived parameters, source-hash keys and embedded route snapshots preserve their original paths. Executable scripts and current documentation use the new layout.',
)
WORK = Path(os.environ.get('CCSR_EXPERIMENT_DIRECTORY', '/tmp/ccsr-trained-12h-20260914'))

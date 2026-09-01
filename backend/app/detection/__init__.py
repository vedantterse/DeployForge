"""Pure repository detection. No FastAPI, no database, no network."""

from app.detection.candidates import (
    RepositoryCandidate,
    ROOT_PATH,
    deployable_candidates,
    resolve_path,
    scan_candidates,
)
from app.detection.detector import DetectedType, DetectionResult, detect_repository

__all__ = [
    "DetectedType",
    "DetectionResult",
    "detect_repository",
    "RepositoryCandidate",
    "ROOT_PATH",
    "scan_candidates",
    "deployable_candidates",
    "resolve_path",
]

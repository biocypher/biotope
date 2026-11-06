"""Paths anchored to this workspace, independent of the shell's directory."""

from pathlib import Path


GRAPH_ROOT = Path(__file__).resolve().parent
PROJECT_ROOT = GRAPH_ROOT.parent

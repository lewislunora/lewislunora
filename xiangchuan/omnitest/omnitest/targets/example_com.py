"""Minimal demo profile: example.com — shows how any domain gets onboarded."""
from omnitest.core.config import Target

TARGET = Target(
    name="example_com",
    base_url="https://example.com",
    seed_paths=["/"],
    authorized_domains=[],   # fill before heavy modules
    notes="Reference/static page; light modules only.",
)

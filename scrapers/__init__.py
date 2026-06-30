"""
scrapers/__init__.py

Priority order (highest to lowest):
  1. survey    - 1st-party personal survey (direct user research)
  2. playstore - Google Play Store reviews
"""
from . import survey, playstore

__all__ = ["survey", "playstore"]


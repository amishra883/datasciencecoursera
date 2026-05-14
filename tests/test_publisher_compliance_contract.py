"""Smoke test: descriptions Publisher emits must pass Compliance.

Catches drift where Publisher template stops including a marker that
Compliance enforces (attribution / transformative / AI-content label).
"""

from __future__ import annotations

from dataclasses import replace

from agents import compliance, publisher


def test_publisher_description_passes_compliance_with_visuals(good_clip):
    desc = publisher.build_description(
        creator=good_clip.source_creator,
        visuals_used=True,
        affiliate_present=False,
    )
    clip = replace(good_clip, description=desc)
    result = compliance.evaluate(clip)
    assert result.passed is True, result.blocked_reason


def test_publisher_description_passes_compliance_without_visuals(good_clip):
    desc = publisher.build_description(
        creator=good_clip.source_creator,
        visuals_used=False,
        affiliate_present=False,
    )
    clip = replace(good_clip, description=desc, visuals_used=[])
    result = compliance.evaluate(clip)
    assert result.passed is True, result.blocked_reason


def test_publisher_description_with_affiliate_includes_ad_marker(good_clip):
    desc = publisher.build_description(
        creator=good_clip.source_creator,
        visuals_used=True,
        affiliate_present=True,
    )
    assert "#ad" in desc
    clip = replace(good_clip, description=desc)
    result = compliance.evaluate(clip)
    assert result.passed is True

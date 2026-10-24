"""Unit tests for IdentityResolver.
"""

from code.agents.identity_resolver import IdentityResolver
from code.ingestion.load_datasets import load_all_datasets


def test_identity_resolution():
    index = load_all_datasets("dataset", use_sample=True)
    resolver = IdentityResolver(index)

    # Test exact email match
    res1 = resolver.resolve("nadia.ionescu@yahoo.com")
    assert res1.user_id == "user_10"
    assert "nadia.ionescu@yahoo.com" in res1.all_identifiers
    assert res1.is_ambiguous is False

    # Test resolution with case insensitivity
    res2 = resolver.resolve("NADIA.IONESCU@YAHOO.COM")
    assert res2.user_id == "user_10"

    # Test historical identifier resolution
    res3 = resolver.resolve("minjun.kim@gmail.com")
    assert res3.user_id == "user_12"
    assert len(res3.all_identifiers) > 1

    # Test unknown identifier
    res4 = resolver.resolve("nonexistent_user_9999@example.com")
    assert res4.user_id is None
    assert res4.is_ambiguous is True

from app.backend.engine.grounding import check_grounded, extract_numbers_and_tokens


def test_exact_substring_is_grounded():
    doc = "Owned onboarding funnel and ran experiments that improved activation by 18%."
    result = check_grounded("improved activation by 18%", doc)
    assert result.grounded
    assert result.similarity == 1.0


def test_fabricated_text_is_not_grounded():
    doc = "Owned onboarding funnel and ran experiments that improved activation by 18%."
    result = check_grounded("Managed a team of 50 engineers across three continents", doc)
    assert not result.grounded


def test_minor_whitespace_noise_still_grounds():
    doc = "Owned  onboarding\nfunnel and ran experiments that improved activation by 18%."
    result = check_grounded("Owned onboarding funnel and ran experiments", doc)
    assert result.grounded


def test_extract_numbers_and_tokens_finds_metrics_and_names():
    tokens = extract_numbers_and_tokens("Improved activation by 18% at Acme using SQL")
    assert "18%" in tokens
    assert "Acme" in tokens
    assert "SQL" in tokens

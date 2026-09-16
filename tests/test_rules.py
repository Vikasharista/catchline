from app.validate.rules import QuoteRow, low_confidence_flags, not_quoted_flags, peer_outlier_flags, severity_of


def test_severity_mapping():
    assert severity_of("illegible") == "red"
    assert severity_of("peer_outlier") == "amber"
    assert severity_of("fx_converted") == "info"
    assert severity_of("unknown_code") == "info"


def test_peer_outlier_detected():
    quotes = [
        QuoteRow("S1", "Sup1", "L01", 8.0),
        QuoteRow("S2", "Sup2", "L01", 8.2),
        QuoteRow("S3", "Sup3", "L01", 12.0),  # ~46% above median of 8.1 -> outlier
    ]
    flags = peer_outlier_flags(quotes)
    assert any(f.supplier_id == "S3" and f.line_id == "L01" for f in flags)
    assert not any(f.supplier_id == "S1" for f in flags)


def test_low_confidence_flag():
    quotes = [QuoteRow("S1", "Sup1", "L01", 8.0, confidence=0.5)]
    flags = low_confidence_flags(quotes)
    assert len(flags) == 1
    assert flags[0].code == "low_confidence"


def test_not_quoted_flags():
    quotes = [QuoteRow("S1", "Sup1", "L01", 8.0)]
    flags = not_quoted_flags(quotes, all_line_ids=["L01", "L02"], supplier_ids=["S1"])
    assert len(flags) == 1
    assert flags[0].line_id == "L02"

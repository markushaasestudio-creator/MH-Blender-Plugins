from mh_room_builder.analyzer.dimensions import parse_dimension, parse_scale_denominator


def test_explicit_mm():
    parsed = parse_dimension("3450 mm")
    assert parsed is not None
    assert parsed.value_mm == 3450


def test_decimal_meters():
    parsed = parse_dimension("3,45")
    assert parsed is not None
    assert parsed.value_mm == 3450


def test_ambiguous_small_integer_is_rejected():
    assert parse_dimension("90") is None


def test_print_scale():
    assert parse_scale_denominator("Maßstab M 1:50") == 50

from datetime import date, timedelta
import os

import pytest

from doonook_chinese_calendar.services import astro_basis as basis


@pytest.mark.parametrize(
    "a,b,expected", [(359, 1, 2), (1, 359, 2), (0, 180, 180), (10, 370, 0)]
)
def test_circular_distance(a, b, expected):
    assert basis.angular_distance(a, b) == expected


@pytest.mark.parametrize(
    "angle,name",
    [
        (0, "conjunction"),
        (60, "sextile"),
        (90, "square"),
        (120, "trine"),
        (180, "opposition"),
    ],
)
def test_major_aspects(angle, name):
    result = basis.find_aspect(0, angle)
    assert result["name"] == name and result["orb"] == 0


def test_orb_boundary_and_no_aspect():
    assert basis.find_aspect(359, 1)["name"] == "conjunction"
    assert basis.find_aspect(0, 8)["name"] == "conjunction"
    assert basis.find_aspect(0, 8.001) is None
    assert basis.find_aspect(0, 45) is None


@pytest.fixture
def positions():
    return dict(
        sun=200, moon=11, mercury=280, venus=0, mars=30, jupiter=120, saturn=120
    )


def test_example_rules_and_sign_specific_houses(positions):
    aries = basis.daily_rules(positions, 1)
    libra = basis.daily_rules(positions, 7)
    love = {f["id"]: f for f in aries["love"]}
    career = {f["id"]: f for f in aries["career"]}
    assert love["aspect:venus:jupiter:trine"]["contribution"] == 1
    assert career["aspect:mars:saturn:square"]["contribution"] == -1
    assert any(f["id"] == "house:venus:7" for f in libra["love"])
    assert not any(f["id"] == "house:venus:7" for f in aries["love"])
    assert aries == basis.daily_rules(positions, 1)


@pytest.fixture
def fake_ephemeris(monkeypatch, positions):
    monkeypatch.setattr(basis, "_kernel", lambda path: (None, None, "test-sha256"))

    def year(path, year, timezone):
        first = date(year, 1, 1)
        return {
            first + timedelta(days=i): dict(positions)
            for i in range((date(year + 1, 1, 1) - first).days)
        }

    monkeypatch.setattr(basis, "_year_positions", year)


def test_full_period_sampling_leap_day_and_year_rollover(fake_ephemeris):
    leap = basis.build_basis(1, date(2024, 2, 29), "fake")
    assert leap["month"]["sample_count"] == 29
    assert leap["year"]["sample_count"] == 366
    assert leap["week"]["sample_count"] == 7
    assert leap["tomorrow"]["start"] == "2024-03-01"
    newyear = basis.build_basis(1, date(2024, 12, 31), "fake")
    assert newyear["tomorrow"]["start"] == "2025-01-01"
    assert newyear["week"]["end"] == "2025-01-05"
    for item in leap.values():
        for category in item["categories"].values():
            assert 1 <= category["score"] <= 5
            assert all(
                f["observed_days"] <= item["sample_count"] for f in category["factors"]
            )


def test_period_basis_deterministic_across_request_days(fake_ephemeris):
    one = basis.build_basis(1, date(2026, 9, 17), "fake")
    two = basis.build_basis(1, date(2026, 9, 18), "fake")
    assert (
        one["year"] == two["year"]
        and one["month"] == two["month"]
        and one["week"] == two["week"]
    )
    assert one["tomorrow"] == two["today"]


def test_missing_and_invalid_file_fail_without_network(tmp_path, monkeypatch):
    with pytest.raises(basis.EphemerisError):
        basis.build_basis(1, date(2026, 9, 17), str(tmp_path / "missing.bsp"))
    invalid = tmp_path / "invalid.bsp"
    invalid.write_bytes(b"not a kernel")
    with pytest.raises(basis.EphemerisError):
        basis.build_basis(1, date(2026, 9, 17), str(invalid))


def test_out_of_range_request_fails():
    with pytest.raises(basis.EphemerisError):
        basis.build_basis(1, date(2200, 1, 1), "not-used")


def test_real_offline_ephemeris_solar_position_and_provenance():
    path = os.environ.get("TEST_ASTRO_EPHEMERIS_PATH", "")
    output = basis.build_basis(1, date(2026, 9, 17), path)
    today = output["today"]
    assert 170 < today["positions"]["sun"]["longitude"] < 177
    assert today["positions"]["sun"]["sign"] == "处女座"
    assert len(today["positions"]) == 7
    assert len(today["ephemeris_sha256"]) == 64
    assert output["year"]["sample_count"] == 365
    assert output == basis.build_basis(1, date(2026, 9, 17), path)


def test_bundled_kernel_has_expected_fingerprint():
    _, _, digest = basis._kernel("")
    assert digest == "c1c7feeab882263fc493a9d5a5b2ddd71b54826cdf65d8d17a76126b260a49f2"


def test_bad_explicit_override_never_falls_back_to_bundled(tmp_path):
    with pytest.raises(basis.EphemerisError):
        basis._kernel(str(tmp_path / "does-not-exist.bsp"))

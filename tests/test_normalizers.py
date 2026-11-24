"""Unit tests for Indonesian reference normalizers (waktu, nominal, wilayah, satuan)."""

from __future__ import annotations

from indoarg.normalizers import (
    cari_stasiun_krl,
    cari_wilayah,
    parse_nominal,
    parse_satuan,
    parse_waktu,
)

REF_TIME = "2026-11-23T18:00:00+07:00"  # Senin, 23 Nov 2026


def test_parse_waktu_relative_and_informal() -> None:
    assert parse_waktu("besok jam 7an malem", REF_TIME)["iso"] == "2026-11-24T19:00:00+07:00"
    assert parse_waktu("lusa jam setengah 8 pagi", REF_TIME)["iso"] == "2026-11-25T07:30:00+07:00"
    assert parse_waktu("besok jam 3 sore", REF_TIME)["iso"] == "2026-11-24T15:00:00+07:00"
    assert parse_waktu("24/11 jam setengah 6 sore", REF_TIME)["iso"] == "2026-11-24T17:30:00+07:00"
    assert parse_waktu("Senin depan jam 10 pagi", REF_TIME)["iso"] == "2026-11-30T10:00:00+07:00"
    assert parse_waktu("minggu depan jam 1 siang", REF_TIME)["iso"] == "2026-11-30T13:00:00+07:00"
    assert parse_waktu("tgl 25 Nov", REF_TIME)["date"] == "2026-11-25"
    assert parse_waktu("besok", REF_TIME)["date"] == "2026-11-24"


def test_parse_nominal_slang_short_and_words() -> None:
    assert parse_nominal("gocap")["nominal"] == 50_000
    assert parse_nominal("ceban")["nominal"] == 10_000
    assert parse_nominal("noban")["nominal"] == 20_000
    assert parse_nominal("cepek ribu")["nominal"] == 100_000
    assert parse_nominal("cepek dolar singapura")["nominal"] == 100
    assert parse_nominal("50rb")["nominal"] == 50_000
    assert parse_nominal("50k")["nominal"] == 50_000
    assert parse_nominal("1,5jt")["nominal"] == 1_500_000
    assert parse_nominal("Rp50.000")["nominal"] == 50_000
    assert parse_nominal("Rp 1.500.000")["nominal"] == 1_500_000
    assert parse_nominal("dua ratus ribu")["nominal"] == 200_000
    assert parse_nominal("seratus lima puluh ribu")["nominal"] == 150_000
    assert parse_nominal("seratus dua puluh ribu")["nominal"] == 120_000
    assert parse_nominal("sejuta")["nominal"] == 1_000_000
    assert parse_nominal("setengah juta")["nominal"] == 500_000


def test_cari_wilayah_and_stasiun_krl() -> None:
    assert cari_wilayah("Jaksel")["kode"] == "31.74"
    assert cari_wilayah("sby")["kode"] == "35.78"
    assert cari_wilayah("Jogja")["kode"] == "34.71"
    assert cari_wilayah("bdg")["kode"] == "32.73"
    assert cari_wilayah("Tangsel")["kode"] == "36.74"
    assert cari_wilayah("Kota Semarang")["kode"] == "33.74"
    assert cari_wilayah("31.74")["kode"] == "31.74"

    assert cari_stasiun_krl("Depok")["kode"] == "DP"
    assert cari_stasiun_krl("Stasiun Manggarai")["kode"] == "MRI"
    assert cari_stasiun_krl("tenabang")["kode"] == "THB"
    assert cari_stasiun_krl("Serpong")["kode"] == "SRP"


def test_parse_satuan_weight_and_duration() -> None:
    assert parse_satuan("2 kilo", "gram")["nilai"] == 2000
    assert parse_satuan("setengah kilo", "gram")["nilai"] == 500
    assert parse_satuan("1,5 kg", "gram")["nilai"] == 1500
    assert parse_satuan("3 ons", "gram")["nilai"] == 300
    assert parse_satuan("sejam setengah", "menit")["nilai"] == 90
    assert parse_satuan("setengah jam", "menit")["nilai"] == 30
    assert parse_satuan("1 jam", "menit")["nilai"] == 60
    assert parse_satuan("dua jam seperempat", "menit")["nilai"] == 135
    assert parse_satuan("2 jam 15 menit", "menit")["nilai"] == 135

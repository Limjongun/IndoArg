"""Deterministic mock executors for the 10 IndoArg tools and 4 S4 normalizer tools."""

from __future__ import annotations

from typing import Any

from indoarg.normalizers import cari_wilayah, parse_nominal, parse_satuan, parse_waktu
from indoarg.tools.registry import ToolRegistry


def execute_normalizer_tool(name: str, arguments: dict[str, Any]) -> dict[str, Any]:
    """Execute one of the 4 S4 normalizer tools deterministically."""
    if name == "parse_waktu":
        return parse_waktu(
            teks=str(arguments.get("teks", "")),
            waktu_acuan=str(arguments.get("waktu_acuan", "2026-11-23T18:00:00+07:00")),
        )
    if name == "parse_nominal":
        return parse_nominal(teks=str(arguments.get("teks", "")))
    if name == "cari_wilayah":
        return cari_wilayah(teks=str(arguments.get("teks", "")))
    if name == "parse_satuan":
        return parse_satuan(
            teks=str(arguments.get("teks", "")),
            target=str(arguments.get("target", "")),
        )
    return {"error": f"Normalizer tool tidak dikenal: '{name}'"}


def execute_target_tool(
    name: str,
    arguments: dict[str, Any],
    registry: ToolRegistry | None = None,
) -> dict[str, Any]:
    """Validate arguments against schema and return deterministic mock response."""
    reg = registry or ToolRegistry.default_target_tools()
    ok, errors = reg.validate_call(name, arguments)
    if not ok:
        return {"status": "error", "tool": name, "errors": errors}

    if name == "buat_pengingat":
        return {
            "status": "ok",
            "tool": name,
            "pengingat_id": "REM-0001",
            "judul": arguments["judul"],
            "waktu": arguments["waktu"],
        }
    if name == "transfer_ewallet":
        return {
            "status": "ok",
            "tool": name,
            "transaksi_id": "TRX-0001",
            "penerima": arguments["penerima"],
            "nominal": arguments["nominal"],
            "platform": arguments["platform"],
        }
    if name == "cek_ongkir":
        kg = max(1, (int(arguments["berat_gram"]) + 999) // 1000)
        return {
            "status": "ok",
            "tool": name,
            "asal": arguments["asal"],
            "tujuan": arguments["tujuan"],
            "berat_gram": arguments["berat_gram"],
            "kurir": arguments["kurir"],
            "estimasi_rupiah": kg * 18000,
        }
    if name == "jadwal_krl":
        return {
            "status": "ok",
            "tool": name,
            "stasiun_asal": arguments["stasiun_asal"],
            "stasiun_tujuan": arguments["stasiun_tujuan"],
            "waktu": arguments["waktu"],
            "kereta_berikutnya": arguments["waktu"],
        }
    if name == "cek_cuaca":
        return {
            "status": "ok",
            "tool": name,
            "wilayah": arguments["wilayah"],
            "tanggal": arguments["tanggal"],
            "kondisi": "berawan",
        }
    if name == "pesan_ojek":
        return {
            "status": "ok",
            "tool": name,
            "pesanan_id": "ORD-0001",
            "jemput": arguments["jemput"],
            "tujuan": arguments["tujuan"],
            "layanan": arguments["layanan"],
        }
    if name == "konversi_kurs":
        return {
            "status": "ok",
            "tool": name,
            "jumlah": arguments["jumlah"],
            "dari": arguments["dari"],
            "ke": arguments["ke"],
            "hasil_mock": arguments["jumlah"],
        }
    if name == "bayar_tagihan":
        return {
            "status": "ok",
            "tool": name,
            "referensi_id": "BIL-0001",
            "jenis": arguments["jenis"],
            "id_pelanggan": arguments["id_pelanggan"],
            "nominal": arguments["nominal"],
        }
    if name == "buat_jadwal_rapat":
        return {
            "status": "ok",
            "tool": name,
            "rapat_id": "MTG-0001",
            "judul": arguments["judul"],
            "mulai": arguments["mulai"],
            "durasi_menit": arguments["durasi_menit"],
            "peserta": arguments["peserta"],
        }
    if name == "cari_dokumen":
        return {
            "status": "ok",
            "tool": name,
            "query": arguments["query"],
            "top_k": arguments["top_k"],
            "hasil": [],
        }
    return {"status": "error", "tool": name, "errors": [f"Executor tidak tersedia untuk '{name}'"]}

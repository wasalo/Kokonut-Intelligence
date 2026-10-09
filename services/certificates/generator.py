"""Certificate generation for carbon credit retirements."""

from __future__ import annotations

import hashlib
import json
from datetime import datetime, timezone
from string import Template
from pathlib import Path

from services.common.logging import get_logger

logger = get_logger("certificates.generator")

TEMPLATE_DIR = Path(__file__).parent / "templates"


def _generate_certificate_number(conn, location_id: str) -> str:
    loc = conn.execute(
        conn.text("SELECT name FROM location WHERE id = :lid"),
        {"lid": location_id},
    ).mappings().first()
    prefix = loc["name"][:4].upper() if loc else "UNKN"

    seq = conn.execute(
        conn.text("SELECT COUNT(*) + 1 as seq FROM retirement_certificate WHERE location_id = :lid"),
        {"lid": location_id},
    ).mappings().first()

    year = datetime.now(timezone.utc).year
    return f"RET-{year}-{prefix}-{seq['seq']:04d}"


def render_certificate_html(template_data: dict) -> str:
    template_path = TEMPLATE_DIR / "retirement_certificate.html"
    if template_path.exists():
        template_text = template_path.read_text()
    else:
        template_text = """
<!DOCTYPE html>
<html>
<head><title>Carbon Credit Retirement Certificate</title>
<style>
body { font-family: 'Georgia', serif; max-width: 800px; margin: 40px auto; padding: 20px; }
.header { text-align: center; border-bottom: 3px double #333; padding-bottom: 20px; }
.title { font-size: 28px; font-weight: bold; margin: 20px 0; }
.details { margin: 30px 0; }
.row { display: flex; margin: 8px 0; }
.label { font-weight: bold; width: 200px; }
.footer { margin-top: 40px; border-top: 1px solid #ccc; padding-top: 10px; font-size: 12px; color: #666; }
</style>
</head>
<body>
<div class="header">
  <div class="title">Carbon Credit Retirement Certificate</div>
  <div>Certificate # $certificate_number</div>
</div>
<div class="details">
  <div class="row"><div class="label">Beneficiary:</div><div>$beneficiary_name</div></div>
  <div class="row"><div class="label">Tonnes Retired:</div><div>$retired_tonnes tCO2e</div></div>
  <div class="row"><div class="label">Vintage Year:</div><div>$vintage_year</div></div>
  <div class="row"><div class="label">Methodology:</div><div>$methodology</div></div>
  <div class="row"><div class="label">Retirement Reason:</div><div>$retirement_reason</div></div>
  <div class="row"><div class="label">Statement:</div><div>$retirement_statement</div></div>
  <div class="row"><div class="label">Issued:</div><div>$issued_at</div></div>
</div>
<div class="footer">
  <div>Verify this certificate: $verification_url</div>
  <div>This certificate confirms permanent retirement of carbon credits.</div>
</div>
</body>
</html>"""
    tmpl = Template(template_text)
    return tmpl.safe_substitute(template_data)


def generate_certificate(conn, retirement_id: str) -> dict:
    retirement = conn.execute(
        conn.text("SELECT * FROM credit_retirement WHERE id = :rid"),
        {"rid": retirement_id},
    ).mappings().first()
    if not retirement:
        raise ValueError(f"Retirement not found: {retirement_id}")

    credit = conn.execute(
        conn.text("SELECT * FROM carbon_credit WHERE id = :cid"),
        {"cid": retirement["credit_id"]},
    ).mappings().first()

    location = conn.execute(
        conn.text("SELECT * FROM location WHERE id = :lid"),
        {"lid": retirement["location_id"]},
    ).mappings().first()

    certificate_number = _generate_certificate_number(conn, retirement["location_id"])
    verification_url = f"https://kokonut.network/certificate/{certificate_number}"

    template_data = {
        "certificate_number": certificate_number,
        "beneficiary_name": retirement.get("beneficiary_name", "Anonymous"),
        "retired_tonnes": str(retirement["retired_tonnes"]),
        "vintage_year": str(credit["vintage_year"]) if credit else "N/A",
        "methodology": credit["methodology"] if credit else "N/A",
        "retirement_reason": retirement["retirement_reason"],
        "retirement_statement": retirement.get("retirement_statement", ""),
        "issued_at": datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC"),
        "verification_url": verification_url,
    }

    html = render_certificate_html(template_data)
    content_hash = hashlib.sha256(html.encode()).hexdigest()

    result = conn.execute(
        conn.text(
            "INSERT INTO retirement_certificate "
            "(retirement_id, credit_id, location_id, certificate_number, "
            "retired_tonnes, retirement_reason, beneficiary_name, beneficiary_wallet, "
            "retirement_statement, vintage_year, methodology, "
            "certificate_html, certificate_hash, verification_url, "
            "status, created_by) "
            "VALUES "
            "(:rid, :cid, :lid, :cn, "
            ":rt, :rr, :bn, :bw, "
            ":rs, :vy, :m, "
            ":ch, :csh, :vu, "
            "'issued', :cb) "
            "RETURNING id"
        ),
        {
            "rid": retirement_id, "cid": retirement["credit_id"],
            "lid": retirement["location_id"], "cn": certificate_number,
            "rt": retirement["retired_tonnes"], "rr": retirement["retirement_reason"],
            "bn": retirement.get("beneficiary_name"), "bw": retirement.get("beneficiary_wallet"),
            "rs": retirement.get("retirement_statement"),
            "vy": credit["vintage_year"] if credit else None,
            "m": credit["methodology"] if credit else None,
            "ch": html, "csh": content_hash, "vu": verification_url,
            "cb": retirement.get("created_by"),
        },
    ).mappings().first()

    logger.info("Generated certificate %s for retirement %s", certificate_number, retirement_id)
    return {
        "certificate_id": str(result["id"]),
        "certificate_number": certificate_number,
        "verification_url": verification_url,
        "certificate_hash": content_hash,
    }


def verify_certificate(conn, certificate_number: str) -> dict:
    cert = conn.execute(
        conn.text("SELECT * FROM retirement_certificate WHERE certificate_number = :cn"),
        {"cn": certificate_number},
    ).mappings().first()
    if not cert:
        return {"valid": False, "error": "Certificate not found"}

    import hashlib
    current_hash = hashlib.sha256((cert["certificate_html"] or "").encode()).hexdigest()
    return {
        "valid": current_hash == cert["certificate_hash"],
        "certificate_number": certificate_number,
        "status": cert["status"],
        "retired_tonnes": float(cert["retired_tonnes"]),
        "beneficiary_name": cert["beneficiary_name"],
        "issued_at": str(cert["issued_at"]),
    }

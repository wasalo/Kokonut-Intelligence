"""Focused XML integrity checks for CSW metadata serialization."""

from xml.etree import ElementTree as ET

from services.csw.serializer import serialize_records_to_iso19115, serialize_to_iso19115

GMD = "http://www.isotc211.org/2005/gmd"
GCO = "http://www.isotc211.org/2005/gco"
CSW = "http://www.opengis.net/cat/csw/2.0.2"


def test_iso19115_serializer_escapes_metadata_as_text():
    xml = serialize_to_iso19115(
        {
            "identifier": "farm<&>1",
            "title": 'Farm A & B <evil:injected xmlns:evil="urn:attacker">North</evil:injected>',
            "abstract": "Soil < 10 & crop > 2\x00",
            "topic_category": "environment&agriculture",
            "reference_system": "EPSG:<4326>",
        }
    )

    root = ET.fromstring(xml)
    assert root.findtext(f".//{{{GMD}}}fileIdentifier/{{{GCO}}}CharacterString") == "farm<&>1"
    assert root.findtext(f".//{{{GMD}}}title/{{{GCO}}}CharacterString") == (
        'Farm A & B <evil:injected xmlns:evil="urn:attacker">North</evil:injected>'
    )
    assert root.findtext(f".//{{{GMD}}}abstract/{{{GCO}}}CharacterString") == "Soil < 10 & crop > 2\uFFFD"
    assert root.find(".//{urn:attacker}injected") is None


def test_csw_record_response_declares_namespaces_and_escapes_fields():
    xml = serialize_records_to_iso19115(
        [
            {
                "identifier": "dataset<&>1",
                "title": "Trees & shade <plot>",
                "abstract": "Canopy > 40% & diverse",
            }
        ]
    )

    root = ET.fromstring(xml)
    record = root.find(f"{{{CSW}}}Record")
    assert record is not None
    assert record.findtext(f"{{{GMD}}}fileIdentifier/{{{GCO}}}CharacterString") == "dataset<&>1"
    assert record.findtext(f"{{{GMD}}}title/{{{GCO}}}CharacterString") == "Trees & shade <plot>"
    assert record.findtext(f"{{{GMD}}}abstract/{{{GCO}}}CharacterString") == "Canopy > 40% & diverse"
    assert len(record) == 3

"""CSW metadata serializer: convert to ISO 19115 XML format."""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from services.common.logging import get_logger

logger = get_logger("csw.serializer")

ISO_19115_TEMPLATE = """<?xml version="1.0" encoding="UTF-8"?>
<gmd:MD_Metadata xmlns:gmd="http://www.isotc211.org/2005/gmd"
                  xmlns:gco="http://www.isotc211.org/2005/gco"
                  xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance">
  <gmd:fileIdentifier>
    <gco:CharacterString>{identifier}</gco:CharacterString>
  </gmd:fileIdentifier>
  <gmd:language>
    <gco:CharacterString>eng</gco:CharacterString>
  </gmd:language>
  <gmd:characterSet>
    <gmd:MD_CharacterSetCode codeList="http://www.isotc211.org/2005/resources/Codelist/gmxCodelists.xml#MD_CharacterSetCode" codeListValue="utf8">utf8</gmd:MD_CharacterSetCode>
  </gmd:characterSet>
  <gmd:level>
    <gmd:MD_ScopeCode codeList="http://www.isotc211.org/2005/resources/Codelist/gmxCodelists.xml#MD_ScopeCode" codeListValue="dataset">dataset</gmd:MD_ScopeCode>
  </gmd:level>
  <gmd:identificationInfo>
    <gmd:MD_DataIdentification>
      <gmd:citation>
        <gmd:CI_Citation>
          <gmd:title>
            <gco:CharacterString>{title}</gco:CharacterString>
          </gmd:title>
          <gmd:date>
            <gmd:CI_Date>
              <gmd:date>
                <gco:Date>{date}</gco:Date>
              </gmd:date>
              <gmd:dateType>
                <gmd:CI_DateTypeCode codeList="http://www.isotc211.org/2005/resources/Codelist/gmxCodelists.xml#CI_DateTypeCode" codeListValue="creation">creation</gmd:CI_DateTypeCode>
              </gmd:dateType>
            </gmd:CI_Date>
          </gmd:date>
        </gmd:CI_Citation>
      </gmd:citation>
      <gmd:abstract>
        <gco:CharacterString>{abstract}</gco:CharacterString>
      </gmd:abstract>
      <gmd:topicCategory>
        <gmd:MD_TopicCategoryCode>{topic_category}</gmd:MD_TopicCategoryCode>
      </gmd:topicCategory>
    </gmd:MD_DataIdentification>
  </gmd:identificationInfo>
  <gmd:referenceSystemInfo>
    <gmd:MD_ReferenceSystem>
      <gmd:referenceSystemIdentifier>
        <gmd:RS_Identifier>
          <gco:CharacterString>{reference_system}</gco:CharacterString>
        </gmd:RS_Identifier>
      </gmd:referenceSystemIdentifier>
    </gmd:MD_ReferenceSystem>
  </gmd:referenceSystemInfo>
</gmd:MD_Metadata>"""


def serialize_to_iso19115(record: dict) -> str:
    return ISO_19115_TEMPLATE.format(
        identifier=record.get("identifier", str(record.get("id", ""))),
        title=record.get("title", "Untitled"),
        abstract=record.get("abstract", record.get("content", "")),
        date=record.get("date", datetime.now(timezone.utc).strftime("%Y-%m-%d")),
        topic_category=record.get("topic_category", "environment"),
        reference_system=record.get("reference_system", "EPSG:4326"),
    )


def serialize_records_to_iso19115(records: list[dict]) -> str:
    xml_parts = ['<?xml version="1.0" encoding="UTF-8"?>']
    xml_parts.append('<csw:GetRecordsResponse xmlns:csw="http://www.opengis.net/cat/csw/2.0.2">')

    for record in records:
        xml_parts.append("  <csw:Record>")
        xml_parts.append(f"    <gmd:fileIdentifier><gco:CharacterString>{record.get('identifier', '')}</gco:CharacterString></gmd:fileIdentifier>")
        xml_parts.append(f"    <gmd:title><gco:CharacterString>{record.get('title', '')}</gco:CharacterString></gmd:title>")
        xml_parts.append(f"    <gmd:abstract><gco:CharacterString>{record.get('abstract', '')}</gco:CharacterString></gmd:abstract>")
        xml_parts.append("  </csw:Record>")

    xml_parts.append("</csw:GetRecordsResponse>")
    return "\n".join(xml_parts)

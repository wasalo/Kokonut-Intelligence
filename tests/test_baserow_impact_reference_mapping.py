from pathlib import Path
import unittest


ROOT = Path(__file__).resolve().parents[1]
CROSSWALK = (ROOT / "docs/phase1-baserow-field-crosswalk.md").read_text()
REPORT = (ROOT / "docs/phase1-baserow-legacy-data-reconciliation.md").read_text()
SCHEMA = (ROOT / "schemas/postgres/025_kokonut_framework_alignment.sql").read_text()
SEED = (ROOT / "schemas/seeds/023_impact_frameworks.sql").read_text()


def section_for(table_name: str) -> str:
    marker = f"### {table_name} (table ID `"
    start = CROSSWALK.index(marker)
    end = CROSSWALK.find("\n### ", start + len(marker))
    return CROSSWALK[start:] if end < 0 else CROSSWALK[start:end]


def row_for(table_name: str, field_name: str) -> list[str]:
    section = section_for(table_name)
    prefix = f"| `{field_name}` (`"
    line = next(line for line in section.splitlines() if line.startswith(prefix))
    return [cell.strip() for cell in line.strip().strip("|").split("|")]


class ImpactReferenceMappingContractTest(unittest.TestCase):
    def test_framework_source_url_is_a_validated_candidate(self):
        row = row_for("Impact Frameworks", "Source")
        self.assertEqual(row[2], "`impact_framework.url`")
        self.assertEqual(row[3], "`CANDIDATE`")
        self.assertIn("value passed HTTP(S) URL parsing", row[4])
        self.assertIn("VARCHAR(500)", SCHEMA)

    def test_framework_status_is_not_inferred_from_target_default(self):
        name_row = row_for("Impact Frameworks", "Name")
        self.assertIn("no source active field", name_row[4].lower())
        self.assertIn("explicitly set `status = null`", name_row[4].lower())
        self.assertIn("status VARCHAR(50) DEFAULT 'active'", SCHEMA)

    def test_dimension_framework_relationship_is_allocated_once(self):
        for table in ("Impact Dimensions", "Impact Frameworks"):
            row = row_for("Impact Dimensions", "Impact Frameworks") if table == "Impact Dimensions" else row_for("Impact Frameworks", "Impact Dimensions")
            self.assertEqual(row[2], "`impact_dimension.framework_id`")
            self.assertEqual(row[3], "`RELATIONSHIP`")
            self.assertIn("zero source edges", row[4].lower())
        self.assertIn("framework_id UUID REFERENCES impact_framework(id)", SCHEMA)

    def test_required_names_and_blank_source_rows_are_reported(self):
        self.assertIn("Seven of the eight rows have no source name", REPORT)
        for table in ("impact_framework", "impact_dimension", "sdg", "form_of_capital"):
            self.assertIn(f"DELETE FROM {table} WHERE COALESCE(TRIM(name), '') = ''", SEED)
        self.assertIn("name VARCHAR(255) NOT NULL", SCHEMA)

    def test_empty_catalog_labels_do_not_create_invented_identity(self):
        forms_active = row_for("Forms of Capital", "Active")
        sdg_active = row_for("SDGs", "Active")
        self.assertEqual(forms_active[2], "`form_of_capital.is_active`")
        self.assertEqual(sdg_active[2], "`sdg.is_active`")
        self.assertIn("both source values are false", forms_active[4].lower())
        self.assertIn("both source values are false", sdg_active[4].lower())
        self.assertIn("do not infer", row_for("SDGs", "Name")[4].lower())


if __name__ == "__main__":
    unittest.main()

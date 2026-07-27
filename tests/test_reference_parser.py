from unittest import TestCase

from app.formulas.reference_parser import parse_references, parse_references_with_diagnostics


class ReferenceParserTests(TestCase):
    def test_normalizes_supported_references(self):
        self.assertEqual(
            parse_references("=SUM($B$2:B10)+'Input Sheet'!$C$3+Input!D4", "Revenue"),
            ["Revenue!B2:B10", "'Input Sheet'!C3", "Input!D4"],
        )

    def test_ignores_strings_and_reports_external_links(self):
        refs, diagnostics = parse_references_with_diagnostics('="A1"+[Other.xlsx]Input!A1', "Revenue")
        self.assertEqual(refs, ["Input!A1"])
        self.assertTrue(diagnostics)

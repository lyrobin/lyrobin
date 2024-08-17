import unittest
from utils import testings
from wiki import parsers, models


class TestOrganizationReader(unittest.TestCase):

    @testings.skip_when_no_network
    def test_get_sections(self):
        r = parsers.OrganizationReader("國立故宮博物院")

        self.assertIn(
            models.WikiSection(
                level=2,
                line="歷任首長",
                index=11,
            ),
            r.sections,
        )

    @testings.skip_when_no_network
    def test_get_director_section(self):
        r = parsers.OrganizationReader("國立故宮博物院")

        self.assertNotEqual("", r.directors_section)
        self.assertTrue(r.directors_section.startswith("<div"))
        self.assertTrue(r.directors_section.endswith("</div>"))

    @testings.skip_when_no_network
    def test_get_directors_table(self):
        r = parsers.OrganizationReader("國立故宮博物院")
        tables = r.directors_tables
        rows = [row.tolist() for _, row in tables[-1].iterrows()]

        self.assertTrue(["蕭宗煌" in row for row in rows])

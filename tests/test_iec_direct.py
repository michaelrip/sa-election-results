"""Direct-source IEC public CSV regression tests. No ESP feed is involved."""
import sys
import unittest
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
from import_iec_reports import (
    ImportErrorIEC, parse_csv, build_results, build_history, report_url
)

HEADER = ("Province,Municipality,Ward,VotingDistrict,BallotType,"
          "PartyName,TotalValidVotes\n")
SAMPLE = HEADER + (
    "Gauteng,JHB,79800001,32841266,Ward,DEMOCRATIC ALLIANCE,120\n"
    "Gauteng,JHB,79800001,32841266,Ward,AFRICAN NATIONAL CONGRESS,80\n"
    "Gauteng,JHB,79800001,32841266,PR,DEMOCRATIC ALLIANCE,200\n"
    "Gauteng,JHB,79800001,32841267,Ward,DEMOCRATIC ALLIANCE,60\n"
    "Gauteng,JHB,79800001,32841267,Ward,AFRICAN NATIONAL CONGRESS,40\n"
    "Gauteng,JHB,79800002,32841270,Ward,DEMOCRATIC ALLIANCE,30\n"
    "Gauteng,JHB,79800002,32841270,Ward,AFRICAN NATIONAL CONGRESS,70\n"
)

class IECDirectReportTests(unittest.TestCase):
    def test_2026_ward_ballot_isolated_from_pr(self):
        data = parse_csv(SAMPLE.encode(), "Johannesburg", 2026)
        self.assertEqual(data["total_votes"], 400)
        self.assertEqual(data["reported_vds"], 3)
        self.assertEqual(data["party_rows"][0],
                         {"name": "DA", "votes": 210, "share": 52.5})
        self.assertEqual(data["wards"][1]["valid_votes"], 300)
        self.assertEqual(data["wards"][1]["parties"][0]["votes"], 180)
        self.assertEqual(data["wards"][1]["parties"][0]["share"], 60.0)
        self.assertEqual(data["wards"][2]["parties"][0]["name"], "ANC")

    def test_historic_only_municipal_percentages(self):
        d = {"Johannesburg": parse_csv(SAMPLE.encode(), "Johannesburg", 2021)}
        old = build_history(d, {"Johannesburg": report_url(2021, 1091, "Johannesburg")})
        self.assertEqual(old["metros"]["Johannesburg"]["parties"]["DA"], 52.5)
        self.assertFalse(old["metros"]["Johannesburg"]["wards"])
        self.assertTrue(old["source_verified"])

    def test_reject_municipality_mismatch(self):
        with self.assertRaisesRegex(ImportErrorIEC, "different municipality"):
            parse_csv(SAMPLE.encode(), "Tshwane", 2026)

    def test_reject_duplicate_voting_district_party(self):
        with self.assertRaisesRegex(ImportErrorIEC, "Duplicate"):
            parse_csv((SAMPLE + SAMPLE.splitlines(keepends=True)[1]).encode(),
                      "Johannesburg", 2026)

    def test_reject_2021_id_as_live_event(self):
        d = {"Johannesburg": parse_csv(SAMPLE.encode(), "Johannesburg", 2026)}
        with self.assertRaisesRegex(ImportErrorIEC, "All four"):
            build_results(d, {"Johannesburg": "https://results.elections.org.za/"}, 1091)

    def test_reject_pr_only(self):
        with self.assertRaisesRegex(ImportErrorIEC, "No valid IEC Ward"):
            parse_csv(SAMPLE.replace(",Ward,", ",PR,").encode(), "Johannesburg", 2026)

    def test_report_urls_are_iec_only(self):
        self.assertEqual(
            report_url(2021, 1091, "Johannesburg"),
            "https://results.elections.org.za/home/LGEPublicReports/1091/"
            "Downloadable%20Party%20Results/GP/JHB.csv")
        with self.assertRaises(ImportErrorIEC):
            report_url(2020, 1091, "Johannesburg")

    def test_2021_cape_has_new_2026_wards_unmatched(self):
        text = HEADER + (
            "Western Cape,CPT,19100116,98761234,Ward,DA,100\n"
            "Western Cape,CPT,19100116,98761234,Ward,ANC,50\n"
        )
        data = parse_csv(text.encode(), "Cape Town", 2021)
        self.assertEqual(data["wards"][116]["valid_votes"], 150)
        self.assertFalse(data["wards"][118]["parties"])

    def test_requires_iec_report_schema(self):
        with self.assertRaisesRegex(ImportErrorIEC, "columns"):
            parse_csv(b"City,Party,Votes\nJHB,DA,100\n", "Johannesburg", 2026)

if __name__ == "__main__":
    unittest.main()

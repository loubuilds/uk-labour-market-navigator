"""Real official demand in complete journeys, with network blocked."""

import copy
import socket
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from uk_labour_market_navigator import demand, workflow
from uk_labour_market_navigator.market import collect_plan


class DemandJourneyTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.root = Path(self.tmp.name).resolve(strict=True)
        self.net = patch.object(socket.socket, "connect", side_effect=AssertionError("No network"))
        self.net.start()

    def tearDown(self):
        self.net.stop()
        self.tmp.cleanup()

    def start(self, places=None, workforce=True):
        return Path(
            workflow.start(
                "Help me compare the workforce and employer advertising for software developers.",
                "Prepare a hiring-location discussion",
                places or ["Reading"],
                "software developers",
                ["Pay and candidate availability remain unanswered."],
                self.root,
                include_demand=True,
                include_workforce=workforce,
            )["run"]
        )

    def draft(self, facts):
        return {
            "title": "Workforce structure alongside employer advertising",
            "opening": "Use the resident workforce and new-advert evidence together as context for the hiring discussion.",
            "sections": [
                {
                    "heading": "What the two sources add",
                    "text": "New advertising adds employer activity to the discussion. It does not establish unique vacancies or an easy hiring location; the sources cover different periods and populations.",
                    "fact_ids": [f["id"] for f in facts],
                }
            ],
            "next_questions": ["Would comparing another district help?"],
            "reviewed_by_host": True,
        }

    def ready(self, places=None, workforce=True):
        run = self.start(places, workforce)
        self.assertEqual(workflow.gather(run, True)["status"], "awaiting_synthesis")
        facts = workflow.read(run / "evidence.json")["facts"]
        self.assertEqual(workflow.publish(run, self.draft(facts))["status"], "ready")
        return run

    def test_combined_reading_contains_both_sources_and_correct_demand_date(self):
        run = self.ready()
        e = workflow.read(run / "evidence.json")
        self.assertEqual(e["demand"]["rows"][0]["new_adverts"], "338")
        self.assertEqual(e["census"]["rows"][0]["count"], "2030")
        html = (run / "brief.html").read_text(encoding="utf-8")
        self.assertIn("338", html)
        self.assertNotIn("Employer demand and competition for hires have not been assessed", html)
        ledger = html.split('<details id="fact-E06000038.new_adverts">')[1].split("</details></details>")[0]
        self.assertIn("When and who</strong><br>April to June 2026", ledger)
        self.assertNotIn("Census Day", ledger)
        for term in ("partly estimated", "November 2025", "April 2023", "not live vacancies", "not a live refresh"):
            self.assertIn(term, html)

    def test_demand_requires_acceptance_and_source_specific_boundary(self):
        run = self.start()
        self.assertEqual(workflow.gather(run, False)["status"], "scope_choice")
        self.assertFalse((run / "evidence.json").exists())
        plan = workflow.read(run / "plan.json")
        plan["demand_scope"]["places"][0]["version"] = "census2021_ltla_2022"
        workflow.write(run / "plan.json", plan)
        with self.assertRaises(ValueError):
            workflow.gather(run, True)

    def test_comparison_keeps_population_and_adverts_separate(self):
        run = self.ready(["Reading", "Cambridge"])
        e = workflow.read(run / "evidence.json")
        self.assertEqual([r["new_adverts"] for r in e["demand"]["rows"]], ["338", "705"])
        self.assertEqual(len(e["facts"]), 12)
        self.assertTrue(all(f["calculation"] == "publisher observation" for f in e["demand"]["facts"]))

    def test_suppressed_selected_demand_withholds_only_demand_component(self):
        run = self.start(["Reading", "Cambridge"])
        records, ref = demand.snapshot()
        records = copy.deepcopy(records)
        records["E07000008/2134"]["raw"] = "[x]"
        with patch.object(demand, "snapshot", return_value=(records, ref)):
            self.assertEqual(workflow.gather(run, True)["status"], "awaiting_synthesis")
            e = workflow.read(run / "evidence.json")
            self.assertEqual(e["demand"]["facts"], [])
            self.assertEqual(len(e["census"]["facts"]), 10)
            self.assertIn("Cambridge", str(e["gaps"]))
            result = workflow.publish(run, self.draft(e["facts"]))
            self.assertEqual(result["answerability"], "partial")

    def test_missing_london_borough_demand_preserves_reading_workforce(self):
        run = self.ready(["Reading", "Westminster"])
        e = workflow.read(run / "evidence.json")
        self.assertFalse(e["demand"]["facts"])
        self.assertTrue(e["census"]["facts"])
        self.assertIn("Westminster", str(e["gaps"]))

    def test_edinburgh_and_belfast_have_demand_without_census_substitution(self):
        run = self.ready(["Edinburgh", "Belfast"])
        e = workflow.read(run / "evidence.json")
        self.assertFalse(e["census"]["facts"])
        self.assertEqual([r["new_adverts"] for r in e["demand"]["rows"]], ["455", "489"])
        self.assertIn("Census occupation evidence unavailable", str(e["gaps"]))

    def test_demand_only_does_not_claim_missing_requested_census(self):
        run = self.ready(["Belfast"], False)
        e = workflow.read(run / "evidence.json")
        self.assertEqual(e["census"]["status"], "not_requested")
        self.assertEqual(len(e["facts"]), 1)
        self.assertNotIn("Resident workforce context unavailable", (run / "brief.html").read_text())

    def test_demand_tampering_including_quality_withdraws_saved_report(self):
        for field, value in (("value", "999999"), ("period", "2026-07"), ("quality", {})):
            run = self.ready()
            e = workflow.read(run / "evidence.json")
            e["demand"]["facts"][0][field] = value
            workflow.write(run / "evidence.json", e)
            seal = workflow.read(run / "evidence-seal.json")
            seal["evidence.json"] = workflow.digest(run / "evidence.json")
            workflow.write(run / "evidence-seal.json", seal)
            manifest = workflow.read(run / "manifest.json")
            manifest["hashes"]["evidence.json"] = seal["evidence.json"]
            workflow.write(run / "manifest.json", manifest)
            self.assertEqual(workflow.verify(run)["status"], "withdrawn")

    def test_installed_reference_and_pack_tampering_refused(self):
        with patch.object(demand, "RESOURCES", self.root):
            (self.root / "advertising-reference.json").write_text("{}")
            with self.assertRaises(ValueError):
                demand.snapshot()

    def test_invalid_scope_cannot_bypass_identity_validation_in_demand_only(self):
        run = self.start(["Belfast"], False)
        plan = workflow.read(run / "plan.json")
        plan["scope"]["places"][0]["label"] = "A made-up area"
        with self.assertRaises(ValueError):
            collect_plan(plan)

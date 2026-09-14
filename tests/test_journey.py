"""Real-source journeys and adverse cases; no network or original project imports."""

import copy
import socket
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from uk_labour_market_navigator import workflow
from uk_labour_market_navigator.evidence import collect, resolve
from uk_labour_market_navigator.report import render


class JourneyTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.base = Path(self.temp.name).resolve(strict=True)
        self.net = patch.object(socket.socket, "connect", side_effect=AssertionError("Network is not permitted"))
        self.net.start()
        self.draft = {
            "title": "Synthetic evidence fixture",
            "opening": "A dated occupation observation for a regression check.",
            "sections": [
                {
                    "heading": "Workforce evidence",
                    "text": "The source describes employed residents, not available candidates.",
                    "fact_ids": ["E06000038.count", "E06000038.share"],
                }
            ],
            "next_questions": ["Would another explicitly chosen district help?"],
            "reviewed_by_host": True,
        }

    def tearDown(self):
        self.net.stop()
        self.temp.cleanup()

    def start(self, places=None, role="software developers", gaps=None):
        started = workflow.start(
            "Help me prepare a developer hiring conversation in Reading.",
            "Prepare a useful hiring-manager conversation",
            places or ["Reading"],
            role,
            gaps or ["Current candidate availability is not measured."],
            self.base,
        )
        return Path(started["run"])

    def ready(self):
        run = self.start()
        workflow.gather(run, True)
        result = workflow.publish(run, self.draft)
        self.assertEqual(result["facts_verification"], "passed")
        return run

    def test_recruiter_has_scope_evidence_synthesis_report_and_followup(self):
        run = self.start()
        self.assertEqual(workflow.read(run / "state.json")["stage"], "scope_choice")
        self.assertFalse((run / "evidence.json").exists())
        self.assertEqual(workflow.gather(run, False)["status"], "scope_choice")
        self.assertFalse((run / "evidence.json").exists())
        result = workflow.gather(run, True)
        self.assertEqual(result["status"], "awaiting_synthesis")
        context = workflow.read(run / "synthesis-context.json")
        self.assertIn("hiring-manager", context["purpose"])
        result = workflow.publish(run, self.draft)
        self.assertEqual(result["answerability"], "partial")
        html = (run / "brief.html").read_text(encoding="utf-8")
        self.assertIn(self.draft["sections"][0]["text"], html)
        for text in (
            "2,030",
            "2.3%",
            "1.0%",
            "2.30x",
            "2.14 to 2.47",
            "Census Day",
            "available",
            "agent-authored",
            "<svg",
            "<table",
        ):
            self.assertIn(text, html)
        self.assertEqual(workflow.verify(run)["status"], "ready")
        self.assertEqual(result["next_questions"], self.draft["next_questions"])

    def test_published_values_and_rounding_are_source_specific(self):
        evidence = collect(resolve(["Reading", "Cambridge"], "software developers"))
        reading, cambridge = evidence["rows"]
        self.assertEqual((reading["count"], reading["share"], reading["concentration"]), ("2030", "2.3", "2.30"))
        self.assertEqual((cambridge["count"], cambridge["share"], cambridge["concentration"]), ("3165", "4.5", "4.50"))
        self.assertTrue(all(f["source_cells"] for f in evidence["facts"]))
        self.assertTrue(all(f["population"] == evidence["population"] for f in evidence["facts"]))

    def test_host_can_write_a_different_purposeful_synthesis(self):
        run = self.start()
        workflow.gather(run, True)
        draft = copy.deepcopy(self.draft)
        draft["title"] = "Questions for a workforce-planning workshop"
        draft["opening"] = "Use the workshop to agree what evidence would make a location discussion useful."
        result = workflow.publish(run, draft)
        text = Path(result["markdown"]).read_text()
        self.assertIn(draft["opening"], text)
        self.assertNotIn(self.draft["opening"], text)

    def test_comparison_and_followup_use_new_explicit_scope(self):
        first = self.ready()
        original = (first / "brief.html").read_bytes()
        second = self.start(["Reading", "Cambridge"])
        workflow.gather(second, True)
        draft = copy.deepcopy(self.draft)
        draft["title"] = "A workforce comparison for the discussion"
        draft["sections"][0]["fact_ids"].append("E07000008.count")
        result = workflow.publish(second, draft)
        self.assertIn("Cambridge", Path(result["report"]).read_text())
        self.assertEqual((first / "brief.html").read_bytes(), original)
        self.assertEqual(workflow.verify(first)["status"], "ready")

    def test_no_silent_place_or_role_guess(self):
        for places, role in [
            (["London"], "software developers"),
            (["Reading"], "senior specialists"),
            (["Reading", "Reading"], "software developers"),
        ]:
            with self.subTest(places=places, role=role), self.assertRaises(ValueError):
                resolve(places, role)

    def test_missing_selected_place_does_not_become_zero_or_disappear(self):
        evidence = collect(resolve(["Reading", "City of London"], "call centre operators"))
        self.assertEqual(evidence["facts"], [])
        self.assertEqual(evidence["rows"], [])
        self.assertIn("City of London", str(evidence["gaps"]))

    def test_invented_numeric_claim_or_fact_reference_cannot_publish(self):
        for change in ("number", "reference", "review"):
            run = self.start()
            workflow.gather(run, True)
            draft = copy.deepcopy(self.draft)
            if change == "number":
                draft["opening"] = "There are 999,999 available candidates."
            if change == "reference":
                draft["sections"][0]["fact_ids"] = ["invented.count"]
            if change == "review":
                draft["reviewed_by_host"] = False
            with self.subTest(change=change), self.assertRaises(ValueError):
                workflow.publish(run, draft)
            self.assertFalse((run / "brief.html").exists())

    def test_readable_surface_or_draft_tampering_withdraws_report(self):
        for name in ("brief.html", "brief.md", "synthesis.json", "evidence.json", "plan.json"):
            run = self.ready()
            (run / name).write_text("altered", encoding="utf-8")
            preserved = {p.name: p.read_bytes() for p in run.iterdir() if p.is_file()}
            result = workflow.verify(run)
            self.assertEqual(result["facts"], [])
            self.assertEqual(result["status"], "withdrawn")
            self.assertEqual(preserved, {p.name: p.read_bytes() for p in run.iterdir() if p.is_file()})

    def test_rewritten_hashes_cannot_approve_fabricated_evidence_or_html(self):
        for name in ("evidence.json", "brief.html"):
            run = self.ready()
            if name == "evidence.json":
                data = workflow.read(run / name)
                data["facts"][0]["value"] = "999999"
                workflow.write(run / name, data)
                seal = workflow.read(run / "evidence-seal.json")
                seal[name] = workflow.digest(run / name)
                workflow.write(run / "evidence-seal.json", seal)
            else:
                (run / name).write_text("A fabricated report", encoding="utf-8")
            manifest = workflow.read(run / "manifest.json")
            manifest["hashes"][name] = workflow.digest(run / name)
            workflow.write(run / "manifest.json", manifest)
            self.assertEqual(workflow.verify(run)["status"], "withdrawn")

    def test_installed_source_tampering_is_not_accepted(self):
        import uk_labour_market_navigator._source as source

        with patch.object(source, "RESOURCES", self.base):
            (self.base / "reference.json").write_text("{}")
            with self.assertRaises(ValueError):
                source.snapshot()

    def test_prose_is_escaped_and_never_claimed_machine_verified(self):
        run = self.start()
        workflow.gather(run, True)
        plan, evidence = workflow.checked_evidence(run)
        draft = copy.deepcopy(self.draft)
        draft["opening"] = "<script>alert('bad')</script>"
        html = render(plan, evidence, draft)["brief.html"]
        self.assertNotIn("<script>", html)
        self.assertIn("&lt;script&gt;", html)
        self.assertIn("agent-authored interpretation", html)

    def test_reader_sees_population_demand_gap_and_plain_source_explanation(self):
        from html.parser import HTMLParser

        class SourceLayout(HTMLParser):
            def __init__(self):
                super().__init__()
                self.depth = 0
                self.raw_depths = []

            def handle_starttag(self, tag, attrs):
                if tag == "details":
                    self.depth += 1
                if tag == "pre":
                    self.raw_depths.append(self.depth)

            def handle_endtag(self, tag):
                if tag == "details":
                    self.depth -= 1

        run = self.ready()
        html = (run / "brief.html").read_text(encoding="utf-8")
        cards = html.split('<div class="cards">', 1)[1].split("<figure>", 1)[0]
        self.assertIn("Residents employed as", cards)
        self.assertIn("Programmers and software development professionals", cards)
        self.assertIn("Of all employed residents locally", cards)
        self.assertIn("work as programmers and software development professionals", cards)
        self.assertLess(html.index("Hiring picture: incomplete"), html.index("2,030"))
        for label in (
            "Where the numbers come from",
            "What this means",
            "How we checked it",
            "How to build out the hiring picture",
            "Preview coverage",
        ):
            self.assertIn(label, html)
        parsed = SourceLayout()
        parsed.feed(html)
        self.assertTrue(parsed.raw_depths)
        self.assertTrue(all(depth == 2 for depth in parsed.raw_depths))
        self.assertEqual(parsed.depth, 0)

    def test_original_report_version_still_verifies_and_detects_tampering(self):
        from uk_labour_market_navigator._report_v1 import render as original_render

        run = self.ready()
        plan, evidence = workflow.checked_evidence(run)
        surfaces = original_render(plan, evidence, self.draft)
        for name, content in surfaces.items():
            (run / name).write_text(content, encoding="utf-8", newline="\n")
        manifest = workflow.read(run / "manifest.json")
        manifest["version"] = 1
        for name in surfaces:
            manifest["hashes"][name] = workflow.digest(run / name)
        workflow.write(run / "manifest.json", manifest)
        original = (run / "brief.html").read_bytes()
        self.assertEqual(workflow.verify(run)["status"], "ready")
        self.assertEqual((run / "brief.html").read_bytes(), original)
        (run / "brief.html").write_text("fabricated", encoding="utf-8")
        self.assertEqual(workflow.verify(run)["status"], "withdrawn")

    def test_unknown_or_boolean_report_version_is_withdrawn(self):
        for version in (99, True):
            run = self.ready()
            manifest = workflow.read(run / "manifest.json")
            manifest["version"] = version
            workflow.write(run / "manifest.json", manifest)
            self.assertEqual(workflow.verify(run)["status"], "withdrawn")

    def test_private_contact_or_secret_assignment_rejected(self):
        for value in ("Contact synthetic@example.invalid", "api_key=synthetic", r"C:\private\file"):
            with self.subTest(value=value), self.assertRaises(ValueError):
                workflow.public_text(value)


if __name__ == "__main__":
    unittest.main()

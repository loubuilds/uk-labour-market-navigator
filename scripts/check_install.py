"""Install the built wheel in an isolated environment, then exercise offline use."""

import subprocess
import sys
import tempfile
import venv
from pathlib import Path

SMOKE = r"""import contextlib, io, json, socket, sys
from pathlib import Path
import uk_labour_market_navigator
from uk_labour_market_navigator import workflow as w
from uk_labour_market_navigator.__main__ import main
assert Path(uk_labour_market_navigator.__file__).resolve().is_relative_to(Path(sys.prefix).resolve())
def blocked(*args, **kwargs):
    raise AssertionError("Network is prohibited in the official offline smoke")
socket.socket.connect = blocked
socket.create_connection = blocked
for command in (["setup"], ["help"]):
    with contextlib.redirect_stdout(io.StringIO()):
        assert main(command) == 0
cases = [("Reading software",["Reading"],"2134","software developers"),
         ("Compare districts",["Reading","Cambridge"],"2134","software developers"),
         ("Senior Java Developer",["Reading"],"2134","Senior Java Developer"),
         ("Scotland and NI",["Edinburgh","Belfast"],"2134","software developers"),
         ("Police pay",["Reading"],"3312","police officers")]
results=[]
for question,places,role,requested in cases:
    started=w.start(question,"Prepare a hiring discussion",places,role,[],Path.cwd()/"runs",release=True,requested_role=requested,include_demand=True,include_pay=True,include_context=True,include_hours=True)
    run=Path(started["run"])
    assert w.verify(run)["status"]=="incomplete"
    assert w.gather(run,True,True)["status"]=="awaiting_synthesis"
    evidence=w.read(run/"evidence.json")
    assert len(evidence["economic"]["facts"]) == 4
    assert evidence["context"]["facts"]
    assert evidence["hours"]["facts"]
    if "Belfast" in places:
        assert evidence["context"]["gaps"]
        assert all("claimant" in f["id"] for f in evidence["context"]["facts"])
    draft={"title":"A workforce discussion", "opening":"Read each source alongside its scope and unanswered requirements.","sections":[{"heading":"What the evidence adds","text":"These descriptive figures support a discussion; they do not diagnose a hiring outcome.","fact_ids":[f["id"] for f in evidence["facts"]]}],"next_questions":["Would another named district comparison help?"],"reviewed_by_host":True}
    outcome=w.publish(run,draft)
    assert outcome["status"]==w.verify(run)["status"]=="ready"
    if requested=="Senior Java Developer":
        assert any("Java" in g for g in outcome["gaps"]) and any("Seniority" in g for g in outcome["gaps"])
    if "Edinburgh" in places:
        assert not evidence["census"]["facts"] and evidence["demand"]["facts"] and evidence["pay"]["facts"]
    if role=="3312":
        assert not evidence["pay"]["facts"]
    results.append({"case":question,"status":outcome["status"],"answerability":outcome["answerability"]})
print(json.dumps({"status":"passed","isolated_install":True,"network_blocked":True,"python":sys.version.split()[0],"platform":sys.platform,"journeys":results},indent=2))
"""


def main(wheel):
    wheel = Path(wheel).resolve()
    with tempfile.TemporaryDirectory(prefix="uk-labour-market-navigator-install-") as temporary:
        # Resolve only the newly created, harness-owned temporary root.
        root = Path(temporary).resolve(strict=True)
        env = root / "environment"
        venv.EnvBuilder(with_pip=True).create(env)
        python = env / ("Scripts/python.exe" if sys.platform == "win32" else "bin/python")
        subprocess.run(
            [str(python), "-m", "pip", "install", "--no-index", "--no-deps", "--disable-pip-version-check", str(wheel)],
            cwd=root,
            check=True,
            capture_output=True,
            text=True,
        )
        command = env / (
            "Scripts/uk-labour-market-navigator.exe" if sys.platform == "win32" else "bin/uk-labour-market-navigator"
        )
        welcome = subprocess.run([str(command), "setup"], cwd=root, check=True, capture_output=True, text=True)
        assert "UK Labour Market Navigator" in welcome.stdout
        assert "Evidence-led labour market research companion for People and Talent practitioners." in welcome.stdout
        result = subprocess.run([str(python), "-I", "-c", SMOKE], cwd=root, check=True, capture_output=True, text=True)
        print(result.stdout.strip())


if __name__ == "__main__":
    main(sys.argv[1])

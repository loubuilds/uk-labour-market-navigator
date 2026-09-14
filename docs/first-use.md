# An easy first conversation

No research question ready? Say **"Show me what this can do."** Your assistant can walk through the fictional Sheffield customer-service example. For your own work, a role and town are enough to begin shaping a question.

## Guidance for coding agents

The following instructions help coding agents provide the first-use experience described above.

### Start with something useful

A new conversation can begin with:

> Would you like to see an example, or explore a hire you're working on? For your own hire, just tell me the role and town.

If the person has already asked a question or chosen the example, continue that route. Do not show a second menu, ask them to repeat themselves or start a research questionnaire.

For **"Show me an example"**, quietly check the bundled example with `python -m scripts.make_example --check`, using the discovered supported interpreter. Open the actual `examples/brief.html` and share a compact explanation of the fictional pay decision: one or two verified figures, what they contribute, and one practical next step. Copy figures from the checked output, not from memory. The synthetic scope is already declared; do not make the person confirm its statistical categories or create another research run simply to read it. End with an invitation to try their own role and town. Do not pretend the fictional stakeholder discussion happened with this user.

For **"Customer service advisers, Sheffield"**, propose a useful starting overview of the work in that place and invite the person to add any hiring or pay decision they have in mind. Do not make that an extra question they must answer before seeing the scope proposal. If the decision is already known, build on it directly. Explain any material broadening and get the user's explicit agreement before collecting a new investigation. The host does the occupation lookup; the person should not need to interpret a classification title.

### Keep setup in the background

Use [Python setup](python-setup.md) for a missing or old interpreter. One short explanation and the actual installer approval are enough; routine version discovery, validation and recovery are not a running commentary. Resume the original request afterwards. Contributor validation is separate from ordinary first use and should not become homework for a new user.

If installation blocks a first look, offer the [readable fictional example](../examples/brief.html) immediately. It needs no Python to open. Explain that it is the bundled demonstration; do not call it newly verified until its reproduction check has actually passed. A person can see what the tool offers while installation is arranged.

Use a few meaningful updates during research, then lead with what was learned. Read the selected checked facts before exploring full source records. A command's success is not evidence that every part of the person's question was answered.

### Make the first answer worth reading

- Give a relevant finding, its immediate meaning for the decision, and the report link. Keep definitions beside the figures that need them; leave the full ledger available on request.
- Describe specific comparisons instead of declaring a market tight or loose. A claimant proportion is neither a measure of available candidates for the role nor sufficient grounds for a pay recommendation.
- Keep possible explanations as questions to investigate. The report checks figures; the host must still review its own interpretation.
- Offer one easy continuation tied to the person's question, such as discussing the offer or comparing a named district. Do not introduce an unrelated role, place or second project.

## Contributor checks for conversational usability

Try a fresh conversation with "setup", "show me an example", a role and town, and a complete hiring question. Check that the assistant continues an already chosen route, needs no classification quiz, explains only material scope choices, and gives something useful before suggesting further work. Also try an old Python and a blocked local preview: the assistant should offer a concrete recovery without losing the question or claiming a check it did not perform.

Automated tests cover the welcome commands and evidence workflow. They cannot guarantee that every coding agent follows these conversational instructions; these human checks remain useful across hosts and models.

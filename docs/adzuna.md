# Optional recent advert research with Adzuna

The official research works without an Adzuna account. This experimental connection can add up to twenty recent matching adverts for a role and place, using your own permitted account access.

## Connect when you need it

1. Say **connect Adzuna**. Your assistant will help prepare the optional local dependency and link you to the [Adzuna developer site](https://developer.adzuna.com/overview).
2. Review the [permission guide](provider-permissions.md) for your intended use. API allowances and permission for ongoing workplace or client research are separate questions.
3. Open the masked terminal prompt using the command your assistant provides. Enter your own App ID and App Key there, never in chat.

Your credentials are stored in your computer's native credential store, separately from this repository. Connection does not make an API request or establish live access; you choose when to make the first search. You can leave Adzuna disconnected and return to it later.

## Ask a question

Tell your assistant the role and place you want to explore. It will propose the search distance and advert-age window for you to confirm before sending the query. Only those public filters and authentication go to Adzuna, not your conversation or research brief.

The results are a newest-first sample, with dates, links and attribution to [The Adzuna API](https://www.adzuna.co.uk/). They can help you inspect examples of advertised work and explicitly mentioned requirements. They do not measure the entire market, distinct competing employers, unique vacancies or available candidates. Search distance is not a commuting-time estimate.

Only explicitly stated, valid pay bounds are shown. Estimated or ambiguous pay is excluded. The reviewed response schema does not establish the pay period, so these figures are not combined or compared with annual official earnings. Open the linked advert for its full context.

Adverts stay separate from the checked official report. The connector does not save or export them, but results displayed in your coding agent can remain in its conversation history. Choose a host appropriate to your provider permission and privacy requirements. This build does not support publishing advert listings.

Each search makes one request and returns at most twenty records. It does not paginate or retry automatically. A failed provider search leaves official research available.

## Check or disconnect

Say **check my Adzuna connection** for local configuration status without a live request. Say **disconnect Adzuna** to remove this checkout's credentials and connection preferences. Disconnecting does not close your provider account or delete earlier conversations.

Disconnect before moving the checkout: the credential entry belongs to that folder's location. If removal cannot be confirmed, the assistant will explain the problem.

## Manual setup

If you prefer the terminal, install the optional dependency in the environment used for this project:

```sh
python -m pip install -e ".[adzuna]"
```

Then run this yourself in an interactive terminal:

```sh
python -m uk_labour_market_navigator adzuna connect --permission personal_research
```

Use `provider_permission` instead when you have Adzuna's permission for the intended organisational use. These are your attestations after reviewing the terms, not automatic classifications of your account.

Windows Credential Manager, macOS Keychain and Linux Secret Service are supported by the connector. An unavailable or unknown store is refused, with no plaintext fallback. The prompt rejects credentials passed through arguments or pipes. `adzuna status` and `adzuna disconnect` provide the controls described above.

For implementation details and testing limits, see the [connector contract](adzuna-connector.md).

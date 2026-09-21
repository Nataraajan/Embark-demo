# Embark-focused GTM planning demonstration

Independent interview prototype with entirely synthetic operating data, denominated in CAD. It is not an official Embark application or company financial forecast.

## Open

The local demo runs at **http://localhost:8507**.

On this workstation, double-click `OPEN-DEMO.cmd` if it is not running. On another machine, install Python and the libraries in `requirements.txt`, then run:

```text
python -m pip install -r requirements.txt
python -m streamlit run app.py --server.port 8507
```

## Included

- Executive KPIs with trends and budget comparisons. The long-view chart has been removed.
- Channel funnel, CAC, discounted cohort LTV and payback.
- Direct channel spend, conversion, contribution and lifetime assumptions, plus a 1.65% starting management fee.
- Exact funded-account variance bridge, expense variance and horizontal monthly schedules.
- Definitions, calculation explanations, limitations and source reference.
- A download of the current scenario's CSV schedules and JSON assumptions.
- A five-minute call walkthrough in `CALL-WALKTHROUGH.md`.

The first six months of 2026 are fixed simulated actuals. Scenario controls change July 2026 onward. The independent budget uses baseline drivers for the full period.

`planning_model.py` contains financial calculations. `app.py` provides the dashboard. `test_model.py` checks financial reconciliation, actuals isolation, budget isolation, scenario effects, zero-fee behavior, exact variance attribution and all app pages.

## Validation

Run `python -m pytest -q` with pytest installed. All 24 tests pass, covering the model, channel stages, diagnostic actuals, AI scenario calculation and app pages. A live Anthropic test also returned a calculated scenario preview.

## Source

[Embark Student Plan financial statements, June 30, 2025, Note 8](https://www.embark.ca/wp-content/uploads/2026/03/Embark-Student-Plan-FS-30Jun2025-English.pdf) establishes the management-fee and rebate structure. No numbers from those statements are represented as actual company inputs in this demonstration.

This prototype is separate from the existing CLAB application. No CLAB files have been changed.

## Simulated funnel performance

Open **Funnel performance**. Choose an acquisition month and channel. January–June 2026 cohorts are mature under a 60-day window as of September 21, 2026; July and August are incomplete and excluded from optimization. The page compares observed conversions with example targets and the prior cohort, then sizes a single-stage pilot using your current customer economics. Data is separately generated and is not the forecast historical ledger. Lead-record and scorecard downloads include reproducible synthetic IDs and dates.

Three additional tests verify cohort reconciliation, maturity, single-stage opportunities and page interaction.

Monthly trends now lead the Funnel performance page: spend and leads, stage conversion, funded accounts and CAC, plus an all-channel metric comparison. Only mature cohorts appear in trend charts; incomplete cohorts are labeled in the audit table. Choose a month beneath the charts to drill into its funnel.

## Channel-specific stages

The existing page layout and four channel groups are retained. Paid search/social use CPM and impression-to-lead conversion. Partnerships use directly entered monthly introductions, introduction-to-application conversion and application-to-funded conversion. Organic & referral uses visits, visit-to-enquiry, enquiry-to-application and application-to-funded conversion; the combined bucket assumes inbound website visits. Non-paid program costs feed CAC and operating expenses independently of acquisition volume. Impressions are not invented for these channels. Actuals charts and opportunity calculators use the same stage labels; conversion comparisons are restricted to matching stage definitions.


## AI model chat

Open the floating **Ask AI** button in the bottom-right on any page to ask about results, metric definitions or a scenario. Claude receives current assumptions, summarized forecast results and simulated diagnostic cohorts. Numeric scenario questions use the same financial engine as the dashboard and display auditable comparison results. Chat previews never overwrite inputs. Conversation history belongs to the current session; previous answers reflect inputs at the time asked.

Configure `ANTHROPIC_API_KEY` in the environment or Streamlit secrets. The default model is Claude Haiku 4.5; configure ANTHROPIC_MODEL in Streamlit secrets to change it. Saved Streamlit secrets take priority over environment variables. Connection settings are not shown to visitors. API charges are separate from ChatGPT/Codex credits. No key is included in downloads or this repository.

The palette uses violet, indigo and pale lavender inspired by Embark's public site. This is an independent illustrative demo.

## Hosting

See [DEPLOY.md](DEPLOY.md) for GitHub and Streamlit Community Cloud setup. Publish `app.py`, the calculation modules, `requirements.txt` and `.streamlit/config.toml`. Keep secrets out of GitHub. See the [official deployment guide](https://docs.streamlit.io/deploy/streamlit-community-cloud/deploy-your-app/deploy).

Revenue-only scope: service, sales and fixed overhead assumptions are removed. Revenue less marketing equals management-fee revenue minus channel spend; it is not operating profit. Revenue LTV discounts lifetime management fees without business-cost deductions. Pilot NPV subtracts only the incremental pilot cost. These definitions apply to the dashboard, AI scenarios and downloads.

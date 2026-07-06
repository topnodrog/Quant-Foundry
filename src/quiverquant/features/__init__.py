"""Derived graph features over the crypto ontology data (PLAN.md §4/§6, lever #2
in ``research/open-foundry-strategic-advantage.md``).

Relationship signals a flat per-source table can't produce: VC conviction
(how many distinct funds back a project) and fund co-investment structure
(which funds cluster into the same deals). Computed here directly from the
``vc_portfolio_backing`` rows the Firecrawl VC collector stored — the same
(fund → company) edges that populate the Open Foundry ``FundBacksProtocol``
graph — so the feature works with or without the Docker/AGE stack running.
"""

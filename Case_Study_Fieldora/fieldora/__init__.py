"""
Fieldora CSM Account Intelligence — a hybrid (deterministic + LLM) account-health engine and
weekly-brief generator, orchestrated with LangGraph.


The code is layered into four modules; this package re-exports their public API so callers can
keep using a single `import fieldora` surface (e.g. `fieldora.run_account`, `fieldora.Account`):


    core     paths · config/rubric · observability · models · trend
    sources  the data-acquisition layer (mode dispatch, connectors, fixtures, crosswalk, aggregation)
    agent    the LangGraph pipeline (llm · prompts · extraction · grounding · rubric · graph · evals)
    cli      presenter · reporting · the argparse runner


Run:  python -m fieldora [account] [--raw|--report|--evals|--build-fixtures|--build-snapshots]
"""


from fieldora import core, sources, agent, cli   # import submodules (tests target these directly)
from fieldora.core import *      # noqa: F401,F403 — deliberate public re-export
from fieldora.sources import *   # noqa: F401,F403
from fieldora.agent import *     # noqa: F401,F403
from fieldora.cli import *       # noqa: F401,F403


main = cli.main                  # console-script / `python -m fieldora` entry point
__version__ = "0.1.0"




"""
AidRadar Custom Tools.

Two Strands-compatible tools that form the backbone of the eligibility pipeline:

Tools:
    eligibility_checker — Evaluates all 8 programs via PolicyEngine + LIHEAP fallback
    application_finder  — Retrieves application URLs and document requirements

The eligibility_checker uses PolicyEngine (policyengine-us) as its calculation
engine for 7 programs, providing audited, up-to-date eligibility math. LIHEAP
uses a simple FPL-based fallback since PolicyEngine doesn't model it.

The application_finder reads from our JSON data files for state-specific
application URLs, required documents, and process notes — data that
PolicyEngine doesn't provide.
"""

def __getattr__(name):
    if name == "eligibility_checker":
        from src.tools.eligibility_checker import eligibility_checker
        return eligibility_checker
    if name == "application_finder":
        from src.tools.application_finder import application_finder
        return application_finder
    if name == "ALL_TOOLS":
        from src.tools.eligibility_checker import eligibility_checker
        from src.tools.application_finder import application_finder
        return [eligibility_checker, application_finder]
    raise AttributeError(f"module 'src.tools' has no attribute {name!r}")

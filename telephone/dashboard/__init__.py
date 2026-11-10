"""The dashboard: a local browser interface for running experiments and reading results.

`telephone dashboard` starts it. It is a FastAPI server bound to this machine plus a static
page with no build step, so it needs nothing beyond the Python install. It is separate from the
public website in web/, which stays static and never runs anything.
"""

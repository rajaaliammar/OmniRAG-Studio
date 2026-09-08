"""Allow ``python -m backend.eval`` to run the evaluation CLI."""

from backend.eval.eval_pipeline import main

raise SystemExit(main())

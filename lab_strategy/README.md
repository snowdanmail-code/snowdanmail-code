# v2.6 Poker Strategy Lab

Research-only, no real chips or connections to live poker applications. Generates hypothetical fold/check/call/bet decisions and evaluates simplified one-street chip EV. Includes value-betting and bluff candidate lines; conditions rely on INPUT estimates of fold equity, samples, position and blockers. This is **not a trained professional poker bot**, GTO solver, or evidence of profitability. It does **not** call OpenAI, change any Android runtime, or control 1win.

`make_gpt_brief(study)` generates JSON to be used in a future permitted ChatGPT analysis workflow; `validate_lab_choice()` accepts an offline hypothetical model answer but always returns `execution_allowed: false`. These laboratory materials are intentionally separate from `lab_auth/`, gameplay APIs, and Android screen controls.

```bash
PYTHONPATH=. python -m unittest discover -s lab_strategy/tests -p 'test_*.py' -v
```

Formulas intentionally simplify away rake, multi-street play, bet and raise responses, pot splits, showdown uncertainty and opponent model calibration. Do not use for financial decisions.

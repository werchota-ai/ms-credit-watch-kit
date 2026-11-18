"""Credit Watch - Azure Functions entry points.

  daily_check   timer (DAILY_CRON app setting): collect, alert, weekly/monthly reports on their days
  teams         HTTP, called by the Teams outgoing webhook ("@Credit Watch weekly"); answers at once, queues the work
  run_report    queue trigger: builds the requested report and posts it to the Teams channel
"""
import json
import logging
import os

import azure.functions as func

import engine
import reports
import teams
from collect import Tokens
from store import Store

app = func.FunctionApp()


def _cfg() -> dict:
    with open(os.path.join(os.path.dirname(__file__), "config.json"), encoding="utf-8") as f:
        return json.load(f)


def _store(tokens: Tokens) -> Store:
    return Store(tokens, account=os.environ["STATE_ACCOUNT"])


@app.timer_trigger(schedule="%DAILY_CRON%", arg_name="timer", run_on_startup=False, use_monitor=True)
def daily_check(timer: func.TimerRequest) -> None:
    tokens = Tokens()
    res = engine.scheduled(_cfg(), tokens, _store(tokens), os.environ.get("TEAMS_WEBHOOK_URL"))
    logging.info("credit-watch scheduled: %d alerts, %d errors, sent %s", len(res["alerts"]), len(res["errors"]), res["sent"])
    for e in res["errors"]:
        logging.warning("check failed: %s", e)


@app.route(route="teams", methods=["POST"], auth_level=func.AuthLevel.ANONYMOUS)
@app.queue_output(arg_name="job", queue_name="reports", connection="AzureWebJobsStorage")
def teams_command(req: func.HttpRequest, job: func.Out[str]) -> func.HttpResponse:
    body = req.get_body()
    if not teams.verify(os.environ.get("TEAMS_OUTGOING_SECRET", ""), body, req.headers.get("Authorization")):
        logging.warning("teams: rejected request with a missing or wrong signature")
        return func.HttpResponse("unauthorized", status_code=401)
    activity = json.loads(body or b"{}")
    cfg = _cfg()
    kind = teams.command(activity)
    if kind == "help":
        reply = reports.help_card(cfg)
    else:
        job.set(json.dumps({"kind": kind, "who": teams.who(activity)}))
        reply = reports.ack(cfg, teams.who(activity), kind)
    return func.HttpResponse(json.dumps(reply), mimetype="application/json")


@app.queue_trigger(arg_name="item", queue_name="reports", connection="AzureWebJobsStorage")
def run_report(item: func.QueueMessage) -> None:
    job = json.loads(item.get_body().decode())
    tokens = Tokens()
    res = engine.on_demand(_cfg(), tokens, _store(tokens), os.environ.get("TEAMS_WEBHOOK_URL"), job["kind"])
    logging.info("credit-watch on demand (%s, by %s): %d alerts, %d errors", job["kind"], job.get("who"),
                 len(res["alerts"]), len(res["errors"]))

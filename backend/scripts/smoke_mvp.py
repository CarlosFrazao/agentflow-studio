"""Smoke test funcional do MVP AgentFlow Studio contra a API viva."""

import json
import subprocess
import sys
import time
import urllib.request

BASE = "http://127.0.0.1:8128"


def req(method, path, token=None, body=None):
    headers = {"Content-Type": "application/json"}
    if token:
        headers["Authorization"] = f"Bearer {token}"
    data = json.dumps(body).encode() if body is not None else None
    r = urllib.request.Request(f"{BASE}{path}", data=data, headers=headers, method=method)
    try:
        with urllib.request.urlopen(r) as resp:
            raw = resp.read().decode()
            payload = json.loads(raw) if raw else {}
            return resp.status, payload
    except urllib.error.HTTPError as e:
        raw = e.read().decode()
        return e.code, json.loads(raw) if raw else {}


def main():
    # register (ou login se já existir do teste anterior)
    st, reg = req("POST", "/api/v1/auth/register", body={
        "email": "validacao@example.com",
        "password": "xK8m!vP2qL",
        "display_name": "Validacao",
    })
    if st == 409:
        st, reg = req("POST", "/api/v1/auth/login", body={
            "email": "validacao@example.com",
            "password": "xK8m!vP2qL",
        })
        print(f"login (register deu 409) -> {st} success={reg.get('success')}")
    else:
        print(f"register         -> {st} success={reg.get('success')}")
    if st not in (200, 201) or "data" not in reg:
        print("  body:", reg)
        return 1
    tok = reg["data"]["access_token"]

    # project
    st, proj = req("POST", "/api/v1/projects", token=tok, body={
        "name": "Validacao MVP", "description": "smoke",
    })
    print(f"create project   -> {st}")
    pid = proj["data"]["id"]

    # card
    st, card = req("POST", "/api/v1/cards", token=tok, body={
        "project_id": pid, "title": "Card smoke", "column": "backlog",
    })
    print(f"create card      -> {st}")
    cid = card["data"]["id"]

    # list cards
    st, lst = req("GET", f"/api/v1/cards?project_id={pid}", token=tok)
    print(f"list cards       -> {st} count={len(lst['data'])}")

    # dashboard
    st, dash = req("GET", "/api/v1/dashboard", token=tok)
    print(f"dashboard        -> {st} keys={list(dash.get('data', {}).keys())}")

    # run card (orquestrador)
    st, run = req("POST", f"/api/v1/cards/{cid}/run", token=tok)
    print(f"run card         -> {st}")

    # cleanup
    st, _ = req("DELETE", f"/api/v1/projects/{pid}", token=tok)
    print(f"delete project   -> {st}")
    return 0


if __name__ == "__main__":
    sys.exit(main())

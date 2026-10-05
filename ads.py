#!/usr/bin/env python3
"""Ad-for-time monetisation for HAMU-GPT.

The app is free to download and use, but **users** (never the owner) get a
tank of chat time that drains only while they are actually talking to a model.
When the tank empties they watch a short rewarded ad to refill it.

Design rules, in order of importance:

1. **Per-email, not per-machine.** Time is keyed by the lowercase email of the
   signed-in account, exactly like a website keys a session by account. Two
   people sharing one PC have two independent balances, and signing out does
   not carry time across accounts.

2. **The owner is exempt.** ``auth.is_admin()`` short-circuits every check here,
   so the owner never sees a timer, never sees an ad, and can never be locked
   out of his own app.

3. **Time is only ever granted for a *completed* ad.** ``grant_for_ad`` takes
   the elapsed seconds the UI actually counted and refuses anything that is not
   at least ``AD_SECONDS`` minus a small tolerance. Closing the ad early -
   Alt+F4, Task Manager, killing the app - grants nothing, because the grant is
   driven by the timer running to completion, not by the ad merely appearing.

4. **The tank only drains while chatting.** The UI tells us how many seconds of
   real conversation happened; we never drain on wall-clock time spent sitting
   on the interface.

5. **Watching is unlimited, its pace is not.** There is no daily cap on how many
   times a user may refill - only ``AD_MAX_PER_HOUR`` completed ads in any
   rolling ``AD_WINDOW_SECONDS``. Because the window rolls, watching 30 ads at
   12:59 does not buy 30 more at 13:01; the oldest watch must age out first.
   Enforced inside the lock in ``grant_for_ad``, so a stale client cannot slip
   past it.

Storage: ``%APPDATA%/HAMU-GPT/ads.json`` - a single dict keyed by email::

    {
      "someone@gmail.com": {
        "seconds": 1830.4,           # remaining tank, in seconds
        "granted_total": 5430.0,     # lifetime seconds earned
        "ads_watched": 12,           # completed ads
        "ads_started": 13,           # ads opened (13-12 = closed early)
        "signup_bonus": false,       # has the CLAIM button been used
        "watched_times": [1.7e9, ...],  # epoch of each completed ad (the window)
        "claim_started": 0.0,        # epoch an ad was opened, 0 when none
        "created_at": "...",
        "last_seen": "..."
      }
    }
"""
from __future__ import annotations

import json
import os
import threading
import time

import store

_lock = threading.Lock()

ADS_FILE = os.path.join(store.data_dir(), "ads.json")

# ---------------------------------------------------------------------------
# tunables - change these numbers and the whole policy follows
# ---------------------------------------------------------------------------
AD_SECONDS = 30                  # how long a rewarded ad runs
AD_REWARD_SECONDS = 5 * 60       # what one completed ad pays out: 5 minutes
# The signup gift. It is CLAIMED by the user from a button, not handed over
# automatically, so a new account genuinely starts at zero and the first thing
# it does is engage with the earn-time UI. 15 minutes is deliberately modest:
# it is a taster, and the intent is that people watch ads once it runs out.
SIGNUP_BONUS_SECONDS = 15 * 60   # the one-time signup gift: 15 minutes
WELCOME_BONUS_SECONDS = 0        # no separate welcome top-up any more
# What a brand-new account starts with: nothing. START_SECONDS is what the
# CLAIM button is worth, not what you are given on arrival.
START_SECONDS = SIGNUP_BONUS_SECONDS

# --- rate limit: unlimited ads, but only so many per hour ------------------
# Watching is unlimited in the sense that there is no daily cap on how many
# times you may refill - only a pace limit. 30 ads x 30s = 15 minutes of ads
# per hour, and at 5 minutes per ad that is 150 minutes of chat time an hour
# at most. A rolling window is used rather than a fixed clock hour, so the
# limit cannot be gamed by watching 30 ads at 12:59 and 30 more at 13:01.
AD_MAX_PER_HOUR = 30             # at most 30 completed ads in any 60 minutes
AD_WINDOW_SECONDS = 60 * 60      # the rolling window
# How long before an "ad in progress" claim goes stale and is ignored, so a
# crashed app cannot leave a claim sitting there forever.
AD_CLAIM_TTL = 5 * 60

# How many completed-ad timestamps to keep per account. 30/hour means at most
# 720/day, so 2,000 comfortably covers the window plus a day of history.
_KEEP_TIMES = 2000

# An ad counts as complete if the UI counted at least this much of it. The UI
# counts whole elapsed seconds, so this only absorbs a dropped frame at the
# very end of the countdown - it is far too small to skip any real part of a
# 30-second ad.
AD_TOLERANCE = 1.0

EMPTY = {
    "seconds": 0.0,
    "granted_total": 0.0,
    "ads_watched": 0,
    "ads_started": 0,
    "signup_bonus": False,
    "created_at": "",
    "last_seen": "",
    "watched_times": [],      # epoch seconds of each completed ad, for the limit
    "claim_started": 0.0,     # epoch seconds an ad was opened (not yet paid)
}


# ---------------------------------------------------------------------------
# helpers
# ---------------------------------------------------------------------------
def _key(email: str) -> str:
    return (email or "").strip().lower()


def _now() -> str:
    return time.strftime("%Y-%m-%d %H:%M:%S")


def _read_all() -> dict:
    """Every account's tank.

    Goes through store, so a hosted instance reads from its key-value store
    rather than from a file a cold start would have wiped - chat time has to
    survive a restart just like the account itself.
    """
    d = store._read(ADS_FILE, {})
    return d if isinstance(d, dict) else {}


def _write_all(d: dict):
    store._write(ADS_FILE, d)


def _num(v, default=0.0) -> float:
    """Coerce anything a hand-edited file might hold into a float."""
    if isinstance(v, bool):
        return default
    try:
        f = float(v)
    except Exception:
        return default
    if f != f or f in (float("inf"), float("-inf")):   # NaN / inf
        return default
    return f


def _int(v, default=0) -> int:
    try:
        return int(v)
    except Exception:
        return default


def _rec(all_: dict, email: str) -> dict:
    """Fetch (creating if needed) the record for one email.

    Every numeric field is coerced on the way out, so a hand-edited
    ``ads.json`` can never raise inside a request.
    """
    k = _key(email)
    r = all_.get(k)
    if not isinstance(r, dict):
        r = dict(EMPTY)
        r["created_at"] = _now()
        all_[k] = r
    # backfill anything a hand-edited file is missing, and sanitise the rest
    r["seconds"] = max(0.0, _num(r.get("seconds")))
    r["granted_total"] = max(0.0, _num(r.get("granted_total")))
    r["ads_watched"] = max(0, _int(r.get("ads_watched")))
    r["ads_started"] = max(0, _int(r.get("ads_started")))
    r["signup_bonus"] = bool(r.get("signup_bonus"))
    r["claim_started"] = max(0.0, _num(r.get("claim_started")))
    # the rolling-window history: a list of epoch seconds, nothing else
    wt = r.get("watched_times")
    if not isinstance(wt, list):
        wt = []
    clean = []
    for x in wt:
        v = _num(x, -1.0)
        if v > 0:
            clean.append(v)
    clean.sort()
    r["watched_times"] = clean[-_KEEP_TIMES:]
    r.setdefault("created_at", "")
    r.setdefault("last_seen", "")
    return r


def _is_admin() -> bool:
    try:
        import auth                       # lazy: avoids a circular import
        return bool(auth.is_admin())
    except Exception:
        return False


def _current_email() -> str:
    """The signed-in address, or '' when there is no live session.

    Honours the signed-out flag: an account that deliberately signed out is
    not a session, so the ad system goes inert rather than gating a ghost.
    """
    try:
        import auth
        if not auth.is_signed_in():
            return ""
        return _key((auth.get_account() or {}).get("email"))
    except Exception:
        return ""


# ---------------------------------------------------------------------------
# public API
# ---------------------------------------------------------------------------
def _hosted() -> bool:
    """Running as a hosted web service rather than the desktop app?"""
    try:
        import store
        return bool(store.hosted())
    except Exception:
        return False


def enabled() -> bool:
    """Is the ad-for-time system in play at all right now?

    It is off for the owner, off when nobody is signed in (the sign-in gate is
    already blocking the app at that point), and off on a HOSTED build.

    Why the hosted build is exempt: this system pays the user in chat time for
    watching an ad, which is incentivized traffic - explicitly prohibited by
    the ad networks that serve websites (Adsterra and HilltopAds both name it).
    A website showing rewarded ads would be banned and lose its earnings, so on
    the web build chat is simply free and the site earns from ordinary display
    ads instead. The desktop app keeps the reward system: it is not served by
    those networks.
    """
    if _is_admin():
        return False
    if _hosted():
        return False
    return bool(_current_email())


def seconds_left(email: str | None = None) -> float:
    e = _key(email) if email else _current_email()
    if not e:
        return 0.0
    return max(0.0, _num(_rec(_read_all(), e).get("seconds")))


def can_chat(email: str | None = None) -> bool:
    """May this account send a message right now?

    True for the owner, and True whenever the ad system is inactive - which
    covers nobody being signed in (the sign-in gate is already blocking the app
    and a phantom gate here would refuse the pre-session calls that must work),
    and the hosted build (see ``enabled``).
    """
    if _is_admin():
        return True
    if not enabled():
        return True
    e = _key(email) if email else _current_email()
    if not e:
        return True                     # no session -> the ad system is inert
    return seconds_left(e) > 0.0


def needs_ad(email: str | None = None) -> bool:
    if _is_admin():
        return False
    if not enabled():
        return False
    e = _key(email) if email else _current_email()
    if not e:
        return False
    return seconds_left(e) <= 0.0


# ---------------------------------------------------------------------------
# the rolling-hour pace limit
# ---------------------------------------------------------------------------
def _in_window(r: dict, now: float) -> list:
    """The completed-ad timestamps that still sit inside the rolling hour."""
    cutoff = now - AD_WINDOW_SECONDS
    return [t for t in (r.get("watched_times") or []) if _num(t) > cutoff]


def ads_used_this_hour(email: str | None = None) -> int:
    """How many ads this account has completed in the last 60 minutes."""
    if _is_admin():
        return 0
    e = _key(email) if email else _current_email()
    if not e:
        return 0
    r = _rec(_read_all(), e)
    return len(_in_window(r, time.time()))


def ads_left_this_hour(email: str | None = None) -> int:
    """How many of the 30 this hour's allowance are still unspent."""
    if _is_admin():
        return AD_MAX_PER_HOUR
    return max(0, AD_MAX_PER_HOUR - ads_used_this_hour(email))


def seconds_until_next_ad(email: str | None = None) -> float:
    """Seconds until one slot frees up. 0 when a slot is open right now.

    The window is rolling, so the oldest watch in it is the one that has to
    age out before another ad may be watched.
    """
    if _is_admin():
        return 0.0
    e = _key(email) if email else _current_email()
    if not e:
        return 0.0
    now = time.time()
    win = _in_window(_rec(_read_all(), e), now)
    if len(win) < AD_MAX_PER_HOUR:
        return 0.0
    return max(0.0, (min(win) + AD_WINDOW_SECONDS) - now)


def can_watch_ad(email: str | None = None) -> bool:
    if _is_admin():
        return True
    if _hosted():
        return False
    return ads_left_this_hour(email) > 0


def ads_used_last_24h(email: str | None = None) -> int:
    """Ads completed in the rolling 24 hours - the real daily figure.

    Because the hourly cap is a rolling window, someone watching flat out can
    clear at most 30 an hour, i.e. 720 in a day. This counts what actually
    happened rather than assuming they watched at the cap.
    """
    if _is_admin():
        return 0
    e = _key(email) if email else _current_email()
    if not e:
        return 0
    cutoff = time.time() - 24 * 60 * 60
    return len([t for t in (_rec(_read_all(), e).get("watched_times") or [])
                if _num(t) > cutoff])


def ensure_account(email: str) -> dict:
    """Create the record on first signup. Grants NOTHING.

    The signup gift is *claimed* by the user (see ``claim_signup_bonus``), not
    handed over here. That is the whole point of the CLAIM button: a new
    account starts at zero, and the first interaction is with the earn-time UI
    rather than a balance quietly appearing.

    ``signup_bonus`` therefore means "has the gift been claimed", and stays
    false until the user presses the button. Logging in again never grants it -
    only the claim does, and only once.
    """
    k = _key(email)
    if not k:
        return dict(EMPTY)
    with _lock:
        all_ = _read_all()
        r = _rec(all_, k)
        r["last_seen"] = _now()
        _write_all(all_)
        return dict(r)


def claim_signup_bonus(email: str | None = None) -> dict:
    """Pay the one-time signup gift. Once per account, for ever.

    Returns ``just_claimed`` so the caller can tell the difference between
    "you just got it" and "you already had it" - the toast must fire on the
    first and never on the second.
    """
    if _is_admin():
        return {"ok": True, "granted": 0, "already": True, "just_claimed": False,
                "reason": "admin", "seconds": 0.0}

    e = _key(email) if email else _current_email()
    if not e:
        return {"ok": False, "granted": 0, "already": False,
                "just_claimed": False, "seconds": 0.0,
                "error": "Not signed in."}

    with _lock:
        all_ = _read_all()
        r = _rec(all_, e)

        if r.get("signup_bonus"):
            # Already taken. Deliberately a success: pressing the button again
            # is not an error, it just has nothing left to give.
            r["last_seen"] = _now()
            _write_all(all_)
            return {"ok": True, "granted": 0, "already": True,
                    "just_claimed": False, "minutes": 0,
                    "seconds": _num(r.get("seconds"))}

        r["signup_bonus"] = True
        r["seconds"] = _num(r.get("seconds")) + START_SECONDS
        r["granted_total"] = _num(r.get("granted_total")) + START_SECONDS
        r["last_seen"] = _now()
        _write_all(all_)
        return {"ok": True, "granted": START_SECONDS,
                "minutes": START_SECONDS // 60,
                "already": False, "just_claimed": True,
                "seconds": _num(r.get("seconds"))}


def grant_for_ad(elapsed: float, email: str | None = None) -> dict:
    """Pay out for a rewarded ad the UI watched to the end.

    ``elapsed`` is what the client actually counted on screen. Anything short
    of ``AD_SECONDS - AD_TOLERANCE`` is refused - that is the anti-glitch rule:
    an ad that was closed, skipped, or interrupted never lands here with a
    complete count, and even if a hand-crafted call did, we do not pay it.
    """
    if _is_admin():
        return {"ok": True, "granted": 0, "reason": "admin", "seconds": 0.0}
    if _hosted():
        return {"ok": False, "granted": 0, "seconds": 0.0,
                "error": "Rewarded ads are not used on the web build."}

    e = _key(email) if email else _current_email()
    if not e:
        return {"ok": False, "error": "Not signed in."}

    try:
        el = float(elapsed or 0.0)
    except Exception:
        el = 0.0

    if el < (AD_SECONDS - AD_TOLERANCE):
        with _lock:
            all_ = _read_all()
            r = _rec(all_, e)
            r["ads_started"] = int(r.get("ads_started", 0)) + 1
            r["claim_started"] = 0.0
            _write_all(all_)
        return {"ok": False, "granted": 0,
                "error": "The ad was not watched to the end — no time granted."}

    with _lock:
        all_ = _read_all()
        r = _rec(all_, e)
        now = time.time()

        # Check the pace limit BEFORE paying, and again inside the lock, so two
        # tabs cannot both slip past a stale count.
        win = _in_window(r, now)
        if len(win) >= AD_MAX_PER_HOUR:
            r["watched_times"] = win
            r["claim_started"] = 0.0
            _write_all(all_)
            wait = max(0.0, (min(win) + AD_WINDOW_SECONDS) - now)
            return {"ok": False, "granted": 0, "limited": True,
                    "wait_seconds": wait,
                    "left_this_hour": 0,
                    "error": "You have watched all "
                             f"{AD_MAX_PER_HOUR} ads for this hour. "
                             "Try again in a little while."}

        win.append(now)
        r["watched_times"] = win[-_KEEP_TIMES:]
        r["seconds"] = _num(r.get("seconds")) + AD_REWARD_SECONDS
        r["granted_total"] = _num(r.get("granted_total")) + AD_REWARD_SECONDS
        r["ads_watched"] = int(r.get("ads_watched", 0)) + 1
        r["ads_started"] = int(r.get("ads_started", 0)) + 1
        r["claim_started"] = 0.0
        r["last_seen"] = _now()
        _write_all(all_)
        return {"ok": True, "granted": AD_REWARD_SECONDS,
                "seconds": r["seconds"],
                "minutes": round(r["seconds"] / 60.0, 1),
                "left_this_hour": max(0, AD_MAX_PER_HOUR - len(win))}


def begin_ad(email: str | None = None) -> dict:
    """Mark that an ad was opened. Purely bookkeeping - grants nothing.

    Recorded so the app can show the claim in the owner's board, and so a
    crashed watch leaves a trace that ages out on its own.
    """
    if _is_admin():
        return {"ok": True, "reason": "admin"}
    if _hosted():
        return {"ok": False, "error": "Rewarded ads are not used on the web build."}
    e = _key(email) if email else _current_email()
    if not e:
        return {"ok": False, "error": "Not signed in."}
    if not can_watch_ad(e):
        return {"ok": False, "limited": True, "left_this_hour": 0,
                "wait_seconds": seconds_until_next_ad(e),
                "error": "Hourly ad limit reached."}
    with _lock:
        all_ = _read_all()
        r = _rec(all_, e)
        r["claim_started"] = time.time()
        r["last_seen"] = _now()
        _write_all(all_)
    return {"ok": True, "left_this_hour": ads_left_this_hour(e)}


def consume(seconds: float, email: str | None = None) -> dict:
    """Drain the tank by the seconds of real conversation that just happened.

    Never goes below zero, and never touches the owner.
    """
    if _is_admin():
        return {"ok": True, "seconds": 0.0, "drained": 0.0}

    e = _key(email) if email else _current_email()
    if not e:
        return {"ok": False, "error": "Not signed in."}

    try:
        d = max(0.0, float(seconds or 0.0))
    except Exception:
        d = 0.0
    if d <= 0.0:
        return {"ok": True, "seconds": seconds_left(e), "drained": 0.0}

    with _lock:
        all_ = _read_all()
        r = _rec(all_, e)
        before = _num(r.get("seconds"))
        after = max(0.0, before - d)
        r["seconds"] = after
        r["last_seen"] = _now()
        _write_all(all_)
        return {"ok": True, "seconds": after, "drained": before - after}


def reset(email: str | None = None) -> dict:
    """Owner tool: wipe one account's tank (or all of them when email is None)."""
    with _lock:
        if email:
            all_ = _read_all()
            all_.pop(_key(email), None)
            _write_all(all_)
        else:
            _write_all({})
    return {"ok": True}


# ---------------------------------------------------------------------------
# status - one call the UI can poll on a timer
# ---------------------------------------------------------------------------
def _base_status() -> dict:
    """The shape every status reply shares - keeps the three branches honest."""
    return {
        "ad_seconds": AD_SECONDS,
        "reward_seconds": AD_REWARD_SECONDS,
        "reward_minutes": AD_REWARD_SECONDS // 60,
        "start_minutes": int(START_SECONDS / 60),
        "welcome_extra_minutes": int(WELCOME_BONUS_SECONDS / 60),
        "base_minutes": int(SIGNUP_BONUS_SECONDS / 60),
        # the one-time signup gift, which the user claims from a button
        "signup_bonus_seconds": SIGNUP_BONUS_SECONDS,
        "signup_bonus_minutes": SIGNUP_BONUS_SECONDS // 60,
        # Default: no claim button. The signed-in branch below sets the real
        # values; the owner branch turns it off because he never sees any of
        # this, and the signed-out / hosted branches have nobody to claim it.
        "signup_bonus_claimed": False,
        "signup_bonus_available": False,
        "max_ads_per_hour": AD_MAX_PER_HOUR,
        "ad_minutes_per_hour": (AD_MAX_PER_HOUR * AD_SECONDS) // 60,
        "chat_minutes_per_hour": (AD_MAX_PER_HOUR * AD_REWARD_SECONDS) // 60,
        # 24 rolling hours is 24 windows of an hour, hence 24 x the hourly cap.
        "max_ads_per_day": AD_MAX_PER_HOUR * 24,
        "ads_used_this_hour": 0,
        "ads_left_this_hour": AD_MAX_PER_HOUR,
        "ads_used_last_24h": 0,
        "limited": False,
        "next_ad_in": 0,
    }


def status(email: str | None = None) -> dict:
    """Everything the interface needs to draw the timer and the paywall."""
    if _is_admin():
        d = _base_status()
        d.update({
            "ok": True, "enabled": False, "is_admin": True,
            "seconds": 0.0, "minutes": 0.0, "needs_ad": False,
            "can_chat": True, "ads_watched": 0, "granted_total": 0.0,
            "signup_bonus": False, "email": "",
            "signup_bonus_claimed": True, "signup_bonus_available": False,
        })
        return d

    if _hosted():
        # The hosted build has no ad-for-time system at all - rewarded ads are
        # prohibited there. Report it as OFF so the UI hides the whole thing,
        # and report chat as free.
        d = _base_status()
        d.update({"ok": True, "enabled": False, "is_admin": False,
                  "hosted": True,
                  "seconds": 0.0, "minutes": 0.0, "needs_ad": False,
                  "can_chat": True, "ads_watched": 0, "granted_total": 0.0,
                  "signup_bonus": False,
                  "email": _key(email) if email else _current_email()})
        return d

    e = _key(email) if email else _current_email()
    if not e:
        d = _base_status()
        d.update({"ok": True, "enabled": False, "is_admin": False,
                  "seconds": 0.0, "minutes": 0.0, "needs_ad": False,
                  "can_chat": False, "ads_watched": 0, "granted_total": 0.0,
                  "signup_bonus": False, "email": ""})
        return d

    r = _rec(_read_all(), e)
    secs = _num(r.get("seconds"))
    now = time.time()
    used = len(_in_window(r, now))
    left = max(0, AD_MAX_PER_HOUR - used)
    wait = 0.0
    if left <= 0:
        win = _in_window(r, now)
        if win:
            wait = max(0.0, (min(win) + AD_WINDOW_SECONDS) - now)

    d = _base_status()
    d.update({
        "ok": True,
        "enabled": True,
        "is_admin": False,
        "email": e,
        "seconds": secs,
        "minutes": round(secs / 60.0, 1),
        "needs_ad": secs <= 0.0,
        "can_chat": secs > 0.0,
        "ads_watched": _int(r.get("ads_watched")),
        "ads_started": _int(r.get("ads_started")),
        "granted_total": _num(r.get("granted_total")),
        "signup_bonus": bool(r.get("signup_bonus")),
        # the CLAIM button: available until taken, CLAIMED for ever after
        "signup_bonus_claimed": bool(r.get("signup_bonus")),
        "signup_bonus_available": not bool(r.get("signup_bonus")),
        "ads_used_this_hour": used,
        "ads_left_this_hour": left,
        "ads_used_last_24h": len([t for t in (r.get("watched_times") or [])
                                  if _num(t) > now - 24 * 60 * 60]),
        "limited": left <= 0,
        "next_ad_in": int(wait + 0.999) if wait > 0 else 0,
        "path": ADS_FILE,
    })
    return d


def fmt_mmss(seconds: float) -> str:
    """1500.4 -> '25:00'. Truncates, so the number only drops when it truly has.

    Rounding up here would show 25:01 for most of the last second, which looks
    like time was handed back. Truncation is the honest direction.
    """
    s = int(max(0.0, float(seconds or 0.0)))
    return f"{s // 60}:{s % 60:02d}"

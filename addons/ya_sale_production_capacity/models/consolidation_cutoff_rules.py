"""Pure date-slot clock contract; no ORM, scheduler or releases.

Defaults reflect owner freeze. Settings can supply an alternative validated
schedule. Unknown SO cutoff never authorizes PP2. Existing S2/S3 admission
before dispatch remains an explicit transitional rule, not a final cutoff.
"""
from datetime import date, datetime, time, timedelta
from zoneinfo import ZoneInfo

WIB=ZoneInfo("Asia/Jakarta")
DISPATCH={"S1":time(5),"S2":time(9),"S3":time(11)}
DEFAULT_POLICY={
    "ro_days_before":2,"ro_minute":8*60,
    "so":{"S1":{"days_before":1,"minute":15*60},"S2":None,"S3":None},
    "mo2_delay_minutes":30,
}


def _integer(n,lo,hi,name):
    if type(n) is not int or not lo<=n<=hi:
        raise ValueError("Invalid "+name)
    return n


def _deadline(day,days,minute):
    days=_integer(days,0,365,"days before")
    minute=_integer(minute,0,1439,"minute of day")
    return datetime.combine(day-timedelta(days=days),time(minute//60,minute%60),tzinfo=WIB)


def schedule(day,slot,policy):
    if type(day) is not date or slot not in DISPATCH:
        raise ValueError("Invalid delivery date/slot")
    if set(policy)!={"ro_days_before","ro_minute","so","mo2_delay_minutes"} or set(policy["so"])!=set(DISPATCH):
        raise ValueError("Invalid cutoff policy")
    ro=_deadline(day,policy["ro_days_before"],policy["ro_minute"])
    dispatch=datetime.combine(day,DISPATCH[slot],tzinfo=WIB)
    delay=_integer(policy["mo2_delay_minutes"],0,1440,"MO2 release delay")
    if ro>=dispatch:
        raise ValueError("RO cutoff must precede dispatch")
    so=None
    release=None
    spec=policy["so"][slot]
    if spec is not None:
        if set(spec)!={"days_before","minute"}:
            raise ValueError("Invalid SO cutoff")
        so=_deadline(day,spec["days_before"],spec["minute"])
        release=so+timedelta(minutes=delay)
        if not ro<=so<dispatch or release>=dispatch:
            raise ValueError("SO cutoff/release must follow RO cutoff and precede dispatch")
    return dict(ro_cutoff=ro,so_cutoff=so,pp2_earliest=release,dispatch=dispatch)


def clock_state(day,slot,now,policy):
    if not isinstance(now,datetime) or now.tzinfo is None or now.utcoffset() is None:
        raise ValueError("Timezone-aware clock required")
    now=now.astimezone(WIB)
    s=schedule(day,slot,policy)
    dispatch_passed=now>=s["dispatch"]
    ro_closed=now>=s["ro_cutoff"]
    so_known=s["so_cutoff"] is not None
    so_closed=so_known and now>=s["so_cutoff"]
    return dict(**s,ro_closed=ro_closed,so_cutoff_configured=so_known,
        so_closed=so_closed,dispatch_passed=dispatch_passed,
        ro_admission_allowed=not ro_closed and not dispatch_passed,
        so_admission_allowed=not so_closed and not dispatch_passed,
        pp1_clock_ready=ro_closed and not dispatch_passed,
        pp2_clock_ready=so_known and now>=s["pp2_earliest"] and not dispatch_passed)

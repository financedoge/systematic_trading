import re, json
d = json.load(open(r'research_tmp\classify.json'))
cs = {int(k): v for k, v in d['cs'].items()}
impl = d['impl']; strict = d['strict_ts']

import importlib.util
spec = importlib.util.spec_from_file_location("c", r"research_tmp\classify.py")
# re-declare formulas by exec'ing only the F dict part
src = open(r'research_tmp\classify.py', encoding='utf-8').read()
Fsrc = src.split('assert len(F) == 101')[0]
ns = {}
exec(Fsrc, ns)
F = ns['F']

def strip_ts(s):
    return re.sub(r'\b(ts|Ts)_(rank|min|max|argmax|argmin)\b', 'TSOP', s)

def match_paren(s, i):
    depth = 0
    for j in range(i, len(s)):
        if s[j] == '(': depth += 1
        elif s[j] == ')':
            depth -= 1
            if depth == 0: return j
    return -1

def outer_cs(a):
    """Return name if the whole expression is <sign>*[0-]* CSOP(EXPR) [ +/- const], else None."""
    s = strip_ts(F[a]).strip()
    for _ in range(6):
        s0 = s
        s = s.strip()
        while s.startswith('(') and match_paren(s, 0) == len(s) - 1:
            s = s[1:-1].strip()
        s = re.sub(r'^0\s*-\s*', '', s)
        s = re.sub(r'^\(?\s*-1\s*\*\s*', '', s).strip()
        s = re.sub(r'^1\s*\*\s*', '', s).strip()
        if s == s0: break
    m = re.match(r'(rank|scale|indneutralize)\s*\(', s, re.I)
    if not m: return None
    j = match_paren(s, m.end() - 1)
    if j == -1: return None
    tail = s[j+1:].strip()
    if tail == '' or re.fullmatch(r'[-+]\s*[\d.]+', tail) or re.fullmatch(r'\*\s*-1', tail):
        return m.group(1).lower()
    return None

tierB = [a for a in sorted(F) if cs[a] == 1 and outer_cs(a)]
tierB_impl = [a for a in tierB if a in impl]
print("Tier B (single CS op applied as final normalisation):", len(tierB))
print("  ", [(a, outer_cs(a)) for a in tierB])
print("Tier B implementable:", len(tierB_impl), tierB_impl)
print()

# Tier C: CS used inside a time-series operator over a CS input (rank stays inside), i.e.
# exactly one CS op nested inside corr/ts_rank/cov. -> "CS-quantised TS"
tierC = [a for a in sorted(F) if cs[a] == 1 and a not in tierB and a not in strict]
print("Tier C (single CS op nested inside a TS operator):", len(tierC), tierC)
print("Tier C implementable:", [a for a in tierC if a in impl])
print()

mixed = [a for a in sorted(F) if cs[a] >= 2]
print("Tier D (>=2 CS ops; CS structurally embedded / multiplicative):", len(mixed))
print("Tier D implementable:", [a for a in mixed if a in impl])
print()

# multiplicative CS x TS mixing among cs==1
print("cs==1 but NOT outer-wrapper and NOT nested-only:")
for a in sorted(F):
    if cs[a] == 1 and a not in tierB and a not in tierC:
        print("   ", a, F[a][:120])
print()

print("=== FINAL TIERING ===")
print("Tier A strict TS      :", len(strict), strict)
print("Tier B outer-wrapper  :", len(tierB), tierB)
print("A+B                   :", len(strict) + len(tierB))
print("Tier C/D structurally CS:", 101 - len(strict) - len(tierB))
print()
allTSlike = sorted(set(strict) | set(tierB))
print("TS-like (A+B) implementable:", len([a for a in allTSlike if a in impl]),
      [a for a in allTSlike if a in impl])

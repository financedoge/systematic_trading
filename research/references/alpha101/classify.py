import re, json
from collections import Counter, defaultdict

F = {}
F[1]="(rank(Ts_ArgMax(SignedPower(((returns < 0) ? stddev(returns, 20) : close), 2.), 5)) - 0.5)"
F[2]="(-1 * correlation(rank(delta(log(volume), 2)), rank(((close - open) / open)), 6))"
F[3]="(-1 * correlation(rank(open), rank(volume), 10))"
F[4]="(-1 * Ts_Rank(rank(low), 9))"
F[5]="(rank((open - (sum(vwap, 10) / 10))) * (-1 * abs(rank((close - vwap)))))"
F[6]="(-1 * correlation(open, volume, 10))"
F[7]="((adv20 < volume) ? ((-1 * ts_rank(abs(delta(close, 7)), 60)) * sign(delta(close, 7))) : (-1 * 1))"
F[8]="(-1 * rank(((sum(open, 5) * sum(returns, 5)) - delay((sum(open, 5) * sum(returns, 5)), 10))))"
F[9]="((0 < ts_min(delta(close, 1), 5)) ? delta(close, 1) : ((ts_max(delta(close, 1), 5) < 0) ? delta(close, 1) : (-1 * delta(close, 1))))"
F[10]="rank(((0 < ts_min(delta(close, 1), 4)) ? delta(close, 1) : ((ts_max(delta(close, 1), 4) < 0) ? delta(close, 1) : (-1 * delta(close, 1)))))"
F[11]="((rank(ts_max((vwap - close), 3)) + rank(ts_min((vwap - close), 3))) * rank(delta(volume, 3)))"
F[12]="(sign(delta(volume, 1)) * (-1 * delta(close, 1)))"
F[13]="(-1 * rank(covariance(rank(close), rank(volume), 5)))"
F[14]="((-1 * rank(delta(returns, 3))) * correlation(open, volume, 10))"
F[15]="(-1 * sum(rank(correlation(rank(high), rank(volume), 3)), 3))"
F[16]="(-1 * rank(covariance(rank(high), rank(volume), 5)))"
F[17]="(((-1 * rank(ts_rank(close, 10))) * rank(delta(delta(close, 1), 1))) * rank(ts_rank((volume / adv20), 5)))"
F[18]="(-1 * rank(((stddev(abs((close - open)), 5) + (close - open)) + correlation(close, open, 10))))"
F[19]="((-1 * sign(((close - delay(close, 7)) + delta(close, 7)))) * (1 + rank((1 + sum(returns, 250)))))"
F[20]="(((-1 * rank((open - delay(high, 1)))) * rank((open - delay(close, 1)))) * rank((open - delay(low, 1))))"
F[21]="((((sum(close, 8) / 8) + stddev(close, 8)) < (sum(close, 2) / 2)) ? (-1 * 1) : (((sum(close, 2) / 2) < ((sum(close, 8) / 8) - stddev(close, 8))) ? 1 : (((1 < (volume / adv20)) || ((volume / adv20) == 1)) ? 1 : (-1 * 1))))"
F[22]="(-1 * (delta(correlation(high, volume, 5), 5) * rank(stddev(close, 20))))"
F[23]="(((sum(high, 20) / 20) < high) ? (-1 * delta(high, 2)) : 0)"
F[24]="((((delta((sum(close, 100) / 100), 100) / delay(close, 100)) < 0.05) || ((delta((sum(close, 100) / 100), 100) / delay(close, 100)) == 0.05)) ? (-1 * (close - ts_min(close, 100))) : (-1 * delta(close, 3)))"
F[25]="rank(((((-1 * returns) * adv20) * vwap) * (high - close)))"
F[26]="(-1 * ts_max(correlation(ts_rank(volume, 5), ts_rank(high, 5), 5), 3))"
F[27]="((0.5 < rank((sum(correlation(rank(volume), rank(vwap), 6), 2) / 2.0))) ? (-1 * 1) : 1)"
F[28]="scale(((correlation(adv20, low, 5) + ((high + low) / 2)) - close))"
F[29]="(min(product(rank(rank(scale(log(sum(ts_min(rank(rank((-1 * rank(delta((close - 1), 5))))), 2), 1))))), 1), 5) + ts_rank(delay((-1 * returns), 6), 5))"
F[30]="(((1.0 - rank(((sign((close - delay(close, 1))) + sign((delay(close, 1) - delay(close, 2)))) + sign((delay(close, 2) - delay(close, 3)))))) * sum(volume, 5)) / sum(volume, 20))"
F[31]="((rank(rank(rank(decay_linear((-1 * rank(rank(delta(close, 10)))), 10)))) + rank((-1 * delta(close, 3)))) + sign(scale(correlation(adv20, low, 12))))"
F[32]="(scale(((sum(close, 7) / 7) - close)) + (20 * scale(correlation(vwap, delay(close, 5), 230))))"
F[33]="rank((-1 * ((1 - (open / close))^1)))"
F[34]="rank(((1 - rank((stddev(returns, 2) / stddev(returns, 5)))) + (1 - rank(delta(close, 1)))))"
F[35]="((Ts_Rank(volume, 32) * (1 - Ts_Rank(((close + high) - low), 16))) * (1 - Ts_Rank(returns, 32)))"
F[36]="(((((2.21 * rank(correlation((close - open), delay(volume, 1), 15))) + (0.7 * rank((open - close)))) + (0.73 * rank(Ts_Rank(delay((-1 * returns), 6), 5)))) + rank(abs(correlation(vwap, adv20, 6)))) + (0.6 * rank((((sum(close, 200) / 200) - open) * (close - open)))))"
F[37]="(rank(correlation(delay((open - close), 1), close, 200)) + rank((open - close)))"
F[38]="((-1 * rank(Ts_Rank(close, 10))) * rank((close / open)))"
F[39]="((-1 * rank((delta(close, 7) * (1 - rank(decay_linear((volume / adv20), 9)))))) * (1 + rank(sum(returns, 250))))"
F[40]="((-1 * rank(stddev(high, 10))) * correlation(high, volume, 10))"
F[41]="(((high * low)^0.5) - vwap)"
F[42]="(rank((vwap - close)) / rank((vwap + close)))"
F[43]="(ts_rank((volume / adv20), 20) * ts_rank((-1 * delta(close, 7)), 8))"
F[44]="(-1 * correlation(high, rank(volume), 5))"
F[45]="(-1 * ((rank((sum(delay(close, 5), 20) / 20)) * correlation(close, volume, 2)) * rank(correlation(sum(close, 5), sum(close, 20), 2))))"
F[46]="((0.25 < (((delay(close, 20) - delay(close, 10)) / 10) - ((delay(close, 10) - close) / 10))) ? (-1 * 1) : (((((delay(close, 20) - delay(close, 10)) / 10) - ((delay(close, 10) - close) / 10)) < 0) ? 1 : ((-1 * 1) * (close - delay(close, 1)))))"
F[47]="((((rank((1 / close)) * volume) / adv20) * ((high * rank((high - close))) / (sum(high, 5) / 5))) - rank((vwap - delay(vwap, 5))))"
F[48]="(indneutralize(((correlation(delta(close, 1), delta(delay(close, 1), 1), 250) * delta(close, 1)) / close), IndClass.subindustry) / sum(((delta(close, 1) / delay(close, 1))^2), 250))"
F[49]="(((((delay(close, 20) - delay(close, 10)) / 10) - ((delay(close, 10) - close) / 10)) < (-1 * 0.1)) ? 1 : ((-1 * 1) * (close - delay(close, 1))))"
F[50]="(-1 * ts_max(rank(correlation(rank(volume), rank(vwap), 5)), 5))"
F[51]="(((((delay(close, 20) - delay(close, 10)) / 10) - ((delay(close, 10) - close) / 10)) < (-1 * 0.05)) ? 1 : ((-1 * 1) * (close - delay(close, 1))))"
F[52]="((((-1 * ts_min(low, 5)) + delay(ts_min(low, 5), 5)) * rank(((sum(returns, 240) - sum(returns, 20)) / 220))) * ts_rank(volume, 5))"
F[53]="(-1 * delta((((close - low) - (high - close)) / (close - low)), 9))"
F[54]="((-1 * ((low - close) * (open^5))) / ((low - high) * (close^5)))"
F[55]="(-1 * correlation(rank(((close - ts_min(low, 12)) / (ts_max(high, 12) - ts_min(low, 12)))), rank(volume), 6))"
F[56]="(0 - (1 * (rank((sum(returns, 10) / sum(sum(returns, 2), 3))) * rank((returns * cap)))))"
F[57]="(0 - (1 * ((close - vwap) / decay_linear(rank(ts_argmax(close, 30)), 2))))"
F[58]="(-1 * Ts_Rank(decay_linear(correlation(IndNeutralize(vwap, IndClass.sector), volume, 3.92795), 7.89291), 5.50322))"
F[59]="(-1 * Ts_Rank(decay_linear(correlation(IndNeutralize(((vwap * 0.728317) + (vwap * (1 - 0.728317))), IndClass.industry), volume, 4.25197), 16.2289), 8.19648))"
F[60]="(0 - (1 * ((2 * scale(rank(((((close - low) - (high - close)) / (high - low)) * volume)))) - scale(rank(ts_argmax(close, 10))))))"
F[61]="(rank((vwap - ts_min(vwap, 16.1219))) < rank(correlation(vwap, adv180, 17.9282)))"
F[62]="((rank(correlation(vwap, sum(adv20, 22.4101), 9.91009)) < rank(((rank(open) + rank(open)) < (rank(((high + low) / 2)) + rank(high))))) * -1)"
F[63]="((rank(decay_linear(delta(IndNeutralize(close, IndClass.industry), 2.25164), 8.22237)) - rank(decay_linear(correlation(((vwap * 0.318108) + (open * (1 - 0.318108))), sum(adv180, 37.2467), 13.557), 12.2883))) * -1)"
F[64]="((rank(correlation(sum(((open * 0.178404) + (low * (1 - 0.178404))), 12.7054), sum(adv120, 12.7054), 16.6208)) < rank(delta(((((high + low) / 2) * 0.178404) + (vwap * (1 - 0.178404))), 3.69741))) * -1)"
F[65]="((rank(correlation(((open * 0.00817205) + (vwap * (1 - 0.00817205))), sum(adv60, 8.6911), 6.40374)) < rank((open - ts_min(open, 13.635)))) * -1)"
F[66]="((rank(decay_linear(delta(vwap, 3.51013), 7.23052)) + Ts_Rank(decay_linear(((((low * 0.96633) + (low * (1 - 0.96633))) - vwap) / (open - ((high + low) / 2))), 11.4157), 6.72611)) * -1)"
F[67]="((rank((high - ts_min(high, 2.14593)))^rank(correlation(IndNeutralize(vwap, IndClass.sector), IndNeutralize(adv20, IndClass.subindustry), 6.02936))) * -1)"
F[68]="((Ts_Rank(correlation(rank(high), rank(adv15), 8.91644), 13.9333) < rank(delta(((close * 0.518371) + (low * (1 - 0.518371))), 1.06157))) * -1)"
F[69]="((rank(ts_max(delta(IndNeutralize(vwap, IndClass.industry), 2.72412), 4.79344))^Ts_Rank(correlation(((close * 0.490655) + (vwap * (1 - 0.490655))), adv20, 4.92416), 9.0615)) * -1)"
F[70]="((rank(delta(vwap, 1.29456))^Ts_Rank(correlation(IndNeutralize(close, IndClass.industry), adv50, 17.8256), 17.9171)) * -1)"
F[71]="max(Ts_Rank(decay_linear(correlation(Ts_Rank(close, 3.43976), Ts_Rank(adv180, 12.0647), 18.0175), 4.20501), 15.6948), Ts_Rank(decay_linear((rank(((low + open) - (vwap + vwap)))^2), 16.4662), 4.4388))"
F[72]="(rank(decay_linear(correlation(((high + low) / 2), adv40, 8.93345), 10.1519)) / rank(decay_linear(correlation(Ts_Rank(vwap, 3.72469), Ts_Rank(volume, 18.5188), 6.86671), 2.95011)))"
F[73]="(max(rank(decay_linear(delta(vwap, 4.72775), 2.91864)), Ts_Rank(decay_linear(((delta(((open * 0.147155) + (low * (1 - 0.147155))), 2.03608) / ((open * 0.147155) + (low * (1 - 0.147155)))) * -1), 3.33829), 16.7411)) * -1)"
F[74]="((rank(correlation(close, sum(adv30, 37.4843), 15.1365)) < rank(correlation(rank(((high * 0.0261661) + (vwap * (1 - 0.0261661)))), rank(volume), 11.4791))) * -1)"
F[75]="(rank(correlation(vwap, volume, 4.24304)) < rank(correlation(rank(low), rank(adv50), 12.4413)))"
F[76]="(max(rank(decay_linear(delta(vwap, 1.24383), 11.8259)), Ts_Rank(decay_linear(Ts_Rank(correlation(IndNeutralize(low, IndClass.sector), adv81, 8.14941), 19.569), 17.1543), 19.383)) * -1)"
F[77]="min(rank(decay_linear(((((high + low) / 2) + high) - (vwap + high)), 20.0451)), rank(decay_linear(correlation(((high + low) / 2), adv40, 3.1614), 5.64125)))"
F[78]="(rank(correlation(sum(((low * 0.352233) + (vwap * (1 - 0.352233))), 19.7428), sum(adv40, 19.7428), 6.83313))^rank(correlation(rank(vwap), rank(volume), 5.77492)))"
F[79]="(rank(delta(IndNeutralize(((close * 0.60733) + (open * (1 - 0.60733))), IndClass.sector), 1.23438)) < rank(correlation(Ts_Rank(vwap, 3.60973), Ts_Rank(adv150, 9.18637), 14.6644)))"
F[80]="((rank(Sign(delta(IndNeutralize(((open * 0.868128) + (high * (1 - 0.868128))), IndClass.industry), 4.04545)))^Ts_Rank(correlation(high, adv10, 5.11456), 5.53756)) * -1)"
F[81]="((rank(Log(product(rank((rank(correlation(vwap, sum(adv10, 49.6054), 8.47743))^4)), 14.9655))) < rank(correlation(rank(vwap), rank(volume), 5.07914))) * -1)"
F[82]="(min(rank(decay_linear(delta(open, 1.46063), 14.8717)), Ts_Rank(decay_linear(correlation(IndNeutralize(volume, IndClass.sector), ((open * 0.634196) + (open * (1 - 0.634196))), 17.4842), 6.92131), 13.4283)) * -1)"
F[83]="((rank(delay(((high - low) / (sum(close, 5) / 5)), 2)) * rank(rank(volume))) / (((high - low) / (sum(close, 5) / 5)) / (vwap - close)))"
F[84]="SignedPower(Ts_Rank((vwap - ts_max(vwap, 15.3217)), 20.7127), delta(close, 4.96796))"
F[85]="(rank(correlation(((high * 0.876703) + (close * (1 - 0.876703))), adv30, 9.61331))^rank(correlation(Ts_Rank(((high + low) / 2), 3.70596), Ts_Rank(volume, 10.1595), 7.11408)))"
F[86]="((Ts_Rank(correlation(close, sum(adv20, 14.7444), 6.00049), 20.4195) < rank(((open + close) - (vwap + open)))) * -1)"
F[87]="(max(rank(decay_linear(delta(((close * 0.369701) + (vwap * (1 - 0.369701))), 1.91233), 2.65461)), Ts_Rank(decay_linear(abs(correlation(IndNeutralize(adv81, IndClass.industry), close, 13.4132)), 4.89768), 14.4535)) * -1)"
F[88]="min(rank(decay_linear(((rank(open) + rank(low)) - (rank(high) + rank(close))), 8.06882)), Ts_Rank(decay_linear(correlation(Ts_Rank(close, 8.44728), Ts_Rank(adv60, 20.6966), 8.01266), 6.65053), 2.61957))"
F[89]="(Ts_Rank(decay_linear(correlation(((low * 0.967285) + (low * (1 - 0.967285))), adv10, 6.94279), 5.51607), 3.79744) - Ts_Rank(decay_linear(delta(IndNeutralize(vwap, IndClass.industry), 3.48158), 10.1466), 15.3012))"
F[90]="((rank((close - ts_max(close, 4.66719)))^Ts_Rank(correlation(IndNeutralize(adv40, IndClass.subindustry), low, 5.38375), 3.21856)) * -1)"
F[91]="((Ts_Rank(decay_linear(decay_linear(correlation(IndNeutralize(close, IndClass.industry), volume, 9.74928), 16.398), 3.83219), 4.8667) - rank(decay_linear(correlation(vwap, adv30, 4.01303), 2.6809))) * -1)"
F[92]="min(Ts_Rank(decay_linear(((((high + low) / 2) + close) < (low + open)), 14.7221), 18.8683), Ts_Rank(decay_linear(correlation(rank(low), rank(adv30), 7.58555), 6.94024), 6.80584))"
F[93]="(Ts_Rank(decay_linear(correlation(IndNeutralize(vwap, IndClass.industry), adv81, 17.4193), 19.848), 7.54455) / rank(decay_linear(delta(((close * 0.524434) + (vwap * (1 - 0.524434))), 2.77377), 16.2664)))"
F[94]="((rank((vwap - ts_min(vwap, 11.5783)))^Ts_Rank(correlation(Ts_Rank(vwap, 19.6462), Ts_Rank(adv60, 4.02992), 18.0926), 2.70756)) * -1)"
F[95]="(rank((open - ts_min(open, 12.4105))) < Ts_Rank((rank(correlation(sum(((high + low) / 2), 19.1351), sum(adv40, 19.1351), 12.8742))^5), 11.7584))"
F[96]="(max(Ts_Rank(decay_linear(correlation(rank(vwap), rank(volume), 3.83878), 4.16783), 8.38151), Ts_Rank(decay_linear(Ts_ArgMax(correlation(Ts_Rank(close, 7.45404), Ts_Rank(adv60, 4.13242), 3.65459), 12.6556), 14.0365), 13.4143)) * -1)"
F[97]="((rank(decay_linear(delta(IndNeutralize(((low * 0.721001) + (vwap * (1 - 0.721001))), IndClass.industry), 3.3705), 20.4523)) - Ts_Rank(decay_linear(Ts_Rank(correlation(Ts_Rank(low, 7.87871), Ts_Rank(adv60, 17.255), 4.97547), 18.5925), 15.7152), 6.71659)) * -1)"
F[98]="(rank(decay_linear(correlation(vwap, sum(adv5, 26.4719), 4.58418), 7.18088)) - rank(decay_linear(Ts_Rank(Ts_ArgMin(correlation(rank(open), rank(adv15), 20.8187), 8.62571), 6.95668), 8.07206)))"
F[99]="((rank(correlation(sum(((high + low) / 2), 19.8975), sum(adv60, 19.8975), 8.8136)) < rank(correlation(low, volume, 6.28259))) * -1)"
F[100]="(0 - (1 * (((1.5 * scale(indneutralize(indneutralize(rank(((((close - low) - (high - close)) / (high - low)) * volume)), IndClass.subindustry), IndClass.subindustry))) - scale(indneutralize((correlation(close, rank(adv20), 5) - rank(ts_argmin(close, 30))), IndClass.subindustry))) * (volume / adv20))))"
F[101]="((close - open) / ((high - low) + .001))"

assert len(F) == 101, len(F)

ids = sorted(F)

def has(a, pat):
    return re.search(pat, F[a], re.I) is not None

# ---- input requirements -------------------------------------------------
vwap   = [a for a in ids if has(a, r'\bvwap\b')]
cap    = [a for a in ids if re.search(r'\bcap\b', F[a], re.I)]
indc   = [a for a in ids if has(a, r'indclass|indneutralize')]
adv    = [a for a in ids if has(a, r'\badv\d+')]

def advset(a):
    return sorted(set(int(x) for x in re.findall(r'adv(\d+)', F[a], re.I)))

adv20_only_etc = {a: advset(a) for a in adv}

# does it use only ohlcv + returns (no vwap, no cap, no IndClass)?
ohlcv = [a for a in ids if a not in vwap and a not in cap and a not in indc]

print("=== INPUT COUNTS ===")
print("needs vwap          :", len(vwap), vwap)
print("needs cap           :", len(cap), cap)
print("needs IndClass      :", len(indc), indc)
print("needs adv{d}        :", len(adv), adv)
print("OHLCV+returns only  :", len(ohlcv), ohlcv)
print()
print("overlaps:")
print("  vwap & IndClass   :", len(set(vwap)&set(indc)), sorted(set(vwap)&set(indc)))
print("  vwap & cap        :", len(set(vwap)&set(cap)), sorted(set(vwap)&set(cap)))
print("  cap & IndClass    :", len(set(cap)&set(indc)), sorted(set(cap)&set(indc)))
print("  vwap&cap&IndClass :", len(set(vwap)&set(cap)&set(indc)))
print("  OHLCV & adv       :", len(set(ohlcv)&set(adv)), sorted(set(ohlcv)&set(adv)))
print("  OHLCV & no adv    :", len(set(ohlcv)-set(adv)), sorted(set(ohlcv)-set(adv)))
badv = [a for a in ids if a not in ohlcv]
print("  blocked (vwap/cap/IndClass):", len(badv), badv)
print()
print("adv windows used:", sorted(set(int(x) for a in adv for x in re.findall(r'adv(\d+)', F[a], re.I))))
print("alphas using adv180/adv150/adv120/adv81 (long windows):",
      [a for a in adv if set(advset(a)) & {81,120,150,180}])
print()

# ---- operators ----------------------------------------------------------
def strip_ts(s):
    # remove ts_rank / Ts_Rank / ts_min / ts_max ... so bare 'rank(' can be counted
    return re.sub(r'\b(ts|Ts)_(rank|min|max|argmax|argmin)\b', 'TSOP', s)

cs_rank_alpha, cs_scale_alpha, indneut_alpha = [], [], []
for a in ids:
    s = strip_ts(F[a])
    if re.search(r'(?<![A-Za-z_])rank\s*\(', s): cs_rank_alpha.append(a)
    if re.search(r'(?<![A-Za-z_])scale\s*\(', s): cs_scale_alpha.append(a)
    if re.search(r'indneutralize\s*\(', s, re.I): indneut_alpha.append(a)

def count_cs(a):
    s = strip_ts(F[a])
    return (len(re.findall(r'(?<![A-Za-z_])rank\s*\(', s))
            + len(re.findall(r'(?<![A-Za-z_])scale\s*\(', s))
            + len(re.findall(r'indneutralize\s*\(', s, re.I)))

cs_counts = {a: count_cs(a) for a in ids}
strict_ts = [a for a in ids if cs_counts[a] == 0]
any_cs    = [a for a in ids if cs_counts[a] > 0]

print("=== CROSS-SECTIONAL vs TIME-SERIES ===")
print("alphas with >=1 CS op  :", len(any_cs))
print("alphas with 0 CS ops   :", len(strict_ts), strict_ts)
print("  strict-TS but needs vwap:", [a for a in strict_ts if a in vwap])
print("  strict-TS implementable :", len([a for a in strict_ts if a not in vwap and a not in cap and a not in indc]),
      [a for a in strict_ts if a not in vwap and a not in cap and a not in indc])
print()
print("rank() used in      :", len(cs_rank_alpha))
print("scale() used in     :", len(cs_scale_alpha), cs_scale_alpha)
print("indneutralize in    :", len(indneut_alpha), indneut_alpha)
print()
buckets = defaultdict(list)
for a in ids:
    buckets[min(cs_counts[a], 12)].append(a)
for k in sorted(buckets):
    lbl = f"{k}" if k < 12 else "12+"
    print(f"  CS-op count {lbl:>3}: {len(buckets[k]):>3}  {buckets[k]}")
print()

# boolean comparison of two cross-sectional ranks: rank(...) < rank(...)
cmp_cs = []
for a in ids:
    s = strip_ts(F[a])
    if re.search(r'rank\s*\(.*?\)\s*[<>]\s*rank\s*\(', s):
        cmp_cs.append(a)
print("rank-vs-rank comparisons:", len(cmp_cs), cmp_cs)
print()

# ---- operator inventory -------------------------------------------------
ops = ["rank","delay","correlation","covariance","decay_linear","ts_rank","ts_min","ts_max",
       "ts_argmax","ts_argmin","sum","product","stddev","scale","signedpower","min(","max(",
       "indneutralize","delta","adv","volume","close","open","high","low","returns","vwap","cap"]
def op_used(a, op):
    s = F[a]
    if op == "rank":
        return re.search(r'(?<![A-Za-z_])rank\s*\(', strip_ts(s)) is not None
    if op == "ts_rank":
        return re.search(r'\bts_rank\s*\(', s, re.I) is not None
    if op == "ts_min":
        return re.search(r'(?<![A-Za-z_])ts_min\s*\(', s, re.I) is not None
    if op == "ts_max":
        return re.search(r'(?<![A-Za-z_])ts_max\s*\(', s, re.I) is not None
    if op == "ts_argmax":
        return re.search(r'ts_argmax\s*\(', s, re.I) is not None
    if op == "ts_argmin":
        return re.search(r'ts_argmin\s*\(', s, re.I) is not None
    if op == "scale":
        return re.search(r'(?<![A-Za-z_])scale\s*\(', s) is not None
    if op == "min(":
        return re.search(r'(?<![A-Za-z_])min\s*\(', s) is not None
    if op == "max(":
        return re.search(r'(?<![A-Za-z_])max\s*\(', s) is not None
    if op == "adv":
        return re.search(r'\badv\d+', s, re.I) is not None
    if op == "signedpower":
        return re.search(r'signedpower\s*\(', s, re.I) is not None
    if op == "indneutralize":
        return re.search(r'indneutralize\s*\(', s, re.I) is not None
    return re.search(r'(?<![A-Za-z_])' + re.escape(op.rstrip('(')) + r'\b', s, re.I) is not None

print("=== OPERATOR INVENTORY (number of the 101 alphas using each) ===")
rows = []
for op in ops:
    used = [a for a in ids if op_used(a, op)]
    rows.append((op, len(used), used))
for op, n, used in sorted(rows, key=lambda r: -r[1]):
    print(f"{op:>14}: {n:>3}   {used if n <= 20 else str(used[:14])+' ...'}")
print()

# raw occurrence counts
occ = Counter()
for a in ids:
    s = strip_ts(F[a])
    for op in ["rank","scale","delay","correlation","covariance","decay_linear","sum","product",
               "stddev","delta","signedpower","indneutralize"]:
        occ[op] += len(re.findall(r'(?<![A-Za-z_])' + op + r'\s*\(', s, re.I))
    occ["ts_rank"] += len(re.findall(r'ts_rank\s*\(', F[a], re.I))
    occ["ts_min"]  += len(re.findall(r'(?<![A-Za-z_])ts_min\s*\(', F[a], re.I))
    occ["ts_max"]  += len(re.findall(r'(?<![A-Za-z_])ts_max\s*\(', F[a], re.I))
    occ["ts_argmax"] += len(re.findall(r'ts_argmax\s*\(', F[a], re.I))
    occ["ts_argmin"] += len(re.findall(r'ts_argmin\s*\(', F[a], re.I))
    occ["min"] += len(re.findall(r'(?<![A-Za-z_])min\s*\(', strip_ts(F[a])))
    occ["max"] += len(re.findall(r'(?<![A-Za-z_])max\s*\(', strip_ts(F[a])))
print("=== RAW OCCURRENCES ACROSS ALL 101 ===")
for k, v in occ.most_common():
    print(f"  {k:>14}: {v}")
print()

# ---- lookback breadcrumbs ----------------------------------------------
long_lb = []
for a in ids:
    nums = [float(x) for x in re.findall(r'(?<![\w.])(\d+(?:\.\d+)?)(?![\w.])', F[a])]
    big = [n for n in nums if n >= 100]
    if big: long_lb.append((a, sorted(set(big))))
print("alphas with lookback >= 100 days:", long_lb)
print()

# ---- implementable set --------------------------------------------------
impl = [a for a in ids if a not in vwap and a not in cap and a not in indc]
print("FINAL IMPLEMENTABLE (OHLCV+returns+derived adv):", len(impl))
print(impl)
print()
print("usable, zero-CS subset of implementable:", [a for a in impl if cs_counts[a]==0])
print("usable, >=1 CS op subset of implementable:", len([a for a in impl if cs_counts[a]>0]))

json.dump({"cs": cs_counts, "vwap": vwap, "cap": cap, "indc": indc, "adv": adv,
           "impl": impl, "strict_ts": strict_ts, "cmp_cs": cmp_cs},
          open(r'research_tmp\classify.json','w'), indent=1)
print("wrote classify.json")

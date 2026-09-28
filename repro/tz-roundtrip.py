"""一条规则 str() 出来、再让 rrulestr 读回去，读回来的还是不是原来那条。

跑法（工作副本根目录；.venv 里的 editable 指回种子，所以必须带 PYTHONPATH=src 才测到副本自己那份码）：
    PYTHONPATH=src .venv/bin/python repro/tz-roundtrip.py
第一行打印被测包的 __file__，能看出测的是哪一份码。

格子只描述读数：串长什么样、读回来的时刻对不对得上、时区身份还在不在。
每格自造输入（日期是写死的常量），跑完把进程时区还原回去，可反复跑。
"""
import os
import sys
import time
import datetime

import dateutil
from dateutil import tz
from dateutil.rrule import rrulestr, rrule, DAILY, YEARLY, MONTHLY, MO

print("code under test:", dateutil.__file__)

res = []


def cell(name, owner, ok, detail=''):
    res.append((name, owner, bool(ok), str(detail)))


def val(fn):
    try:
        return ('ok', fn())
    except Exception as e:
        return ('exc', type(e).__name__ + ': ' + str(e)[:80])


NY = tz.gettz('America/New_York')
UTC = tz.tzutc()


def seq(rr):
    return list(rr)


def same_instants(a, b):
    """两个序列逐个比时刻（aware/naive 混比会炸，这里兜住）。"""
    if len(a) != len(b) or not a:
        return False, 'len %d vs %d' % (len(a), len(b))
    for x, y in zip(a, b):
        try:
            if not (x == y):
                return False, '%s vs %s' % (x, y)
        except TypeError:
            return False, 'aware/naive: %s vs %s' % (x, y)
    return True, 'ok'


# ---------------- S 组：串本身的形状
rn = rrule(DAILY, count=8, dtstart=datetime.datetime(2024, 3, 5, 9, 0, tzinfo=NY))
naive = rrule(YEARLY, count=5, dtstart=datetime.datetime(1997, 9, 2, 9, 0))
ru = rrule(DAILY, count=2, dtstart=datetime.datetime(2024, 1, 1, 9, 0, tzinfo=UTC))
k = val(lambda: str(rn))
cell('S1 命名区起点的串里带区名参数', 'src/dateutil/rrule.py __str__',
     k[0] == 'ok' and 'TZID=' in k[1], repr(k[1])[:70])
cell('S2 不带时区的规则串一字不改', 'src/dateutil/rrule.py __str__',
     str(naive) == 'DTSTART:19970902T090000\nRRULE:FREQ=YEARLY;COUNT=5', repr(str(naive))[:70])
rr_plain = 'DTSTART:19970105T083000\nRRULE:FREQ=YEARLY;INTERVAL=2'
cell('S3 读回来的规则再写出去还是同一串', 'src/dateutil/rrule.py __str__',
     str(rrulestr(rr_plain)) == rr_plain, repr(str(rrulestr(rr_plain)))[:70])
rr_rule_part = str(rrule(MONTHLY, count=3, interval=2, byweekday=(MO,),
                         dtstart=datetime.datetime(1997, 9, 2, 9, 0)))
cell('S4 RRULE 段的写法照旧', 'src/dateutil/rrule.py __str__',
     rr_rule_part.endswith('RRULE:FREQ=MONTHLY;INTERVAL=2;COUNT=3;BYDAY=MO'), repr(rr_rule_part)[-52:])
cell('S5 不带区名的起点（UTC 那类）写法照旧', 'src/dateutil/rrule.py __str__',
     str(ru) == 'DTSTART:20240101T090000\nRRULE:FREQ=DAILY;COUNT=2', repr(str(ru))[:70])

# ---------------- N 组：命名区，序列跨 2024-03-10 的夏令时切换
k = val(lambda: rrulestr(str(rn))._dtstart.tzinfo is not None)
cell('N1 往返后命名区起点还带时区', 'src/dateutil/rrule.py __str__', k[0] == 'ok' and k[1] is True, repr(k[1])[:60])
k = val(lambda: same_instants(seq(rrulestr(str(rn))), seq(rn)))
cell('N2 往返后每个时刻都对得上（含夏令时切换日）', 'src/dateutil/rrule.py __str__',
     k[0] == 'ok' and k[1][0], repr(k[1])[:70])
k = val(lambda: (rrulestr(str(rn))._dtstart.tzinfo.utcoffset(datetime.datetime(2024, 1, 10, 12)) ==
                 NY.utcoffset(datetime.datetime(2024, 1, 10, 12)) and
                 rrulestr(str(rn))._dtstart.tzinfo.utcoffset(datetime.datetime(2024, 7, 10, 12)) ==
                 NY.utcoffset(datetime.datetime(2024, 7, 10, 12))))
cell('N3 往返后的时区冬天差 5 小时、夏天差 4 小时（同一个区身份）', 'src/dateutil/tz/tz.py zone-id',
     k[0] == 'ok' and k[1] is True, repr(k[1])[:70])
k = val(lambda: str(rrulestr(str(rn))) == str(rn))
cell('N4 写出去—读回来—再写出去，串不变', 'src/dateutil/rrule.py __str__ + src/dateutil/tz/tz.py zone-id',
     k[0] == 'ok' and k[1] is True, repr(k[1])[:60])
k = val(lambda: type(rrulestr(str(rn))._dtstart.tzinfo).__name__)
cell('N5 往返后起点的时区是个查得到区名的对象', 'src/dateutil/tz/tz.py zone-id',
     k[0] == 'ok' and 'tzfile' in str(k[1]), repr(k[1])[:60])

# ---------------- L 组：本地时区
old_tz_env = os.environ.get('TZ')
os.environ['TZ'] = 'America/Denver'
time.tzset()
try:
    local = tz.tzlocal()
    rl = rrule(DAILY, count=8, dtstart=datetime.datetime(2024, 3, 5, 9, 0, tzinfo=local))
    k = val(lambda: same_instants(seq(rrulestr(str(rl))), seq(rl)))
    cell('L1 本地时区起点（跨夏令时）往返后每个时刻都对得上', 'src/dateutil/tz/tz.py zone-id',
         k[0] == 'ok' and k[1][0], repr(k[1])[:70] + ' tznames=' + repr(local._tznames))
    k = val(lambda: rrulestr(str(rl))._dtstart.tzinfo.utcoffset(datetime.datetime(2024, 7, 1, 12)) ==
            local.utcoffset(datetime.datetime(2024, 7, 1, 12)))
    cell('L2 本地时区读回来七月差 6 小时、一月差 7 小时', 'src/dateutil/tz/tz.py zone-id',
         k[0] == 'ok' and k[1] is True, repr(k[1])[:60])
finally:
    if old_tz_env is None:
        os.environ.pop('TZ', None)
    else:
        os.environ['TZ'] = old_tz_env
    time.tzset()

r_off = rrule(DAILY, count=3, dtstart=datetime.datetime(2024, 6, 1, 9, 0, tzinfo=tz.tzoffset('CET', 3600)))
cell('L3 只有偏移没有区名的起点写法照旧', 'src/dateutil/rrule.py __str__',
     str(r_off) == 'DTSTART:20240601T090000\nRRULE:FREQ=DAILY;COUNT=3', repr(str(r_off))[:70])

# ---------------- U 组：既有口径不许动
ru_until = rrule(YEARLY, count=2, dtstart=datetime.datetime(1997, 9, 2, 9, 0, tzinfo=NY),
                 until=datetime.datetime(1999, 1, 1, 0, 0, tzinfo=UTC))
k = val(lambda: same_instants(seq(rrulestr(str(ru_until))), seq(ru_until)))
cell('U1 带 UNTIL 的命名区规则往返后序列对得上', 'src/dateutil/rrule.py __str__',
     k[0] == 'ok' and k[1][0], repr(k[1])[:70])
k = val(lambda: rrulestr('DTSTART;TZID=America/New_York:19970902T090000Z\nRRULE:FREQ=YEARLY;COUNT=3'))
cell('U2 区名参数和 Z 同时出现仍然报错', 'src/dateutil/rrule.py _parse_date_value',
     k[0] == 'exc' and 'ValueError' in k[1], repr(k[1])[:70])
k = val(lambda: str(rrulestr('DTSTART;TZID=Mars/Olympus:20240101T090000\nRRULE:FREQ=DAILY;COUNT=1')._dtstart.tzinfo))
cell('U3 认不出来的区名仍然退回不带时区', 'src/dateutil/rrule.py _parse_date_value',
     k[0] == 'ok' and k[1] == 'None', repr(k[1])[:60])
k = val(lambda: rrulestr(str(naive))._dtstart.tzinfo is None)
cell('U4 不带时区的规则读回来还是不带时区', 'src/dateutil/rrule.py __str__', k[0] == 'ok' and k[1] is True, repr(k[1])[:60])
k = val(lambda: [str(x) for x in rrulestr('DTSTART;TZID=America/New_York:19970902T090000\n'
                                          'RRULE:FREQ=YEARLY;COUNT=2')])
cell('U5 文本里给区名仍然读得到纽约', 'src/dateutil/rrule.py _parse_date_value',
     k[0] == 'ok' and k[1][0] == '1997-09-02 09:00:00-04:00', repr(k[1])[:70])
k = val(lambda: str(ru_until))
cell('U6 带时区起点的 UNTIL 要写成 UTC 形式（读回来才不撞多个时区）', 'src/dateutil/rrule.py __str__',
     k[0] == 'ok' and 'UNTIL=19990101T000000Z' in k[1], repr(k[1])[:70])

print('---- PANEL (rrule 时区往返) ----')
ok = 0
for name, owner, good, detail in res:
    print(('PASS ' if good else 'FAIL ') + name + ' | ' + owner + ' | ' + detail)
    ok += 1 if good else 0
print('TOTAL %d/%d' % (ok, len(res)))
sys.exit(0)

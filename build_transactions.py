#!/usr/bin/env python3
"""
Build the association-rule-mining dataset (market-basket transactions) + exact answer key.

Run in Colab (no internet needed):
    !python build_transactions.py --out "/content/drive/MyDrive/RC3 AI Hackathon/arm_task" --n 500000

Outputs (in --out):
    transactions.txt              full dataset, one transaction per line, space-separated item ids   (students)
    dev_transactions.txt          smaller dataset with the same structure                            (students)
    dev_frequent_itemsets.csv     itemset,count     exact answer key for the dev set                 (students)
    dev_rules.csv                 antecedent,consequent,count,confidence                             (students)
    params.json                   min_support, min_confidence                                        (students)
    frequent_itemsets.csv         answer key for transactions.txt                                    (PRIVATE)
    rules.csv                     answer key for transactions.txt                                    (PRIVATE)
    student_data.zip              the five student files above
    stats.json

Definitions used for the answer key
    min_count = ceil(min_support * number_of_transactions)
    frequent itemset : count(X) >= min_count, |X| >= 1
    rule A -> C      : A, C non-empty, disjoint, A u C frequent, count(A u C)/count(A) >= min_confidence
                       (consequent may have any size)
"""
import argparse, bisect, csv, json, math, os, random, time, zipfile
import numpy as np

# ------------------------------------------------------------------ world (shared by dev and full)
ZIPF_S = 0.85          # item popularity skew
AVG_LEN = 10           # mean basket size (before bulk orders)
MAX_LEN = 30
P_PATTERN = 0.5        # chance that a fill step adds a whole pattern instead of one item
CORRUPT = 0.10         # chance each pattern item is dropped
BULK_P = 0.003         # fraction of very large "bulk" baskets
BULK_LO, BULK_HI = 35, 70


def make_world(seed, n_items, n_patterns, n_bundles):
    rng = random.Random(seed)
    nrng = np.random.default_rng(seed)
    ids = list(range(1, n_items + 1))
    rng.shuffle(ids)                                  # popularity rank -> item id
    w = [1.0 / (r + 1) ** ZIPF_S for r in range(n_items)]
    tot = sum(w)
    cum_item, acc = [], 0.0
    for x in w:
        acc += x / tot
        cum_item.append(acc)

    def draw_item():
        return ids[min(bisect.bisect(cum_item, rng.random()), n_items - 1)]

    patterns, prev = [], []
    for _ in range(n_patterns):
        L = int(min(7, 2 + nrng.poisson(2.0)))
        items = set()
        if prev:
            k = min(len(prev), L - 1, int(len(prev) * 0.5))
            items.update(rng.sample(prev, k))
        while len(items) < L:
            items.add(draw_item())
        prev = sorted(items)
        patterns.append(prev)
    pw = nrng.exponential(1.0, n_patterns)
    pw /= pw.sum()
    cum_pat = list(np.cumsum(pw))

    bundles = []
    for _ in range(n_bundles):                        # long planted itemsets (deep levels)
        L = rng.choice([8, 9])
        pool = ids[20:400]
        bundles.append((sorted(rng.sample(pool, L)), rng.uniform(0.012, 0.03)))
    return dict(ids=ids, cum_item=cum_item, patterns=patterns, cum_pat=cum_pat, bundles=bundles)


def generate(world, n, seed):
    rng = random.Random(seed)
    nrng = np.random.default_rng(seed)
    ids, cum_item = world['ids'], world['cum_item']
    patterns, cum_pat, bundles = world['patterns'], world['cum_pat'], world['bundles']
    n_items = len(ids)
    lens = np.minimum(nrng.poisson(AVG_LEN - 1, n) + 1, MAX_LEN)
    bulk = nrng.random(n) < BULK_P
    lens[bulk] = nrng.integers(BULK_LO, BULK_HI + 1, int(bulk.sum()))
    bis, rnd = bisect.bisect, rng.random
    out = []
    for t in range(n):
        items = set()
        for bitems, q in bundles:
            if rnd() < q:
                for it in bitems:
                    if rnd() > 0.03:
                        items.add(it)
        target = int(lens[t])
        while len(items) < target:
            if rnd() < P_PATTERN:
                pat = patterns[min(bis(cum_pat, rnd()), len(patterns) - 1)]
                for it in pat:
                    if rnd() > CORRUPT:
                        items.add(it)
            else:
                items.add(ids[min(bis(cum_item, rnd()), n_items - 1)])
        out.append(sorted(items))
    return out


# ------------------------------------------------------------------ exact miner (answer key only)
_TBL = np.array([bin(i).count('1') for i in range(256)], dtype=np.uint8)


def popcount(a64):
    if hasattr(np, 'bitwise_count'):
        return int(np.bitwise_count(a64).sum())
    return int(_TBL[a64.view(np.uint8)].sum())


def mine_frequent(tx, min_count):
    """Exact frequent itemsets with vertical bitsets (Eclat). Returns {tuple(sorted items): count}."""
    n = len(tx)
    lens = np.fromiter(map(len, tx), dtype=np.int64, count=n)
    flat = np.fromiter((i for t in tx for i in t), dtype=np.int32, count=int(lens.sum()))
    tid = np.repeat(np.arange(n, dtype=np.int32), lens)
    cnt = np.bincount(flat)
    freq_items = np.where(cnt >= min_count)[0]
    order = np.argsort(flat, kind='stable')
    flat_s, tid_s = flat[order], tid[order]
    bounds = np.searchsorted(flat_s, np.arange(len(cnt) + 1))
    nbytes = ((n + 7) // 8 + 7) // 8 * 8
    cands = []
    for it in freq_items:
        arr = np.zeros(nbytes * 8, dtype=bool)
        arr[tid_s[bounds[it]:bounds[it + 1]]] = True
        bits = np.packbits(arr).view(np.uint64)
        cands.append((int(it), bits, int(cnt[it])))
    cands.sort(key=lambda x: x[2])
    result = {}

    def rec(prefix, cl):
        for k, (it, b, c) in enumerate(cl):
            p = prefix + [it]
            result[tuple(sorted(p))] = c
            nxt = []
            for jt, bj, _ in cl[k + 1:]:
                inter = b & bj
                cc = popcount(inter)
                if cc >= min_count:
                    nxt.append((jt, inter, cc))
            if nxt:
                rec(p, nxt)

    rec([], cands)
    return result


def make_rules(freq, min_conf):
    rules = []
    for X, c in freq.items():
        k = len(X)
        if k < 2:
            continue
        for mask in range(1, (1 << k) - 1):
            A = tuple(X[i] for i in range(k) if mask >> i & 1)
            ca = freq[A]
            if c >= min_conf * ca - 1e-12:
                C = tuple(X[i] for i in range(k) if not mask >> i & 1)
                rules.append((A, C, c, c / ca))
    rules.sort()
    return rules


# ------------------------------------------------------------------ io
def write_tx(path, tx):
    with open(path, 'w') as f:
        for t in tx:
            f.write(' '.join(map(str, t)) + '\n')


def write_key(prefix, out, freq, rules):
    with open(os.path.join(out, prefix + 'frequent_itemsets.csv'), 'w', newline='') as f:
        w = csv.writer(f)
        w.writerow(['itemset', 'count'])
        for X, c in sorted(freq.items(), key=lambda kv: (len(kv[0]), kv[0])):
            w.writerow([' '.join(map(str, X)), c])
    with open(os.path.join(out, prefix + 'rules.csv'), 'w', newline='') as f:
        w = csv.writer(f)
        w.writerow(['antecedent', 'consequent', 'count', 'confidence'])
        for A, C, c, conf in rules:
            w.writerow([' '.join(map(str, A)), ' '.join(map(str, C)), c, f"{conf:.6f}"])


def build_set(world, n, seed, min_sup, min_conf, out, prefix, txname, stats):
    t0 = time.time()
    tx = generate(world, n, seed)
    write_tx(os.path.join(out, txname), tx)
    print(f"[{prefix or 'full'}] generated {n} transactions in {time.time()-t0:.0f}s", flush=True)
    min_count = math.ceil(min_sup * n)
    t0 = time.time()
    freq = mine_frequent(tx, min_count)
    t1 = time.time()
    rules = make_rules(freq, min_conf)
    print(f"[{prefix or 'full'}] min_count={min_count} frequent={len(freq)} rules={len(rules)} "
          f"(mine {t1-t0:.0f}s, rules {time.time()-t1:.0f}s)", flush=True)
    write_key(prefix, out, freq, rules)
    sizes = {}
    for X in freq:
        sizes[len(X)] = sizes.get(len(X), 0) + 1
    lens = [len(t) for t in tx]
    stats[(prefix or 'full') + '_stats'] = dict(
        n=n, min_count=min_count, n_frequent=len(freq), n_rules=len(rules),
        frequent_by_size={str(k): v for k, v in sorted(sizes.items())},
        avg_len=round(sum(lens) / n, 2), max_len=max(lens),
        n_items_used=len({i for t in tx for i in t}))


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--out', required=True)
    ap.add_argument('--n', type=int, default=500000)
    ap.add_argument('--dev-n', type=int, default=50000)
    ap.add_argument('--items', type=int, default=2000)
    ap.add_argument('--patterns', type=int, default=300)
    ap.add_argument('--bundles', type=int, default=6)
    ap.add_argument('--min-support', type=float, default=0.003)
    ap.add_argument('--min-confidence', type=float, default=0.6)
    ap.add_argument('--seed', type=int, default=7)
    a = ap.parse_args()
    os.makedirs(a.out, exist_ok=True)
    world = make_world(a.seed, a.items, a.patterns, a.bundles)
    stats = {}
    build_set(world, a.dev_n, a.seed + 1, a.min_support, a.min_confidence, a.out, 'dev_', 'dev_transactions.txt', stats)
    build_set(world, a.n, a.seed + 2, a.min_support, a.min_confidence, a.out, '', 'transactions.txt', stats)
    with open(os.path.join(a.out, 'params.json'), 'w') as f:
        json.dump(dict(min_support=a.min_support, min_confidence=a.min_confidence), f)
    with zipfile.ZipFile(os.path.join(a.out, 'student_data.zip'), 'w', zipfile.ZIP_DEFLATED) as z:
        for fn in ('transactions.txt', 'dev_transactions.txt', 'dev_frequent_itemsets.csv', 'dev_rules.csv', 'params.json'):
            z.write(os.path.join(a.out, fn), fn)
    with open(os.path.join(a.out, 'stats.json'), 'w') as f:
        json.dump(stats, f, indent=2)
    print(json.dumps(stats, indent=2))


if __name__ == '__main__':
    main()

"""Deterministic validation and ranking. No model calls belong in this module."""
import json
import math
from datetime import date


def number(value):
    if isinstance(value, bool):
        raise ValueError('Boolean is not a score')
    result = float(value)
    if not math.isfinite(result):
        raise ValueError('Non-finite number')
    return result


def check_criteria(criteria):
    active = [dict(c) for c in criteria if c['is_active']]
    if not active:
        raise ValueError('Activate at least one criterion.')
    if len({c['criterion_id'] for c in criteria}) != len(criteria):
        raise ValueError('Criterion IDs must be unique.')
    for c in criteria:
        if not str(c['name']).strip() or not str(c['description']).strip():
            raise ValueError('Every criterion needs a name and description.')
        if number(c['max_score']) <= 0 or number(c['weight']) < 0:
            raise ValueError('Maximum scores must be positive and weights nonnegative.')
    if not math.isclose(sum(number(c['weight']) for c in active), 100, abs_tol=1e-6):
        raise ValueError('Active weights must total 100%.')
    return active


def validate(raw, criteria, text):
    warnings = []
    if isinstance(raw, str):
        try:
            raw = json.loads(raw)
        except (ValueError, TypeError):
            raw = {}
            warnings.append('Malformed JSON: all criteria defaulted to zero.')
    if not isinstance(raw, dict):
        raw = {}
        warnings.append('Expected a JSON object; all criteria defaulted to zero.')
    rows = raw.get('criteria', [])
    if not isinstance(rows, list):
        rows = []
        warnings.append('criteria was not a list.')
    by_id = {}
    known = {c['criterion_id'] for c in criteria}
    for row in rows:
        if not isinstance(row, dict):
            warnings.append('Ignored a non-object criterion.')
            continue
        try:
            cid = int(str(row.get('criterion_id')))
        except (ValueError, TypeError):
            warnings.append('Ignored an invalid criterion ID.')
            continue
        if cid not in known:
            warnings.append(f'Ignored inactive/unknown criterion {cid}.')
        elif cid in by_id:
            warnings.append(f'Duplicate criterion {cid}: first result retained.')
        else:
            by_id[cid] = row
    normalized = []
    clean_text = ' '.join(text.split()).casefold()
    for c in criteria:
        cid = c['criterion_id']
        row = by_id.get(cid, {})
        if not row:
            warnings.append(f'{c["name"]}: missing; assigned zero.')
        if 'max_score' in row:
            try:
                if number(row['max_score']) != c['max_score']:
                    warnings.append(f'{c["name"]}: model maximum overridden by database maximum.')
            except (ValueError, TypeError, OverflowError):
                warnings.append(f'{c["name"]}: invalid model maximum overridden by database maximum.')
        try:
            score = number(row.get('score', 0))
        except (ValueError, TypeError, OverflowError):
            score = 0
            warnings.append(f'{c["name"]}: invalid score; assigned zero.')
        clipped = min(max(score, 0), c['max_score'])
        if clipped != score:
            warnings.append(f'{c["name"]}: score clipped to permitted range.')
        evidence = row.get('evidence', '')
        evidence = evidence.strip() if isinstance(evidence, str) else ''
        # Exact quote check after whitespace/case normalization, not semantic verification.
        grounded = bool(evidence) and ' '.join(evidence.split()).casefold() in clean_text
        if clipped > 0 and not grounded:
            warnings.append(f'{c["name"]}: missing/unmatched evidence; assigned zero.')
            clipped = 0
        justification = row.get('justification', '')
        if not isinstance(justification, str) or not justification.strip():
            justification = 'No justification supplied.'
            warnings.append(f'{c["name"]}: justification missing.')
        normalized.append({**c, 'score': clipped, 'evidence': evidence,
                           'evidence_verified': grounded, 'justification': justification})
    risks = raw.get('risks', [])
    return {'criteria': normalized, 'warnings': warnings,
            'risks': [r for r in risks if isinstance(r, str)] if isinstance(risks, list) else [],
            'overall_summary': raw.get('overall_summary', '') if isinstance(raw.get('overall_summary', ''), str) else ''}


def rank(suppliers, criteria):
    if not suppliers:
        raise ValueError('Supply at least one supplier.')
    names = [s['supplier_name'].strip().casefold() for s in suppliers]
    if any(not n for n in names) or len(set(names)) != len(names):
        raise ValueError('Supplier names must be nonempty and unique (ignoring case).')
    for s in suppliers:
        date.fromisoformat(s['submission_date'])
        if not 0 <= number(s['experience_rating']) <= 10:
            raise ValueError('Historical experience must be between 0 and 10.')
    benchmarks = {c['criterion_id']: max(next(r['score'] for r in s['criteria']
                  if r['criterion_id'] == c['criterion_id']) for s in suppliers) for c in criteria}
    for s in suppliers:
        absolute = ppi = 0.0
        for row in s['criteria']:
            best = benchmarks[row['criterion_id']]
            relative = 100 * row['score'] / best if best else 0.0
            row.update(benchmark=best, gap=row['score'] - best, relative_percent=relative)
            absolute += row['score'] / row['max_score'] * row['weight']
            ppi += relative * row['weight'] / 100
        s.update(absolute_score=absolute, ppi=ppi)
    # Round only for sorting equality at floating-point noise precision; UI uses 2 decimals.
    suppliers.sort(key=lambda s: (-round(s['ppi'], 12), s['submission_date'],
                                  -number(s['experience_rating']), s['supplier_name'].casefold()))
    for i, supplier in enumerate(suppliers, 1):
        supplier['final_rank'] = i
        supplier['rank_reason'] = 'Highest PPI in this batch.' if i == 1 else explain(suppliers[i-2], supplier)
    return suppliers


def explain(previous, current):
    if round(previous['ppi'], 12) != round(current['ppi'], 12):
        return f'Placed after {previous["supplier_name"]}: lower PPI.'
    if previous['submission_date'] != current['submission_date']:
        return f'PPI tied with {previous["supplier_name"]}; earlier submission wins.'
    if previous['experience_rating'] != current['experience_rating']:
        return f'PPI/date tied with {previous["supplier_name"]}; higher experience wins.'
    return f'PPI/date/experience tied with {previous["supplier_name"]}; alphabetical name wins.'

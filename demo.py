"""One successful persisted run and one validation/error case, without API calls."""
import json
from pathlib import Path
from core import validate
from storage import init_db, get_criteria
from workflow import run_batch

ROOT = Path(__file__).parent


def main():
    init_db()
    inputs = [{'supplier_name': p.stem, 'submission_date': f'2026-10-{20+i:02}',
               'experience_rating': [7,3,8,9][i], 'pdf_bytes': p.read_bytes()}
              for i, p in enumerate(sorted((ROOT/'samples').glob('*.pdf')))]
    run = run_batch(inputs, 'Demo')
    (ROOT/'sample_run.json').write_text(json.dumps(run, indent=2), encoding='utf-8')
    for s in run['suppliers']:
        print(f'{s["final_rank"]}. {s["supplier_name"]}: absolute={s["absolute_score"]:.2f}, PPI={s["ppi"]:.2f}')
    bad = validate('{bad JSON', get_criteria(), 'No supporting evidence.')
    (ROOT/'validation_example.json').write_text(json.dumps(bad, indent=2), encoding='utf-8')
    print('\nValidation example: malformed JSON -> five zero scores and explicit warnings.')
    print('Saved sample_run.json and validation_example.json.')


if __name__ == '__main__':
    main()

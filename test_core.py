import copy
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch
from core import validate, rank, check_criteria
from storage import init_db, get_criteria, save_criteria, save_run, load_run
from workflow import run_batch, extract_pdf


class EvaluationTests(unittest.TestCase):
    def setUp(self):
        scratch = Path(__file__).parent / 'data' / 'test-temp'
        scratch.mkdir(parents=True, exist_ok=True)
        self.tmp = tempfile.TemporaryDirectory(dir=scratch)
        self.db = Path(self.tmp.name) / 'test.sqlite3'
        init_db(self.db)
        self.criteria = get_criteria(self.db)

    def tearDown(self):
        self.tmp.cleanup()

    def supplier(self, name='A', scores=None, submitted='2026-01-01', experience=5):
        raw = {'criteria': [{'criterion_id': c['criterion_id'], 'score': s, 'evidence': 'proof', 'justification': 'test'}
                           for c, s in zip(self.criteria, scores or [5]*5)]}
        return {**validate(raw, self.criteria, 'proof'), 'supplier_name': name,
                'submission_date': submitted, 'experience_rating': experience}

    def test_hand_calculated_scores(self):
        ranked = rank([self.supplier('A', [10]*5), self.supplier('B', [5]*5)], self.criteria)
        self.assertEqual([(s['absolute_score'], s['ppi']) for s in ranked], [(100,100),(50,50)])
        self.assertEqual(ranked[1]['criteria'][0]['gap'], -5)

    def test_zero_benchmark(self):
        s = self.supplier()
        for row in s['criteria']:
            row['score'] = 0
        self.assertEqual(rank([s], self.criteria)[0]['ppi'], 0)

    def test_every_tie_break(self):
        rows = [self.supplier('Z', submitted='2026-01-02', experience=10),
                self.supplier('C', experience=4), self.supplier('B', experience=8), self.supplier('A', experience=8)]
        self.assertEqual([s['supplier_name'] for s in rank(rows, self.criteria)], ['A','B','C','Z'])

    def test_invalid_json_and_missing(self):
        result = validate('not json', self.criteria, 'proof')
        self.assertEqual(len(result['criteria']), 5)
        self.assertTrue(all(r['score'] == 0 for r in result['criteria']))
        self.assertTrue(result['warnings'])

    def test_normalization(self):
        raw = {'criteria': [{'criterion_id': 1, 'score': 99, 'evidence': 'proof'},
                            {'criterion_id': 1, 'score': 2}, {'criterion_id': 2, 'score': 'NaN'},
                            {'criterion_id': 3, 'score': True}, {'criterion_id': 4, 'score': 7, 'evidence': 'invented'},
                            {'criterion_id': 999, 'score': 10}]}
        result = validate(raw, self.criteria, 'proof')
        self.assertEqual([r['score'] for r in result['criteria']], [10,0,0,0,0])
        self.assertGreaterEqual(len(result['warnings']), 5)

    def test_weights_and_snapshot(self):
        changed = copy.deepcopy(self.criteria)
        changed[0]['weight'] = 5
        with self.assertRaises(ValueError):
            save_criteria(changed, self.db)
        self.assertEqual(get_criteria(self.db)[0]['weight'], 30)

    def test_demo_end_to_end_and_persistence(self):
        inputs = [{'supplier_name': p.stem, 'submission_date': '2026-01-01', 'experience_rating': 5,
                   'pdf_bytes': p.read_bytes()} for p in sorted((Path(__file__).parent/'samples').glob('*.pdf'))]
        run = run_batch(inputs, 'Demo', db_path=self.db)
        self.assertEqual(len(run['suppliers']), 4)
        self.assertEqual(run['suppliers'][0]['supplier_name'], 'NexaWorks')
        self.assertTrue(all(not s['warnings'] for s in run['suppliers']))
        self.assertEqual(load_run(run['rfp_run_id'], self.db), run)

    def test_bad_pdf(self):
        with self.assertRaises(ValueError):
            extract_pdf(b'not a pdf')

    def test_api_failure_saves_no_partial_run(self):
        from storage import list_runs
        p = next((Path(__file__).parent/'samples').glob('*.pdf'))
        item = {'supplier_name': 'A', 'submission_date': '2026-01-01', 'experience_rating': 5, 'pdf_bytes': p.read_bytes()}
        with patch('workflow.evaluate_openai', side_effect=ValueError('test API failure')):
            with self.assertRaises(ValueError):
                run_batch([item], 'OpenAI', db_path=self.db)
        self.assertEqual(list_runs(self.db), [])


if __name__ == '__main__':
    unittest.main()

from datetime import date
import json
import os
from pathlib import Path
import streamlit as st
from storage import init_db, get_criteria, save_criteria, list_runs, load_run
from workflow import run_batch

st.set_page_config(page_title='RFP Evaluation Studio', page_icon='📊', layout='wide')
init_db()
st.title('RFP Evaluation Studio')
st.caption('Evidence-backed supplier scorecards. Transparent Python scoring and peer ranking.')

with st.sidebar:
    st.header('Evaluation settings')
    st.caption('Evaluator: OpenAI')
    secret_key = os.environ.get('OPENAI_API_KEY', '')
    try:
        secret_key = st.secrets.get('OPENAI_API_KEY', secret_key)
    except (FileNotFoundError, st.errors.StreamlitSecretNotFoundError):
        pass
    api_key = st.text_input('OpenAI API key', value=secret_key, type='password')
    model = st.text_input('JSON-capable OpenAI model ID', value=os.environ.get('OPENAI_MODEL', 'gpt-4o-mini'))
    st.caption('The key stays in this session and is never written to the database. Live mode sends extracted proposal text to OpenAI.')

criteria_tab, evaluate_tab, results_tab, learn_tab = st.tabs(['1 · Criteria', '2 · Suppliers', '3 · Results', 'How it works'])
with criteria_tab:
    st.subheader('Configure the evaluation')
    st.write('Active weights must total 100%. Each batch stores a snapshot so later edits do not change old results.')
    rows = get_criteria(active_only=False)
    for row in rows:
        row['is_active'] = bool(row['is_active'])
    edited = st.data_editor(rows, disabled=['criterion_id'], hide_index=True, key='criteria_editor')
    if st.button('Save criteria'):
        try:
            save_criteria(edited)
            st.success('Criteria saved. New batches will use these settings.')
        except (ValueError, TypeError) as exc:
            st.error(str(exc))

with evaluate_tab:
    st.subheader('Upload supplier proposals')
    st.write('Historical experience uses a 0–10 scale. Submission date and experience break PPI ties only.')
    samples = Path(__file__).parent / 'samples'
    with st.expander('Download the four fictional sample proposals'):
        for pdf in sorted(samples.glob('*.pdf')):
            st.download_button(pdf.stem, pdf.read_bytes(), pdf.name, 'application/pdf', key=pdf.name)
    use_samples = st.checkbox('Use all four bundled sample proposals', value=True)
    files = list(sorted(samples.glob('*.pdf'))) if use_samples else st.file_uploader('Supplier PDFs (15 MB / 30 pages each)', type=['pdf'], accept_multiple_files=True)
    inputs = []
    defaults = {'Apex Systems': 7, 'BrightPath Tech': 3, 'NexaWorks': 8, 'Orbit Digital': 9}
    for i, file in enumerate(files or []):
        name = file.stem if use_samples else Path(file.name).stem
        with st.expander(name, expanded=True):
            a, b, c = st.columns(3)
            supplier = a.text_input('Supplier name', name, key=f'name_{i}_{name}')
            submitted = b.date_input('Submission date', date(2026, 10, 20 + i), key=f'date_{i}_{name}')
            experience = c.number_input('Historical experience / 10', 0.0, 10.0, float(defaults.get(name, 5)), step=0.5, key=f'exp_{i}_{name}')
            inputs.append({'supplier_name': supplier.strip(), 'submission_date': submitted.isoformat(),
                           'experience_rating': experience, 'pdf_bytes': file.read_bytes() if use_samples else file.getvalue()})
    if st.button('Evaluate suppliers', type='primary', disabled=not inputs):
        try:
            with st.spinner('Extracting, evaluating, validating and ranking...'):
                st.session_state['run'] = run_batch(inputs, 'OpenAI', api_key, model)
            st.success('Run saved. Open the Results tab to review the leaderboard and evidence.')
        except Exception as exc:
            st.error(str(exc) if isinstance(exc, ValueError) else 'Evaluation failed. No partial leaderboard was saved. Check your setup and retry.')

with results_tab:
    runs = [r for r in list_runs() if load_run(r['rfp_run_id']).get('mode') == 'OpenAI']
    selection = st.selectbox('Previously saved run', ['Current session'] + [r['rfp_run_id'] for r in runs])
    run = st.session_state.get('run') if selection == 'Current session' else load_run(selection)
    if run and run.get('mode') != 'OpenAI':
        run = None
    if not run:
        st.info('Evaluate suppliers to create a leaderboard.')
    else:
        st.caption(f'RFP_RUN_ID: {run["rfp_run_id"]} | {run["mode"]} | {run["created_at"]}')
        fields = ['final_rank', 'supplier_name', 'absolute_score', 'ppi', 'submission_date', 'experience_rating']
        st.dataframe([{k: round(s[k], 2) if isinstance(s[k], float) else s[k] for k in fields} for s in run['suppliers']], hide_index=True)
        st.caption('PPI is relative to this batch. Absolute score measures performance against the maximum score. Both use a 0–100 scale.')
        for s in run['suppliers']:
            with st.expander(f'#{s["final_rank"]} · {s["supplier_name"]} — PPI {s["ppi"]:.2f}'):
                st.write(s['overall_summary'])
                st.info(s['rank_reason'])
                display = ['name', 'score', 'max_score', 'weight', 'benchmark', 'gap', 'relative_percent', 'evidence', 'justification']
                st.dataframe([{k: r[k] for k in display} for r in s['criteria']], hide_index=True)
                for warning in s['warnings']:
                    st.warning(warning)
                for risk in s['risks']:
                    st.write('Risk: ' + risk)
                with st.expander('Audit: extracted document and original evaluation output'):
                    st.text(s['extracted_text'])
                    st.json(s['raw_model_output'])
        st.download_button('Download complete run JSON', json.dumps(run, indent=2, allow_nan=False), f'{run["rfp_run_id"]}.json', 'application/json')

with learn_tab:
    st.markdown('''1. **Load criteria:** SQLite supplies the active weights and scoring rubric.
2. **Extract text:** pypdf reads every page; scans without text are rejected.
3. **Evaluate:** OpenAI returns criterion scores, exact evidence quotes, and explanations for each proposal.
4. **Validate:** Python fills missing criteria with zero, clips out-of-range scores, rejects non-finite values, and checks quoted evidence against the document.
5. **Score:** Absolute score = sum(score / maximum × weight).
6. **Benchmark:** Each criterion uses the highest supplier score. Gap = score − benchmark. Relative % = score / benchmark × 100; a zero benchmark gives 0%.
7. **Rank:** PPI = sum(relative % × weight / 100). Sort by higher PPI, earlier submission, higher experience, then supplier name.
8. **Save:** One SQLite transaction stores the complete run, rubric snapshot, raw evaluation, warnings, and ranked results.

An exact quote check proves the quote occurs in the extracted document. It does not prove the proposal's claims or that the score is appropriate; review the scorecards before procurement decisions.''')

"""Reproducible synthetic PDFs and explicitly labelled demo scorecards."""
import hashlib
import json
from pathlib import Path
from reportlab.lib import colors
from reportlab.lib.styles import getSampleStyleSheet
from reportlab.lib.units import inch
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, PageBreak, Table, TableStyle
from storage import SEED

ROOT = Path(__file__).parent / 'samples'
PROFILES = [
    ('Apex Systems', [9, 7, 6, 9, 7], 'INR 24,00,000', '16 weeks',
     'Modular services expose versioned REST APIs with retry queues and idempotent ERP synchronization. Load tests target 2,000 concurrent users.',
     'Delivery includes discovery in weeks 1-3, integration in weeks 4-10 and acceptance in weeks 11-16. A project manager and four engineers are assigned; client data availability may delay integration.',
     'Encryption uses TLS 1.3 in transit and AES-256 at rest. Role-based access, SSO, audit logs, daily backups and quarterly access reviews are included. Certification evidence is a fictional audit summary, not an independent certificate.',
     'Business-hours support with a 2-hour critical response and 99.5% monthly availability target is included. Two fictional reference projects are listed; after-hours support costs extra.'),
    ('BrightPath Tech', [6, 7, 9, 3, 4], 'INR 11,00,000', '8 weeks',
     'A configurable web portal will connect to the ERP using CSV imports. Real-time synchronization and load-test results are not included.',
     'Delivery is planned in 8 weeks with configuration in weeks 1-3, import scripts in weeks 4-5 and testing in weeks 6-8. Two developers share testing duties; no contingency reserve is budgeted.',
     'HTTPS and password authentication are proposed. Data residency, backup recovery tests, access review frequency and independent compliance evidence are not specified.',
     'Email support is available on business days with a next-day response target. The team has one small fictional implementation and no independently verified enterprise references.'),
    ('NexaWorks', [8, 9, 8, 8, 9], 'INR 18,50,000', '12 weeks',
     'The solution uses documented REST adapters, a staging environment and automated contract tests. Capacity planning targets 1,000 concurrent users; larger workloads require a separate sizing exercise.',
     'A 12-week plan defines discovery, prototype, integration, migration rehearsal and acceptance gates. A RACI assigns a delivery manager, integration lead, three engineers and a QA lead. A two-week risk reserve and weekly risk register reviews are included.',
     'SSO, least-privilege roles, encrypted backups and immutable audit logs are included. Recovery targets are RPO 24 hours and RTO 8 hours. Annual penetration testing is planned; no completed certification is claimed.',
     '24x7 incident intake provides a 1-hour critical response and named escalation owner. Three fictional comparable projects include reference contacts, transition training and monthly service reviews.'),
    ('Orbit Digital', [5, 7, 7, 7, 9], 'INR 17,00,000', '14 weeks',
     'The portal architecture is described at a high level. ERP integration will be finalized during discovery; API contracts, retry behavior and performance targets are not provided.',
     'Delivery takes 14 weeks with discovery, build and user acceptance phases. A senior project manager, two engineers and a part-time tester are assigned. Dependencies are tracked monthly, but detailed acceptance gates are absent.',
     'Role-based access, TLS encryption, daily backups and audit trails are proposed. A security lead reviews releases; retention periods and recovery-time commitments remain to be agreed.',
     'The team reports eight fictional comparable deployments over six years. Three fictional client references and a named service manager are provided. A 2-hour critical response and quarterly service reviews are included.'),
]


def build():
    ROOT.mkdir(exist_ok=True)
    styles = getSampleStyleSheet()
    styles['BodyText'].leading = 16
    fixtures = {}
    for name, scores, price, duration, technical, implementation, security, support in PROFILES:
        path = ROOT / f'{name}.pdf'
        story = []
        def para(text, style='BodyText'):
            story.extend([Paragraph(text, styles[style]), Spacer(1, 12)])
        para(name, 'Title')
        para('Fictional supplier proposal | RFP-2026-PORTAL', 'Heading2')
        para('SYNTHETIC CLASSROOM DATA - All organizations, projects, contacts and claims in this proposal are invented.')
        para('1. Executive summary and requirement', 'Heading2')
        para('The buyer seeks a cloud supplier-onboarding and procurement portal for 500 staff. The common scope is approval workflows, ERP connectivity, SSO, reporting, data migration and administrator training. Each bidder must describe capacity, delivery, total costs and operational support.')
        para(f'{name} proposes delivery in {duration} at a fixed implementation price of {price}. The following sections state our offered scope and limitations.')
        para('2. Proposed solution', 'Heading2')
        para(technical)
        para('The base scope covers supplier registration, approval routing, purchase-request tracking and a reporting dashboard. Buyer staff supply clean master data and approve requirements. New third-party licensing is excluded unless explicitly priced.')
        story.append(PageBreak())
        para('3. Delivery, team and milestones', 'Heading1')
        para(implementation)
        para('The buyer must provide an ERP sandbox, an identity-provider test account and a product owner. Scope changes require a written estimate and approval. Acceptance requires successful user journeys and resolution of critical defects.')
        para('4. Commercial proposal', 'Heading2')
        table = Table([['Item', 'Offer'], ['Implementation (fixed)', price], ['Delivery schedule', duration],
                       ['First-year support', 'Included in fixed price'], ['Tax', 'GST excluded'],
                       ['Cloud hosting', 'Buyer account; usage billed separately'], ['Payment milestones', '30% kickoff / 40% build / 30% acceptance']], colWidths=[2.1*inch, 4.1*inch])
        table.setStyle(TableStyle([('BACKGROUND',(0,0),(-1,0),colors.HexColor('#183653')),('TEXTCOLOR',(0,0),(-1,0),colors.white),('GRID',(0,0),(-1,-1),0.4,colors.lightgrey),('FONTSIZE',(0,0),(-1,-1),9),('TOPPADDING',(0,0),(-1,-1),10),('BOTTOMPADDING',(0,0),(-1,-1),10)]))
        story.extend([table, Spacer(1, 18)])
        para('Assumptions: one ERP instance, English interface and one data migration are included. Travel, custom mobile apps and ongoing cloud consumption are excluded. Renewal pricing after year one is subject to a new quote; this is a total-cost uncertainty.')
        story.append(PageBreak())
        para('5. Security, compliance and risk', 'Heading1')
        para(security)
        para('All claims are illustrative. The buyer should validate security evidence before any real procurement. Key shared risks include delayed sandbox access, poor source data and unapproved scope changes. The supplier will record issues and escalate unresolved dependencies to the buyer sponsor.')
        para('6. Support, experience and references', 'Heading2')
        para(support)
        para('Fictional reference directory: Cedar Training Cooperative, Mira Shah, reference@cedar.example; Blue Lake Services, Arun Das, reference@bluelake.example. These are invented classroom contacts and must not be contacted. Reference availability and comparability should be assessed from the stated project history.')
        para('7. Scope boundaries and confirmation', 'Heading2')
        para('This document is a teaching artifact and is not a contractual offer. Unsupported items should receive conservative evaluation. The evaluation must use only this proposal and the active rubric; no external reputation or unstated capabilities should be assumed.')
        def footer(canvas, doc):
            canvas.setFont('Helvetica', 9)
            canvas.drawString(42, 30, f'{name} | Synthetic RFP response')
            canvas.drawRightString(553, 30, f'Page {doc.page}')
        SimpleDocTemplate(str(path), pagesize=(595,842), rightMargin=42, leftMargin=42,
                          topMargin=45, bottomMargin=48).build(story, onFirstPage=footer, onLaterPages=footer)
        quotes = [technical, implementation, f'{name} proposes delivery in {duration} at a fixed implementation price of {price}.', security, support]
        rows = [{'criterion_id': c[0], 'score': score, 'max_score': 10,
                 'evidence': quote, 'justification': f'Illustrative score based on the stated {c[1].lower()} strengths and limitations. Review the quoted evidence.'}
                for c, score, quote in zip(SEED, scores, quotes)]
        fixtures[hashlib.sha256(path.read_bytes()).hexdigest()] = {'supplier_name': name, 'scorecard': {
            'supplier_name': name, 'criteria': rows, 'risks': ['Fictional claims; not independently verified.', 'Cloud usage and post-year-one support add uncertain cost.'],
            'overall_summary': f'Fixed classroom demonstration scorecard for {name}; not generated by an LLM.'}}
    (ROOT / 'demo_scorecards.json').write_text(json.dumps(fixtures, indent=2), encoding='utf-8')
    print('Created four synthetic proposals and matching demo fixtures.')


if __name__ == '__main__':
    build()

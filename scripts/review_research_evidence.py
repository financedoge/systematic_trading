"""Validate one versioned evidence dossier; no app/database/broker writes."""
import argparse
import json
from pathlib import Path

from systematic_trading.research.evidence_review import assess

ROOT=Path(__file__).resolve().parents[1]


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('dossier',type=Path)
    parser.add_argument('--output',type=Path,required=True)
    args=parser.parse_args()
    result=assess(json.loads(args.dossier.read_text(encoding='utf8')),ROOT,ROOT/'config/research-evidence-policy-v1.json')
    content=json.dumps(result,sort_keys=True,indent=2,allow_nan=False)+'\n'
    if args.output.exists() and args.output.read_text(encoding='utf8')!=content:
        raise FileExistsError('Preserve the earlier review; choose a new output version')
    args.output.parent.mkdir(parents=True,exist_ok=True)
    args.output.write_text(content,encoding='utf8')
    print(json.dumps({k:result[k] for k in ('status','requested_stage','integrity_and_claim_issues','evidence_gaps','authority')}))
    return 0 if result['status']=='research_evidence_reviewable' else 1


if __name__=='__main__':raise SystemExit(main())

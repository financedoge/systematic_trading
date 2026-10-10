"""Freeze and execute the small admitted-universe control, with no broker writes."""
import argparse
from concurrent.futures import ProcessPoolExecutor, ThreadPoolExecutor, as_completed
import json
import os
from pathlib import Path
import sys
import time


def main():
    parser=argparse.ArgumentParser()
    parser.add_argument("stage",choices=["prepare","calculate","native","analyze","report"])
    parser.add_argument("--root",type=Path,required=True)
    parser.add_argument("--broker",type=Path,default=Path("var/research/etf-admission-20261009/ib-identity.json"))
    parser.add_argument("--output",type=Path)
    args=parser.parse_args();root=args.root.resolve()
    os.environ.update(OMP_NUM_THREADS="1",OPENBLAS_NUM_THREADS="1",MKL_NUM_THREADS="1",NUMEXPR_NUM_THREADS="1",PYTHONDONTWRITEBYTECODE="1")
    if args.stage!="prepare":sys.path.insert(0,str(root/"source"))
    from systematic_trading.research.universe_control import prepare,initialize,decision,freeze_decisions,jobs,economics,ARMS,job_name
    from systematic_trading.research.momentum_replay import checked_files,read_json,native_parity
    from systematic_trading.lean.contracts import write_json
    if args.stage=="prepare":
        print(json.dumps(prepare(root,args.broker.resolve())));return
    checked_files(root,"input_manifest.json");p=read_json(root/"protocol.json");started=time.perf_counter()
    progress=dict(stage=args.stage,workers=os.cpu_count(),status="running",completed=[])
    if args.stage=="calculate":
        with ProcessPoolExecutor(max_workers=os.cpu_count(),initializer=initialize,initargs=(str(root),)) as pool:
            freeze_decisions(root,dict(pool.map(decision,sorted(read_json(root/"control.json")))))
            for future in as_completed([pool.submit(economics,j) for j in jobs()]):
                name=future.result();progress["completed"].append(name);print(name,flush=True)
    elif args.stage=="native":
        from systematic_trading.research.compute import available_resources
        resource=available_resources(len(ARMS),"lean");progress["resources"]=resource
        def run(arm):
            name=job_name((arm,5,0));native_parity(root/"bundles"/name,root/"native"/name,
                read_json(root/"data_receipt.json")["image"],cpus=str(resource["cpus_per_run"]));return name
        with ThreadPoolExecutor(max_workers=resource["workers"]) as pool:
            for future in as_completed([pool.submit(run,a) for a in ARMS]):
                name=future.result();progress["completed"].append(name);print(name,flush=True)
    elif args.stage=="analyze":
        from systematic_trading.research.universe_control_analysis import summarize,inference,finalize
        summarize(root)
        with ProcessPoolExecutor(max_workers=os.cpu_count()) as pool:
            uncertainty=list(pool.map(inference,[(str(root),b) for b in p["bootstrap_blocks"]]))
        print(json.dumps(finalize(root,uncertainty)),flush=True)
    else:
        if args.output is None:raise ValueError("--output is required")
        from systematic_trading.research.universe_control_analysis import artifacts
        print(artifacts(root,args.output))
    progress.update(status="succeeded",elapsed_seconds=time.perf_counter()-started)
    write_json(root/(args.stage+"_progress.json"),progress);print(json.dumps(progress),flush=True)


if __name__=="__main__":main()

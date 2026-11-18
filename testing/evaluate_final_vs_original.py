"""End-to-end comparison: original BM25F CombSUM vs final tuned BM25F.
Run from backend/: python -u ../testing/evaluate_final_vs_original.py --queries ../testing/test_queries_final.csv --output ../testing/bm25_final_comparison
"""
from __future__ import annotations
import argparse,csv,json,sys,math,random
from pathlib import Path
from collections import defaultdict
BACKEND=Path(__file__).resolve().parent.parent/'backend'
sys.path.insert(0,str(BACKEND))
from bm25_baseline import INDEX_PATH,search_documents,combsum
from bm25_stopwords import STOP_INDEX_PATH
from evaluate_bm25 import known_positive_metrics,normalize_name
from evaluate_document_weights import aggregate
METRICS=('known_ndcg_at_k','known_mrr_at_k','known_recall_at_k','known_hits_at_k')
CONFIGS=('original','tuned')
def save(path,rows):
    if not rows:return
    with path.open('w',newline='',encoding='utf-8') as f:
        w=csv.DictWriter(f,fieldnames=list(rows[0]));w.writeheader();w.writerows(rows)
def main():
    p=argparse.ArgumentParser()
    p.add_argument('--queries',type=Path,required=True)
    p.add_argument('--output',type=Path,required=True)
    p.add_argument('--original-index',type=Path,default=INDEX_PATH)
    p.add_argument('--tuned-index',type=Path,default=STOP_INDEX_PATH)
    p.add_argument('--depth',type=int,default=100)
    p.add_argument('--top-k',type=int,default=10)
    args=p.parse_args()
    for ix in (args.original_index,args.tuned_index):
        if not (ix/'people.json').exists():p.error(f'Index or people.json not found: {ix}')
    with args.queries.open(newline='',encoding='utf-8-sig') as f:
        reader=csv.DictReader(f)
        if not {'query','query_type','expected_experts'}.issubset(reader.fieldnames or []):p.error('Missing query, query_type, expected_experts columns')
        queries=list(reader)
    original_people=json.loads((args.original_index/'people.json').read_text(encoding='utf-8'))
    tuned_people=json.loads((args.tuned_index/'people.json').read_text(encoding='utf-8'))
    if set(original_people)!=set(tuned_people):
        print('WARNING: researcher sets differ across indexes; check corpus comparability',flush=True)
    metrics=[];rankings=[];cache={}
    for qid,row in enumerate(queries,1):
        query=row['query'].strip()
        if not query:continue
        expected={normalize_name(n) for n in row['expected_experts'].split(';') if n.strip()}
        if query not in cache:
            original_docs=search_documents(query,limit=args.depth,path=args.original_index)
            tuned_docs=search_documents(query,limit=args.depth,path=args.tuned_index)
            cache[query]={
                'original':(len(original_docs),combsum(original_docs,original_people,limit=args.top_k)),
                'tuned':(len(tuned_docs),aggregate(tuned_docs,tuned_people,{'paper':1.,'project':3.,'course':1.},limit=args.top_k))}
        for config,(n_docs,ranked) in cache[query].items():
            vals=known_positive_metrics(ranked,expected,args.top_k)
            metrics.append(dict(query_id=qid,query=query,query_type=row['query_type'],configuration=config,retrieved_document_count=n_docs,expected_expert_count=len(expected),**vals))
            for rank,expert in enumerate(ranked,1):
                rankings.append(dict(query_id=qid,query=query,query_type=row['query_type'],configuration=config,rank=rank,researcher_uuid=expert['uuid'],researcher_name=expert['name'],score=expert['score'],known_positive=int(normalize_name(expert['name']) in expected)))
        if qid%25==0 or qid==len(queries):print(f'Processed {qid}/{len(queries)}',flush=True)
    summary=[]
    for config in CONFIGS:
        for group in ['overall']+sorted(set(x['query_type'] for x in metrics)):
            rows=[x for x in metrics if x['configuration']==config and (group=='overall' or x['query_type']==group)]
            if not rows:continue
            summary.append(dict(configuration=config,query_type=group,queries=len(rows),**{m:sum(float(r[m]) for r in rows)/len(rows) for m in METRICS}))
    paired=[]
    original={r['query_id']:r for r in metrics if r['configuration']=='original'}
    for r in metrics:
        if r['configuration']!='tuned':continue
        a=original[r['query_id']]
        paired.append(dict(query_id=r['query_id'],query=r['query'],query_type=r['query_type'],**{f'delta_{m}':float(r[m])-float(a[m]) for m in METRICS}))
    args.output.mkdir(parents=True,exist_ok=True)
    for name,rows in [('metrics.csv',metrics),('rankings.csv',rankings),('summary.csv',summary),('paired_differences.csv',paired)]:save(args.output/name,rows)
    (args.output/'run_config.json').write_text(json.dumps(dict(original_index=str(args.original_index),tuned_index=str(args.tuned_index),query_count=len(queries),depth=args.depth,top_k=args.top_k,original='no stemming, no stopword removal, equal field weights, CombSUM, equal type weights',tuned='stemming + stopwords, equal field weights, discounted CombSUM, paper:project:course = 1:3:1',notes='Known-positive labels incomplete. Both pipelines use top 100; tuning used same queries so this is an in-sample comparison.'),indent=2),encoding='utf-8')
    for r in summary:
        print(f"{r['configuration']:8} {r['query_type']:10} nDCG={r['known_ndcg_at_k']:.4f} MRR={r['known_mrr_at_k']:.4f} Recall={r['known_recall_at_k']:.4f}")
    print('Saved:',args.output.resolve())
if __name__=='__main__':main()

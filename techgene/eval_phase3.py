"""Phase 3 最终回溯评估"""
from storage.db import get_session, get_latest_scores
from storage.models import Paper, Alert

with get_session() as sess:
    papers = sess.query(Paper).order_by(Paper.published_date).all()
    alerts = sess.query(Alert).count()

print("=== TechGene 最终状态 ===")
print(f"追踪论文: {len(papers)} 篇")
print(f"告警记录: {alerts} 条")
print()

milestones = ['backprop-1986', 'imagenet-2009', 'resnet-2015', 'yolo-2016', 'alphago-2016', 'transformer-2017', 'sd-2022']
dims = ['abstraction', 'interface', 'composability', 'standardization', 'distance', 'medium', 'iteration']
dim_cn = {'abstraction': 'abs', 'interface': 'ifc', 'composability': 'cmp', 'standardization': 'std', 'distance': 'dst', 'medium': 'med', 'iteration': 'itr'}

header = f"{'Paper':28} {'Year':>5} " + " ".join(f"{dim_cn[d]:>4}" for d in dims) + "  Comp"
print(header)
print("-" * 90)

for pid in milestones:
    p = sess.get(Paper, pid)
    if not p:
        continue
    year = p.published_date.year if p.published_date else 0
    scores = get_latest_scores(pid)
    comp = round(sum(scores.values()) / len(scores), 1) if scores else 0
    row = f"{p.title[:28]:28} {year:>5} "
    for d in dims:
        v = scores.get(d, 0)
        row += f"{v:4.1f} "
    row += f"{comp:5.1f}"
    print(row)

print()
import os
db_size = os.path.getsize('data/techgene.db')
print(f"DB size: {db_size/1024:.0f} KB")
print("Timeline: http://139.59.117.164:8080/timeline.html")

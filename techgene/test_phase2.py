"""Phase 2 分析器测试"""
from analyzers.interface import InterfaceAnalyzer
from analyzers.composability import ComposabilityAnalyzer
from analyzers.standardization import StandardizationAnalyzer
from analyzers.distance import DistanceAnalyzer
from analyzers.iteration import IterationAnalyzer
from analyzers.abstraction import AbstractionAnalyzer
from analyzers.medium import MediumAnalyzer

analyzers = [
    AbstractionAnalyzer(), MediumAnalyzer(), InterfaceAnalyzer(),
    ComposabilityAnalyzer(), StandardizationAnalyzer(), DistanceAnalyzer(),
    IterationAnalyzer(),
]

tests = [
    ("Transformer", 2017, "Attention Is All You Need",
     "The dominant sequence transduction models are based on complex recurrent networks. We propose the Transformer, based solely on attention mechanisms, dispensing with recurrence and convolutions entirely."),
    ("ResNet", 2015, "Deep Residual Learning for Image Recognition",
     "Deeper neural networks are more difficult to train. We present a residual learning framework to ease the training of networks that are substantially deeper than those used previously."),
    ("YOLO", 2016, "You Only Look Once: Unified Real-Time Object Detection",
     "We present YOLO, a new approach to object detection. We frame object detection as a regression problem to spatially separated bounding boxes and associated class probabilities."),
]

for name, year, title, abstract in tests:
    paper = {"arxiv_id": name, "title": title, "abstract": abstract,
             "concepts": [], "citation_count": year, "published": f"{year}-06-01"}
    print(f"\n=== {name} ({year}) ===")
    for a in analyzers:
        try:
            r = a.analyze(paper)
            s = r.get("score", 0)
            c = r.get("confidence", 0)
            print(f"  {a.dimension:15}: {s:4.1f}  (conf={c:.1f})")
        except Exception as e:
            print(f"  {a.dimension:15}: ERROR - {e}")

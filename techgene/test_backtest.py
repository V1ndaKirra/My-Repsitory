"""回溯测试：七个里程碑论文的抽象层级评分"""
from analyzers.abstraction import AbstractionAnalyzer

a = AbstractionAnalyzer()

tests = [
    ("Backprop", 1986, [
        {"display_name": "CS", "level": 0, "score": 0.73},
        {"display_name": "AI", "level": 1, "score": 0.54},
        {"display_name": "ANN", "level": 2, "score": 0.41},
        {"display_name": "Backprop", "level": 3, "score": 0.55},
        {"display_name": "Algorithm", "level": 1, "score": 0.39},
    ]),
    ("ImageNet", 2009, [
        {"display_name": "CS", "level": 0, "score": 0.87},
        {"display_name": "AI", "level": 1, "score": 0.52},
        {"display_name": "WordNet", "level": 2, "score": 0.83},
        {"display_name": "IR", "level": 1, "score": 0.50},
        {"display_name": "Cluster", "level": 2, "score": 0.53},
    ]),
    ("ResNet", 2015, [
        {"display_name": "CS", "level": 0, "score": 0.78},
        {"display_name": "AI", "level": 1, "score": 0.72},
        {"display_name": "DL", "level": 2, "score": 0.57},
        {"display_name": "ObjDet", "level": 3, "score": 0.61},
        {"display_name": "ResNet", "level": 3, "score": 0.43},
    ]),
    ("YOLO", 2016, [
        {"display_name": "CS", "level": 0, "score": 0.77},
        {"display_name": "AI", "level": 1, "score": 0.71},
        {"display_name": "ObjDet", "level": 3, "score": 0.81},
        {"display_name": "BBox", "level": 3, "score": 0.68},
    ]),
    ("AlphaGo", 2016, [
        {"display_name": "CS", "level": 0, "score": 0.71},
        {"display_name": "AI", "level": 1, "score": 0.59},
        {"display_name": "RL", "level": 2, "score": 0.61},
        {"display_name": "MCTS", "level": 3, "score": 0.86},
    ]),
    ("Transformer", 2017, [
        {"display_name": "CS", "level": 0, "score": 0.78},
        {"display_name": "AI", "level": 1, "score": 0.72},
        {"display_name": "NLP", "level": 2, "score": 0.65},
        {"display_name": "Transformer", "level": 3, "score": 0.85},
        {"display_name": "MT", "level": 2, "score": 0.60},
    ]),
    ("StableDiff", 2022, [
        {"display_name": "CS", "level": 0, "score": 0.77},
        {"display_name": "AI", "level": 1, "score": 0.59},
        {"display_name": "CV", "level": 1, "score": 0.39},
        {"display_name": "ImgTrans", "level": 3, "score": 0.43},
        {"display_name": "Inpaint", "level": 3, "score": 0.44},
    ]),
]

print(f"{'Tech':15} {'Year':>4} {'Score':>6} {'L3%':>5} {'L2%':>5}")
print("-" * 40)
for name, year, concepts in tests:
    paper = {"arxiv_id": name, "title": name, "concepts": concepts, "abstract": ""}
    r = a.analyze(paper)
    e = r["evidence"]
    print(f"{name:15} {year:4} {r['score']:6.1f} {e['level3_ratio']:5.2f} {e['level2_ratio']:5.2f}")

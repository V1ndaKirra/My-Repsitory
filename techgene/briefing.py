"""技术谱系时间线 HTML 生成器 v2

特性：
- 正确的时间轴（从论文 published_date 获取）
- 全部 7 个维度显示在 tooltip
- 引用关系线（citation edges）展示技术血缘
- 节点大小反映综合评分，颜色反映技术类型
"""

import json
from datetime import datetime
from storage.db import get_session, get_latest_scores
from storage.models import Paper

DIM_NAMES_CN = {
    "abstraction": "抽象层级",
    "interface": "接口通用性",
    "composability": "可组合性",
    "standardization": "标准化效应",
    "distance": "产业距离",
    "medium": "扩散媒介",
    "iteration": "迭代潜力",
}

# 已知的技术血缘关系（citation edges）
# 格式: (source_paper_id, target_paper_id, relationship_label)
KNOWN_EDGES = [
    ("backprop-1986", "resnet-2015", "训练基础"),
    ("backprop-1986", "alphago-2016", "训练基础"),
    ("backprop-1986", "transformer-2017", "优化基础"),
    ("imagenet-2009", "resnet-2015", "基准数据集"),
    ("imagenet-2009", "yolo-2016", "基准数据集"),
    ("resnet-2015", "alphago-2016", "残差模块"),
    ("resnet-2015", "yolo-2016", "主干网络"),
    ("transformer-2017", "sd-2022", "注意力机制"),
]


def generate_timeline() -> str:
    """生成交互式技术谱系时间线 HTML。"""
    with get_session() as sess:
        papers = sess.query(Paper).order_by(Paper.published_date).all()

    # 构建节点数据
    nodes = []
    node_ids = set()
    for p in papers:
        if not p.published_date:
            continue
        # 精确到日: year + day_of_year/365
        day_of_year = p.published_date.timetuple().tm_yday
        year = p.published_date.year + (day_of_year - 1) / 365.0
        
        # 确定性抖动：基于 paper ID 的 hash，避免同一天论文完全重叠
        # 抖动范围 ±0.005 年份 ≈ ±2 天
        hash_val = sum(ord(c) for c in p.id) % 100
        jitter = (hash_val - 50) / 10000.0
        year += jitter
        scores = get_latest_scores(p.id)
        composite = sum(scores.values()) / len(scores) if scores else 0

        nodes.append({
            "id": p.id,
            "name": p.title[:50],
            "year": year,
            "composite": round(composite, 1),
            "scores": {DIM_NAMES_CN.get(k, k): round(v, 1) for k, v in scores.items()},
            "is_milestone": not p.id.startswith("W"),
        })
        node_ids.add(p.id)

    # 过滤边：只保留两端节点都存在的边
    edges = [
        {"source": s, "target": t, "label": label}
        for s, t, label in KNOWN_EDGES
        if s in node_ids and t in node_ids
    ]

    nodes_json = json.dumps(nodes, ensure_ascii=False)
    edges_json = json.dumps(edges, ensure_ascii=False)

    html = f"""<!DOCTYPE html>
<html lang="zh-CN">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>TechGene 技术谱系时间线</title>
<script src="https://cdn.jsdelivr.net/npm/echarts@5.5.0/dist/echarts.min.js"></script>
<style>
  body {{ font-family: -apple-system, 'Microsoft YaHei', sans-serif; margin: 0; background: #0d1117; color: #c9d1d9; }}
  #header {{ padding: 16px 40px; background: #161b22; border-bottom: 1px solid #30363d; display: flex; justify-content: space-between; align-items: center; }}
  #header h1 {{ margin: 0; font-size: 20px; color: #58a6ff; }}
  #header .meta {{ color: #8b949e; font-size: 12px; }}
  #chart {{ width: 100%; height: calc(100vh - 140px); }}
  #legend {{ position: absolute; bottom: 12px; left: 40px; font-size: 12px; color: #8b949e; display: flex; gap: 20px; }}
  .dot {{ display: inline-block; width: 10px; height: 10px; border-radius: 50%; margin-right: 4px; }}
</style>
</head>
<body>
<div id="header">
  <div>
    <h1>🧬 TechGene 技术谱系时间线</h1>
    <span class="meta">节点: {len(nodes)} | 关系线: {len(edges)} | 更新于 {datetime.utcnow().strftime('%Y-%m-%d %H:%M')} UTC</span>
  </div>
  <div style="display:flex; gap:16px; font-size:13px">
    <span><span class="dot" style="background:#58a6ff"></span> 高接口通用性</span>
    <span><span class="dot" style="background:#3fb950"></span> 高可组合性</span>
    <span><span class="dot" style="background:#f0883e"></span> 里程碑</span>
    <span><span class="dot" style="background:#d2a8ff"></span> 其他</span>
  </div>
</div>
<div id="chart"></div>
<script>
var nodes = {nodes_json};
var edges = {edges_json};

var chart = echarts.init(document.getElementById('chart'));

// 里程碑节点放上面，普通节点放下面
var milestoneNodes = nodes.filter(n => n.is_milestone);
var normalNodes = nodes.filter(n => !n.is_milestone);

var yValue = function(n) {{
    return n.is_milestone ? n.composite + 0.8 : n.composite;
}};

var option = {{
  toolbox: {{
    feature: {{
      dataZoom: {{ yAxisIndex: 'none', title: {{ zoom: '框选缩放', back: '还原' }} }},
      restore: {{ title: '重置' }},
      saveAsImage: {{ title: '保存图片', pixelRatio: 2 }},
    }},
    right: 20,
    top: 0,
    iconStyle: {{ borderColor: '#8b949e' }},
    emphasis: {{ iconStyle: {{ borderColor: '#58a6ff' }} }},
  }},
  dataZoom: [
    {{
      type: 'slider',
      xAxisIndex: 0,
      start: 0,
      end: 100,
      height: 20,
      bottom: 8,
      borderColor: '#30363d',
      fillerColor: 'rgba(88,166,255,0.15)',
      handleStyle: {{ color: '#58a6ff' }},
      textStyle: {{ color: '#8b949e' }},
    }},
    {{
      type: 'slider',
      yAxisIndex: 0,
      start: 0,
      end: 100,
      width: 20,
      right: 8,
      borderColor: '#30363d',
      fillerColor: 'rgba(88,166,255,0.15)',
      handleStyle: {{ color: '#58a6ff' }},
      textStyle: {{ color: '#8b949e' }},
    }},
    {{
      type: 'inside',
      xAxisIndex: 0,
      zoomOnMouseWheel: true,
      moveOnMouseMove: true,
    }},
    {{
      type: 'inside',
      yAxisIndex: 0,
      zoomOnMouseWheel: true,
      moveOnMouseMove: true,
    }},
  ],
  tooltip: {{
    trigger: 'item',
    formatter: function(p) {{
      if (p.dataType === 'edge') {{
        return '<b>' + p.data.label + '</b><br/>' + p.data.source + ' → ' + p.data.target;
      }}
      if (!p.data.name) return '';
      var s = p.data.scores || {{}};
      var lines = [
        '<b style=font-size:14px>' + p.data.name + '</b>',
        '<span style=color:#58a6ff>综合: ' + p.value[1].toFixed(1) + '/5</span>',
        '<span style=color:#8b949e>年份: ' + p.value[0] + '</span>',
        '<hr style=margin:4px 0;border-color:#30363d>'
      ];
      var dims = Object.keys(s);
      for (var i = 0; i < dims.length; i++) {{
        var v = s[dims[i]];
        var color = v >= 4 ? '#3fb950' : v >= 3 ? '#d2a8ff' : '#8b949e';
        lines.push(dims[i] + ': <span style=color:' + color + ';font-weight:bold>' + v + '</span>');
      }}
      return lines.join('<br/>');
    }}
  }},
  legend: {{ show: false }},
  animation: true,
  grid: {{ left: 60, right: 30, top: 40, bottom: 40 }},
  xAxis: {{
    type: 'value',
    name: '年份',
    min: 1985,
    max: 2027,
    axisLabel: {{ color: '#8b949e', formatter: function(v) {{ return v.toFixed(0); }} }},
    splitLine: {{ lineStyle: {{ color: '#21262d' }} }},
    nameTextStyle: {{ color: '#8b949e' }},
    scale: true,  // 自适应范围，避免数据挤在边缘
  }},
  yAxis: {{
    type: 'value',
    name: '综合评分',
    min: 2,
    max: 5.5,
    axisLabel: {{ color: '#8b949e' }},
    splitLine: {{ lineStyle: {{ color: '#21262d' }} }},
    nameTextStyle: {{ color: '#8b949e' }},
    scale: true,
  }},
  series: [
    // 关系线（edges）
    {{
      type: 'lines',
      coordinateSystem: 'cartesian2d',
      data: edges.map(function(e) {{
        var s = nodes.find(n => n.id === e.source);
        var t = nodes.find(n => n.id === e.target);
        if (!s || !t) return null;
        return {{
          coords: [[s.year, yValue(s)], [t.year, yValue(t)]],
          label: {{ show: true, formatter: e.label, position: 'middle', color: '#e6edf3', fontSize: 12, fontWeight: 'bold' }},
          name: e.label
        }};
      }}).filter(Boolean),
      lineStyle: {{
        color: '#58a6ff',
        width: 1.5,
        curveness: 0.2,
        type: 'dashed',
        opacity: 0.6,
      }},
      effect: {{
        show: true,
        period: 8,
        trailLength: 0.15,
        symbol: 'arrow',
        symbolSize: 6,
        color: '#f0883e',
      }},
      zlevel: 0,
    }},
    // 里程碑节点
    {{
      type: 'scatter',
      name: '里程碑',
      data: milestoneNodes.map(function(n) {{
        return {{
          value: [n.year, yValue(n)],
          name: n.name,
          scores: n.scores,
          id: n.id
        }};
      }}),
      symbolSize: function(val) {{ return Math.max(18, val[1] * 10); }},  // 高分越大
      itemStyle: {{
        borderColor: '#f0883e',
        borderWidth: 2,
        color: function(p) {{
          var s = p.data.scores || {{}};
          if ((s['接口通用性'] || s['interface']) >= 4) return '#58a6ff';
          if ((s['可组合性'] || s['composability']) >= 3) return '#3fb950';
          return '#d2a8ff';
        }},
        opacity: 0.9,
      }},
      label: {{
        show: true,
        formatter: function(p) {{ return p.data.name.substring(0, 20); }},
        position: 'top',
        color: '#c9d1d9',
        fontSize: 11,
        distance: 8,
      }},
      zlevel: 2,
    }},
    // 普通节点
    {{
      type: 'scatter',
      name: '论文',
      data: normalNodes.map(function(n) {{
        return {{
          value: [n.year, yValue(n)],
          name: n.name,
          scores: n.scores,
          id: n.id
        }};
      }}),
      symbolSize: function(val) {{ return Math.max(10, val[1] * 8); }},  // 高分越大
      itemStyle: {{
        color: function(p) {{
          var s = p.data.scores || {{}};
          if ((s['接口通用性'] || s['interface']) >= 4) return '#58a6ff';
          if ((s['可组合性'] || s['composability']) >= 3) return '#3fb950';
          return '#d2a8ff';
        }},
        opacity: 0.6,
      }},
      zlevel: 1,
    }},
  ]
}};

chart.setOption(option);
window.addEventListener('resize', () => chart.resize());
</script>
</body>
</html>"""

    return html

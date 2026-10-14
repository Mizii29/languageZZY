"""Render measured tables; never invent missing samples or average speed ratios."""
import argparse
import json
import os
from pathlib import Path
import re

from benchmarks.audit import audit
from benchmarks.common import ROOT


def load(path):
    return json.loads(Path(path).read_text(encoding='utf-8'))


def index(summary):
    return {(r['case'],r['n'],r['language'],r['scope']):r for r in summary['statistics']}


def cell(row):
    if row is None:
        return '未测'
    return f"{row['median_ns']/1e6:.4f} ± {row['mad_ns']/1e6:.4f} ({row['samples']})"


def ratio(left,right):
    if not left or not right or left['samples']!=15 or right['samples']!=15:
        return '不比较'
    return f"{left['median_ns']/right['median_ns']:.2f}"


def render(baseline, comparison=None):
    evidence=audit(baseline)
    environment=load(baseline/'environment.json')
    machine=load(baseline/'hardware-supplement.json') if (baseline/'hardware-supplement.json').exists() else environment['machine']
    summary=load(baseline/'summary.json')
    stats=index(summary)
    cases=load(baseline/'cases.json')['cases']
    lines=['# ZZY P07 性能实测报告','',
        '本报告由已保存的原始样本生成表格。ZZY/Python 比较来自未优化的 P06 运行时代码；优化前后对照单列，不能将不同任务或范围的比值平均为一个排名。',
        '',f"基线启动时间：{environment['timestamp']}；Git：`{environment['revision']}`；ZZY {environment['zzy_version']}。",
        f"环境：{environment['os']}；{machine['cpu']}；{machine['logical_processors']} 逻辑处理器；物理内存 {machine['memory_bytes']/1024**3:.2f} GiB。",
        f"Python：`{environment['python']}`；Unicode {environment['unicode']}；GC 开启。资源指纹：`{environment['resource_fingerprint']}`。",
        '', '## 方法与证据','',
        '工作量、算法、预载/输入构造/复位边界与 Python 包装的限制见 [基准说明](../../benchmarks/README.md) 和 [固定清单](../../benchmarks/cases.json)。人工小规模答案及 172 条等价验证与真实 CLI 测试先通过，三档各自还须通过配对结果门禁才计时。',
        '每个范围按种子 20261008 串行交错语言，3 次独立进程预热、15 次样本；原始记录保存真实顺序和批次数。状态每次重建，短任务的批内也复位。read/prepare 每个进程测一次，其他阶段保存批内累计值，表格按 batch 换算每次任务。',
        '表中为 **中位数毫秒 ± MAD 毫秒 (成功样本数)**；MAD 是绝对中位差，不是标准差或置信区间。最小/最大值与全部原始样本另存。超时样本不填 0，不进入速度统计；不足 15 个成功样本的范围不计算比值，避免将超时截断后的快样本当作完整分布。',
        'cli_total 包括受控启动、读文件、准备、输入构造、执行、输出和进程回收；execute 排除准备/输入构造/校验/清理。B05 的 CLI 还打印完整排序结果及原数组，不能将其 CLI 数字当成排序微基准。',
        'prepare：ZZY 包含解码/行索引/哈希及正式 prepare；Python 为 compile。词法/解析/绑定另作独立探针，不把探针三段硬凑成 prepare。Python 不伪造对应内部阶段。',
        '无长期 Program 缓存、Lazy 命中或 NumPy 加速。批内预载 Program 是明确排除解析的 execute 测量条件，不是“已实现缓存”的证据。新进程不等于冷磁盘；系统负载、温度和 CPU 调频未锁定。短 Python 任务受计时开销和批上限影响，见原始 batch，不将本机结果推广到其他平台。',
        '',f"证据审计：{evidence['records']} 条记录，{evidence['equivalence_jobs']} 个三档预检组合，{evidence['measured_jobs']} 个进入测量的组合，{evidence['sample_records']} 条正式样本记录。审计核对输入字节/哈希、环境关联、样本索引/次数、失败配对和由原始记录重算的统计。",'',
        '[环境及版本](../../benchmarks/results/baseline/environment.json) · [原始样本](../../benchmarks/results/baseline/raw.jsonl) · [统计及失败清单](../../benchmarks/results/baseline/summary.json) · [生成输入](../../benchmarks/results/baseline/inputs/)',
        '', '## ZZY 与 Python：固定工作量','',
        '比值为 `T_ZZY / T_Python`，大于 1 表示 ZZY 较慢。B01—B03 为基础算法，B04—B05 为带检查的等价库任务；B07—B09 的语言机制成本不与整数循环混为总排名。','',
        '| 任务 | n | ZZY execute | Python execute | ZZY/Python execute | ZZY CLI | Python CLI |',
        '|---|---:|---:|---:|---:|---:|---:|']
    for case in cases:
        for n in case['sizes']:
            ident=case['id']
            z,p=(stats.get((ident,n,lang,'execute')) for lang in ('zzy','python'))
            lines.append(f'| {ident} | {n} | {cell(z)} | {cell(p)} | {ratio(z,p)} | {cell(stats.get((ident,n,"zzy","cli_total")))} | {cell(stats.get((ident,n,"python","cli_total")))} |')
    lines += ['','## B06 前端分解','',
        '| n | ZZY read | ZZY prepare | 词法探针 | 解析探针 | 绑定探针 | Python read | Python compile |',
        '|---:|---:|---:|---:|---:|---:|---:|---:|']
    for n in (100,1000,10000):
        columns=[stats.get(('B06',n,lang,scope)) for lang,scope in
                 [('zzy','read'),('zzy','prepare'),('zzy','probe_lex'),('zzy','probe_parse'),('zzy','probe_bind'),('python','read'),('python','prepare')]]
        lines.append('| '+str(n)+' | '+' | '.join(map(cell,columns))+' |')
    lines += ['','## 输入构造与清理','',
        '下列开销没有隐藏在“纯执行”之外而不报；全部任务的其余阶段见统计 JSON。initialize 包含独立上下文/命名空间、定义及输入构造。','',
        '| 任务 | n | ZZY initialize | Python initialize | ZZY cleanup | Python cleanup |',
        '|---|---:|---:|---:|---:|---:|']
    for ident in ('B03','B04','B05','B07'):
        for n in (1000,10000,100000):
            columns=[stats.get((ident,n,lang,scope)) for scope in ('initialize','cleanup') for lang in ('zzy','python')]
            lines.append(f'| {ident} | {n} | '+' | '.join(map(cell,columns))+' |')
    lines += ['','## 失败、超时与未测','',
        '30 秒上限作用于整个子进程请求，包括准备、输入构造、校验和清理；不能据此宣称 execute 本身超时。配对门禁失败后，另一语言同一范围也不进入正式计时。所有失败仍保存在原始记录及 summary.failures。','',
        '| 阶段 | 任务/n | 语言 | 范围 | 状态 | 次数 |','|---|---|---|---|---|---:|']
    from collections import Counter
    counts=Counter((r['phase'],r['case'],r['n'],r['language'],r['scope'],r['status']) for r in summary['failures'])
    for (phase,ident,n,language,scope,status),count in sorted(counts.items()):
        lines.append(f'| {phase} | {ident}/{n} | {language} | {scope} | {status} | {count} |')
    if not counts:
        lines.append('| — | — | — | — | 无失败 | 0 |')
    if comparison:
        compared=load(comparison/'summary.json')
        meta=load(comparison/'environment.json')
        measured=index(compared)
        lines += ['','## 优化前后：独立交错实验','',
            f"before：`{meta['variants']['before']['revision']}`；after：`{meta['variants']['after']['revision']}`。",
            '两版从 Git 取出独立运行时快照，使用同一隔离启动器、同一份生成输入和相同有效资源配置，版本/范围按同一种子交错；3 次预热、15 次样本、batch=1。这里的 CLI 包含两边相同的 runpy 隔离启动器，不能与上表直接相除。',
            '加速比为 `T_before / T_after`，大于 1 才更快；没有完整样本则不计算。此实验只支持所列工作量的优化结论，未重新测全部 B01—B09 或优化后与 Python 的完整矩阵。','',
            '| 任务/n | 范围 | before | after | before/after |','|---|---|---:|---:|---:|']
        for ident in meta['cases']:
            for scope in ('cli_total','prepare','initialize','execute','cleanup'):
                before,after=(measured.get((ident,meta['n'],label,scope)) for label in ('before','after'))
                lines.append(f'| {ident}/{meta["n"]} | {scope} | {cell(before)} | {cell(after)} | {ratio(before,after)} |')
        lines += ['',f"对照记录完整：{compared['sampling_complete']}；失败记录：{len(compared['failures'])}。",
            '[对照环境/源码版本](../../benchmarks/results/location-comparison/environment.json) · [对照原始样本](../../benchmarks/results/location-comparison/raw.jsonl) · [对照统计](../../benchmarks/results/location-comparison/summary.json)']
    lines += ['','## 复现命令','',
        '从项目根目录执行；输出目录必须不存在。基线需检出记录中的基准提交（执行源码与 P06 d085c94 相同），或使用相同运行时快照；在当前优化后的版本直接跑基线命令会产生新的优化版测量，不能冒充原基线。不要覆盖历史数据。','',
        '```powershell',
        '& ./.venv/Scripts/python.exe -X utf8 -m benchmarks.run --verify-only --output dist/p07-equivalence-new',
        '& ./.venv/Scripts/python.exe -X utf8 -m benchmarks.run --output benchmarks/results/baseline-new',
        '& ./.venv/Scripts/python.exe -X utf8 -m benchmarks.audit benchmarks/results/baseline',
        '& ./.venv/Scripts/python.exe -X utf8 -m benchmarks.report --baseline benchmarks/results/baseline --output dist/p07-tables.md',
        '```','',
        'run 返回 1 表示存在已记录的失败/超时/门禁未通过；audit 返回成功只代表证据结构完整，不把这些工作量改判为通过。测试及剖析命令、优化决策和未验证范围见后续验收记录。','']
    text='\n'.join(lines)
    text=text.replace('../../benchmarks/results/baseline',
                      '../../'+os.path.relpath(baseline.resolve(),ROOT).replace('\\','/'))
    if comparison:
        text=text.replace('../../benchmarks/results/location-comparison',
                          '../../'+os.path.relpath(comparison.resolve(),ROOT).replace('\\','/'))
    return text


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--baseline',type=Path,required=True)
    parser.add_argument('--comparison',type=Path)
    parser.add_argument('--output',type=Path,required=True)
    args=parser.parse_args()
    text=render(args.baseline,args.comparison)
    def link(match):
        target=ROOT/match.group(1)[6:]
        relative=os.path.relpath(target,args.output.resolve().parent).replace('\\','/')
        return ']('+relative+')'
    text=re.sub(r'\]\((\.\./\.\./[^)]+)\)',link,text)
    args.output.write_text(text,encoding='utf-8')


if __name__=='__main__':main()

"""Render tables only from completed raw measurements; never manufacture samples."""
import json
from pathlib import Path
import statistics

ROOT=Path(__file__).resolve().parent


def main():
    baseline=json.loads((ROOT/'results/baseline.json').read_text(encoding='utf-8'))
    render=json.loads((ROOT/'results/render.json').read_text(encoding='utf-8'))
    seek=json.loads((ROOT/'results/seek-final.json').read_text(encoding='utf-8'))
    assert baseline['driver_passed'] and render['driver_passed'] and seek['driver_passed']
    lines=['# Sketch 实际性能测量', '',
        '日期：2026-10-17。基线先保存，未实施速度优化。最终验收中的资源/状态修复另列复测，不能把不同代码快照混为同一组样本。', '',
        '## 方法与等价性', '',
        '同一 Windows 11 / CPython 3.12.14，默认 default-v1 策略；每个场景、规模、语言、测量种类各3次新进程。无预热丢弃，按重复轮交替 ZZY/Python 顺序；计时期间不并行跑本项目测试或其他基准。操作系统文件缓存、CPU调频及桌面系统负载未锁定。原始样本包含命令、版本、策略/指纹、退出码、双流与失败类别。', '',
        'single 为 N 次 forward(1)，一个笔/层；multi 为4笔/4层轮流 forward(1)；batch 为每次最多10000点的 polyline，总线段数 N。单笔与批量是不同对象/历史成本的工作负载，不能仅按线段数宣称调用优化倍数。每个工作负载的 ZZY/Python 对照使用相同宿主几何、0.25曲线误差策略、历史、资源配置和序列化路径；逐点坐标、颜色/线宽、对象/段数、ID、层和笔终态核对固定答案与 SHA256。', '',
        f'实际配对通过 {baseline["equivalent_pairs"]}/{baseline["expected_pairs"]}；进程样本 {len(baseline["samples"])} 个。Python 对照调用同一通用宿主 API，仍使用 ZZY 值/资源模型，因此衡量 AST 调度相对直接宿主调用的成本，不是普通 Python/turtle 的整体速度排名。', '',
        'CLI 墙钟包含进程启动、模块导入、准备、建图、输出与退出；ZZY 使用真实 python -m zzy run，Python 使用配对 worker --generation-only（其模块导入并非与 ZZY 完全一致）。phase worker 将 prepare 与 ready/done 之间的执行分开；recording_nested 是执行内 Edit 建立/提交的嵌套计时，不能再次加到 generation。undo/redo 操作全部历史；seek 包含 Replay 构造及中点→末点→零定位；SVG 不包含磁盘写入，project_save/function_export 包含真实临时目录的原子发布，首次/缓存解码由实际 ZZY Lazy 执行。', '',
        'GUI 在真实 Tk 8.6.12 新进程运行，每个场景规模3次；first_render 为首个 Scene 到分批渲染完成，unchanged_render 验证已有 object:1 的 Tk item ID 保留，seek_render 含队列、回放定位及渲染。GUI 总进程时间还含生成、建窗与关闭，不作为纯渲染时间。单样本进程超时180秒，GUI渲染等待截止90秒。', '',
        '## 完整 CLI 墙钟', '',
        '以下单位秒，格式为中位数 ± 样本标准差（n=3，离散程度不是置信区间）。', '',
        '| 场景 | 线段数 | ZZY | Python 同宿主 |', '|---|---:|---:|---:|']
    def fmt(stats):
        if not stats:return '无成功样本'
        spread=f'{stats["stdev"]:.6f}' if stats['stdev'] is not None else '未定义'
        return f'{stats["median"]:.6f} ± {spread}' + (f' (n={stats["n"]})' if stats['n']!=3 else '')
    lookup={(s['kind'],s['scenario'],s['size'],s['language']):s for s in baseline['summary']}
    for scenario in ('single','batch','multi'):
        for size in (1000,10000,100000):
            lines.append(f'| {scenario} | {size} | '+ ' | '.join(fmt(lookup['cli',scenario,size,l]['statistics'].get('process_wall')) for l in ('zzy','python'))+' |')
    lines+=['','## 准备、生成与历史记录','','| 场景/规模 | 语言 | prepare | generation | recording_nested |','|---|---|---:|---:|---:|']
    for scenario in ('single','batch','multi'):
        for size in (1000,10000,100000):
            for language in ('zzy','python'):
                selected=[s['measurement'] for s in baseline['samples'] if (s['kind'],s['scenario'],s['size'],s['language'])==('phases',scenario,size,language)]
                values=[s['prepare_seconds'] for s in selected]
                stats=lookup['phases',scenario,size,language]['statistics']
                lines.append(f'| {scenario}/{size} | {language} | {statistics.median(values):.6f} ± {statistics.stdev(values):.6f} | {fmt(stats.get("generation"))} | {fmt(stats.get("recording_nested"))} |')
    lines+=['','## 操作阶段（ZZY 基线）','','Python 对照的完整逐阶段统计保留在 baseline.json/summary；下表单位秒。失败不进入成功样本统计。','','| 场景/规模 | undo | redo | seek | SVG | project_save |','|---|---:|---:|---:|---:|---:|']
    for scenario in ('single','batch','multi'):
        for size in (1000,10000,100000):
            stats=lookup['phases',scenario,size,'zzy']['statistics']
            lines.append(f'| {scenario}/{size} | '+' | '.join(fmt(stats.get(k)) for k in ('undo','redo','seek','svg','project_save'))+' |')
    lines+=['','## 图案首次/缓存与峰值内存','','内存为 Windows GetProcessMemoryInfo 的进程 PeakWorkingSetSize，覆盖导入、生成、验证和全部阶段，不是某阶段独占 RSS，也不是 ResourceMeter 逻辑载荷。下列内存为3次峰值的中位数 MiB；每个原始值均保存。','','| 场景/规模 | 首次解码 | 缓存 wake | 函数导出 | ZZY 峰值 | Python 峰值 |','|---|---:|---:|---:|---:|---:|']
    for scenario in ('single','batch','multi'):
        for size in (1000,10000,100000):
            stats=lookup['phases',scenario,size,'zzy']['statistics']
            peaks=[]
            for language in ('zzy','python'):
                values=[s['measurement']['peak_process_working_set_bytes']/1048576 for s in baseline['samples'] if (s['kind'],s['scenario'],s['size'],s['language'])==('phases',scenario,size,language)]
                peaks.append(f'{statistics.median(values):.2f}')
            lines.append(f'| {scenario}/{size} | '+' | '.join([*(fmt(stats.get(k)) for k in ('first_decode','cached_decode','function_export')),*peaks])+' |')
    lines+=['','## 真实 GUI','','| 场景/规模 | 状态计数 | 首次渲染 | 不变刷新 | 中点定位渲染 |','|---|---|---:|---:|---:|']
    for s in render['summary']:
        lines.append(f'| {s["scenario"]}/{s["size"]} | {s["statuses"]} | '+' | '.join(fmt(s['stages'].get(k)) for k in ('first_render','unchanged_render','seek_render'))+' |')
    lines+=['','GUI 初轮27个样本中6个小批量场景断言失败，原始记录保留在 results/render-layout-failed.json。单独诊断确认“不变刷新”期间视口由1×1变为704×504，属于初次布局重绘；测量改为等待窗口已映射、视口有效且渲染完成，仍严格核对item ID。上表只来自重新完整执行的27个样本，21成功、6因消息载荷拒绝，没有将失败初轮并入统计。', '',
        '## 回放资源修复后的专项复测', '',
        'Replay 现在按历史中最大对象列表预留，避免clear后当前空画布导致低估；close释放暂存引用。这是正确性修复，不是速度优化。按同一中点→末点→零定位再次各测3次，原始记录为 results/seek-final.json；基线列来自同场景ZZY phase worker。专项驱动省略其他操作阶段，操作系统时序未锁定，不据此宣称前后加速。', '',
        '| 场景/规模 | 基线 seek | 修复后 seek | 修复后状态 |','|---|---:|---:|---|']
    for s in seek['summary']:
        old=lookup['phases',s['scenario'],s['size'],'zzy']['statistics'].get('seek')
        lines.append(f'| {s["scenario"]}/{s["size"]} | {fmt(old)} | {fmt(s["statistics"])} | {s["statuses"]} |')
    lines+=['','## 失败与限制','','| 场景/规模 | 语言 | 阶段 | 状态/资源 | 次数 |','|---|---|---|---|---:|']
    failures={}
    for s in baseline['samples']:
        for stage,value in s.get('measurement',{}).get('stages',{}).items():
            if value['status']!='ok':
                key=(s['scenario'],s['size'],s['language'],stage,value.get('key',value['status']))
                failures[key]=failures.get(key,0)+1
    for (scenario,size,language,stage,key),count in failures.items():lines.append(f'| {scenario}/{size} | {language} | {stage} | {key} | {count} |')
    for s in render['summary']:
        for status,count in s['statuses'].items():
            if status!='ok':lines.append(f'| {s["scenario"]}/{s["size"]} | GUI | render/seek | {status}（细节见原始样本） | {count} |')
    lines+=['','默认预算允许建图不表示同一上下文还容得下历史副本、JSON、SVG或GUI消息。100000个独立对象会在部分阶段超限；批量折线的对象/历史更少，不能把这个差异归功于语言本身。所有超限都保留键/上限/请求量，没有调高配置、删除失败样本或降低几何精度。表中“无成功样本”包括被拒绝的阶段，以及因前置编码失败而未执行的解码；原始stages中无该键表示未执行。进程级失败/超时另有 status，只有正常采集和固定答案配对通过才允许生成此报告。', '',
        '## 结论与复现', '',
        '直接宿主调用通常比 AST 循环生成快；严格解码、历史/项目序列化的成本不可忽略。Lazy 的再次 wake 避免重复解码，但首次成本仍然存在。已有不可变路径共享、增量历史与 GUI 不变对象复用得到功能和测量验证；本轮没有据此宣传整体更快，也没有将小样本噪声当作优化收益。没有实施额外速度优化；当前优先使用批量几何并保留明确资源失败语义。', '',
        '```powershell', '& ./.venv/Scripts/python.exe -X utf8 -m benchmarks.sketch.run --repeats 3 --output dist/sketch-baseline-reproduction.json', '& ./.venv/Scripts/python.exe -X utf8 -m benchmarks.sketch.render --all --repeats 3 --output dist/sketch-render-reproduction.json', '& ./.venv/Scripts/python.exe -X utf8 -m benchmarks.sketch.seek --all --repeats 3 --output dist/sketch-seek-reproduction.json', '```', '',
        '基线源码快照见 results/baseline-inventory.json（包括未提交的Replay预留修复时的逐文件哈希）及本地基线提交；results/baseline.json 保存108个完整样本与27个固定答案配对。GUI 的 results/render.json 独立保存27个真实桌面样本。最终验收快照、后续资源修复与相关定位复测见 tests/e4/results 与开发记录。重新测量请写入 dist 新文件保留原始证据。', '']
    (ROOT/'README.md').write_text('\n'.join(lines),encoding='utf-8')


if __name__=='__main__':main()

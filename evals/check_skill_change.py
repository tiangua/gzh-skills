#!/usr/bin/env python3
# SPDX-License-Identifier: Apache-2.0
"""技能改动的合入前检查。

把工作区（含未跟踪文件）和某个提交（默认 HEAD）比较，只看 skills/ 下的改动：
  1. 正文过长：SKILL.md 去掉 frontmatter 后超过 --max-lines 行或 --max-chars 字；
  2. 参考文件膨胀：某个技能的 references/、templates/ 文件数比基线多出 --max-new-files 个以上，
     或文件总数超过 --max-files；单个参考文件比基线增长超过 --max-growth 倍且多出 --min-growth-chars 字以上；
  3. 混进流水账：新增的行里出现日期、时刻、“用户说 / 聊天里”、对话标记（“用户：”“User:”“> 某某：”）、
     机器人或账号名、issue/PR 编号（出处后的“YYYY-MM 查阅”除外）。技能里应写成“规则 + 原因 + 影响哪一步”，不写事件经过。

用法：
  python evals/check_skill_change.py                 # 工作区 vs HEAD
  python evals/check_skill_change.py --base HEAD~1   # 工作区 vs 指定提交
  python evals/check_skill_change.py --all           # 不看差异，全量检查所有技能（第 3 项扫全部行）
  python evals/check_skill_change.py --scan 提案.md  # 只做第 3 项，检查待审改动文件里拟写入技能的文字
  python evals/check_skill_change.py --selftest      # 自测检查规则本身
退出码：0 = 通过，1 = 有问题。
"""
from __future__ import annotations

import argparse
import re
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
REF_DIRS = ("references", "templates")

# 机器人、账号等具体名字。可用 --names 追加。
DEFAULT_NAMES = ["X热点", "Lunar", "训练师", "公众号主笔", "tiangua", "phantom", "Grok", "lunar.zhou"]

LOG_PATTERNS = [
    ("日期", re.compile(r"(?<!\d)(?:19|20)\d{2}\s*[-/.年]\s*\d{1,2}(?:\s*[-/.月]\s*\d{1,2}\s*日?)?(?!\d)")),
    ("日期", re.compile(r"(?<!\d)\d{1,2}\s*月\s*\d{1,2}\s*[日号]")),
    ("日期", re.compile(r"(?:昨天|今天|前天|上周[一二三四五六日]|周[一二三四五六日]那次)")),
    ("时刻", re.compile(r"(?<![\d.:])(?:[01]?\d|2[0-3]):[0-5]\d(?::[0-5]\d)?(?![\d:])")),
    ("聊天转述", re.compile(r"(?:用户|老板|他|她|我)(?:说过?|提到|反馈说|要求说|在聊天里)|聊天记录|对话里|群里有人|user said|the user (?:said|asked)", re.I)),
    ("对话标记", re.compile(r"^\s*(?:>\s*)?(?:用户|助手|机器人|User|Assistant|Human|AI|Bot)\s*[:：]", re.I | re.M)),
    ("对话标记", re.compile(r"\[(?:t\d+[us]\d*|inbound|agent)\]", re.I)),
    ("编号", re.compile(r"(?:(?<![\w#])#\d{2,}\b|\b(?:PR|issue|工单)\s*#?\d{2,}\b)", re.I)),
]

# 出处后面的“2026-10 查阅 / accessed”这类查阅日期是来源信息，允许保留。
CITE_DATE = re.compile(r"\d\s*(?:日)?\s*(?:查阅|访问|核对|accessed)", re.I)

# ----------------------------------------------------------------------------- git helpers
def git(*args: str, check=True) -> str:
    r = subprocess.run(["git", "-C", str(ROOT), *args], capture_output=True, text=True)
    if check and r.returncode != 0:
        raise SystemExit(f"git {' '.join(args)} 失败：{r.stderr.strip()}")
    return r.stdout


def base_text(base: str, rel: str) -> str | None:
    r = subprocess.run(["git", "-C", str(ROOT), "show", f"{base}:{rel}"], capture_output=True, text=True)
    return r.stdout if r.returncode == 0 else None


def base_files(base: str, prefix: str) -> list[str]:
    out = git("ls-tree", "-r", "--name-only", base, "--", prefix, check=False)
    return [l for l in out.splitlines() if l]


def changed_skill_files(base: str) -> list[str]:
    tracked = git("diff", "--name-only", base, "--", "skills").splitlines()
    untracked = git("ls-files", "--others", "--exclude-standard", "--", "skills").splitlines()
    return sorted({f for f in tracked + untracked if f})


def added_lines(base: str, rel: str) -> list[tuple[int, str]]:
    """工作区相对 base 新增的行（行号, 内容）。新文件返回全部行。"""
    path = ROOT / rel
    if not path.exists():
        return []
    new = path.read_text(encoding="utf-8").splitlines()
    old = base_text(base, rel)
    if old is None:
        return list(enumerate(new, 1))
    out = git("diff", "-U0", base, "--", rel)
    res, ln = [], 0
    for l in out.splitlines():
        m = re.match(r"^@@ -\d+(?:,\d+)? \+(\d+)(?:,\d+)? @@", l)
        if m:
            ln = int(m.group(1)); continue
        if l.startswith("+") and not l.startswith("+++"):
            res.append((ln, l[1:])); ln += 1
    return res


# ----------------------------------------------------------------------------- checks
def split_body(text: str) -> str:
    m = re.match(r"^---\n.*?\n---\n", text, re.S)
    return text[m.end():] if m else text


def body_problems(text: str, max_lines: int, max_chars: int) -> list[str]:
    body = split_body(text)
    n_lines, n_chars = len(body.strip("\n").splitlines()), len(body)
    probs = []
    if n_lines > max_lines:
        probs.append(f"SKILL.md 正文 {n_lines} 行，超过上限 {max_lines} 行；细节移到 references/ 的已有文件里")
    if n_chars > max_chars:
        probs.append(f"SKILL.md 正文 {n_chars} 字，超过上限 {max_chars} 字；细节移到 references/ 的已有文件里")
    return probs


def ref_problems(old: dict[str, int], new: dict[str, int], a) -> list[str]:
    """old / new：{相对路径: 字数}，只含 references/、templates/ 下的文件。"""
    probs = []
    added = sorted(set(new) - set(old))
    if len(added) > a.max_new_files:
        probs.append(f"新增参考文件 {len(added)} 个（上限 {a.max_new_files}）：{added}；优先补进按主题命名的已有文件")
    if len(new) > a.max_files:
        probs.append(f"参考文件共 {len(new)} 个，超过上限 {a.max_files}")
    for f in sorted(set(new) & set(old)):
        o, n = old[f], new[f]
        if n - o >= a.min_growth_chars and n > o * a.max_growth:
            probs.append(f"{f} 从 {o} 字增长到 {n} 字（超过 {a.max_growth} 倍）；检查是否堆进了流水账或重复内容")
    return probs


def log_problems(lines: list[tuple[int, str]], names: list[str]) -> list[str]:
    probs = []
    in_code = False
    for ln, s in lines:
        if s.strip().startswith("```"):
            in_code = not in_code
        if in_code:
            continue
        for label, rx in LOG_PATTERNS:
            m = rx.search(s)
            if m and label == "日期" and CITE_DATE.search(s[m.start():m.end() + 8]):
                continue  # 出处的查阅日期属于事实来源，不算流水账
            if m:
                probs.append(f"第 {ln} 行有{label}“{m.group(0).strip()}”：{s.strip()[:60]}")
        for n in names:
            if n and n in s:
                probs.append(f"第 {ln} 行有具体机器人 / 账号名“{n}”：{s.strip()[:60]}")
    return probs


# ----------------------------------------------------------------------------- runners
def ref_sizes_worktree(skill: str) -> dict[str, int]:
    d = ROOT / "skills" / skill
    out = {}
    for sub in REF_DIRS:
        for p in (d / sub).rglob("*") if (d / sub).exists() else []:
            if p.is_file():
                try:
                    out[str(p.relative_to(ROOT))] = len(p.read_text(encoding="utf-8"))
                except UnicodeDecodeError:
                    out[str(p.relative_to(ROOT))] = p.stat().st_size
    return out


def ref_sizes_base(base: str, skill: str) -> dict[str, int]:
    out = {}
    for sub in REF_DIRS:
        for f in base_files(base, f"skills/{skill}/{sub}"):
            out[f] = len(base_text(base, f) or "")
    return out


def run(a) -> list[str]:
    names = DEFAULT_NAMES + (a.names or [])
    report: list[str] = []
    if a.scan:
        for f in a.scan:
            lines = list(enumerate(Path(f).read_text(encoding="utf-8").splitlines(), 1))
            if lines and lines[0][1].strip() == "---":  # 跳过待审改动的 frontmatter（proposer 字段可以写机器人名）
                end = next((i for i, (_, s) in enumerate(lines[1:], 1) if s.strip() == "---"), 0)
                lines = lines[end + 1:]
            report += [f"{f}: {p}" for p in log_problems(lines, names)]
        return report
    if a.all:
        skills = sorted(p.name for p in (ROOT / "skills").iterdir() if p.is_dir())
        files_by_skill = {s: [str(p.relative_to(ROOT)) for p in (ROOT / "skills" / s).rglob("*.md")] for s in skills}
    else:
        files_by_skill: dict[str, list[str]] = {}
        for f in changed_skill_files(a.base):
            parts = f.split("/")
            if len(parts) >= 3:
                files_by_skill.setdefault(parts[1], []).append(f)
    for skill, files in sorted(files_by_skill.items()):
        sk = ROOT / "skills" / skill / "SKILL.md"
        if sk.exists():
            report += [f"skills/{skill}: {p}" for p in body_problems(sk.read_text(encoding="utf-8"), a.max_lines, a.max_chars)]
        old = {} if a.all else ref_sizes_base(a.base, skill)
        if not a.all:
            report += [f"skills/{skill}: {p}" for p in ref_problems(old, ref_sizes_worktree(skill), a)]
        elif len(ref_sizes_worktree(skill)) > a.max_files:
            report.append(f"skills/{skill}: 参考文件共 {len(ref_sizes_worktree(skill))} 个，超过上限 {a.max_files}")
        for f in sorted(files):
            if not f.endswith(".md") or not (ROOT / f).exists():
                continue
            lines = (list(enumerate((ROOT / f).read_text(encoding="utf-8").splitlines(), 1)) if a.all
                     else added_lines(a.base, f))
            report += [f"{f}: {p}" for p in log_problems(lines, names)]
    return report


def selftest(a) -> list[str]:
    fails = []
    def expect(name, cond):
        print(f"[{'PASS' if cond else 'FAIL'}] selftest {name}")
        if not cond:
            fails.append(name)
    short = "---\nname: x\ndescription: y\n---\n" + "一行\n" * 10
    long = "---\nname: x\ndescription: y\n---\n" + "一行规则。\n" * (a.max_lines + 5)
    expect("正文短的不报", not body_problems(short, a.max_lines, a.max_chars))
    expect("正文超行数会报", bool(body_problems(long, a.max_lines, a.max_chars)))
    expect("正文超字数会报", bool(body_problems("x" * (a.max_chars + 1), 10**6, a.max_chars)))
    base = {"skills/s/references/a.md": 2000}
    expect("参考文件小幅增长不报", not ref_problems(base, {"skills/s/references/a.md": 2400}, a))
    expect("参考文件翻倍增长会报", bool(ref_problems(base, {"skills/s/references/a.md": 6000}, a)))
    many = dict(base, **{f"skills/s/references/n{i}.md": 100 for i in range(a.max_new_files + 1)})
    expect("一次新增多个参考文件会报", bool(ref_problems(base, many, a)))
    good = ["- **规则**：出处链接和它支撑的句子放在同一段。原因：分开后排版会把链接挪到文末，读者对不上。影响：gzh-draft 步骤 4。",
            "- 封面比例 2.35:1，缩略图 1:1。", "每篇只改 3–5 处。", "上限引自官方文档（2026-10 查阅）。",
            "```", "10:30 写在代码块里不算", "```"]
    expect("正常规则不报", not log_problems(list(enumerate(good, 1)), DEFAULT_NAMES))
    bad = ["2026-10-20 那次发布出了问题，所以要先核对。", "10 月 18 日的稿子标题超长。", "晚上 21:57 跑的那次失败了。",
           "用户说标题不要超过 20 字。", "> 用户：这个不行", "User: please fix", "见 PR #123 的讨论。", "X热点 给的素材要先去重。",
           "[t21u] 提交作者保持不变"]
    hits = [bool(log_problems([(1, s)], DEFAULT_NAMES)) for s in bad]
    expect(f"流水账写法全部被抓到（{sum(hits)}/{len(bad)}）", all(hits))
    return fails


def build_parser() -> argparse.ArgumentParser:
    ap = argparse.ArgumentParser(description="技能改动的合入前检查（工作区 vs 提交）")
    ap.add_argument("--base", default="HEAD", help="对比的提交，默认 HEAD")
    ap.add_argument("--all", action="store_true", help="全量检查所有技能，不看差异")
    ap.add_argument("--scan", nargs="+", metavar="FILE", help="只检查这些文件里有没有流水账写法")
    ap.add_argument("--max-lines", type=int, default=160, help="SKILL.md 正文行数上限（默认 160）")
    ap.add_argument("--max-chars", type=int, default=6000, help="SKILL.md 正文字数上限（默认 6000）")
    ap.add_argument("--max-files", type=int, default=8, help="每个技能 references/+templates/ 文件数上限（默认 8）")
    ap.add_argument("--max-new-files", type=int, default=1, help="一次改动最多新增的参考文件数（默认 1）")
    ap.add_argument("--max-growth", type=float, default=1.5, help="单个参考文件相对基线的增长倍数上限（默认 1.5）")
    ap.add_argument("--min-growth-chars", type=int, default=800, help="增长少于这么多字时不报（默认 800）")
    ap.add_argument("--names", nargs="*", help="额外要拦的机器人 / 账号名")
    ap.add_argument("--selftest", action="store_true", help="自测检查规则")
    return ap


def main(argv=None) -> int:
    a = build_parser().parse_args(argv)
    if a.selftest:
        fails = selftest(a)
        print(f"\nselftest 失败 {len(fails)} 项")
        return 1 if fails else 0
    report = run(a)
    scope = "扫描文件" if a.scan else ("全部技能" if a.all else f"工作区 vs {a.base}")
    for r in report:
        print(f"[FAIL] {r}")
    print(f"\n技能改动检查（{scope}）：{'通过' if not report else f'发现 {len(report)} 个问题'}")
    return 1 if report else 0


if __name__ == "__main__":
    sys.exit(main())

# academic-deai-zh · 中文学术文本去 AI 味

[![CI](https://github.com/Brighthao18/academic-deai-zh/actions/workflows/ci.yml/badge.svg)](https://github.com/Brighthao18/academic-deai-zh/actions/workflows/ci.yml)
[![License: MIT](https://img.shields.io/badge/License-MIT-blue.svg)](LICENSE)

**专注中文学术文本去 AI 味**的 Codex Skill。面向论文、课题申请、综述与研究汇报，优先支持医学与生命科学，帮助改善模板腔、空泛套话、重复铺垫和机械衔接，让文字更自然、清楚。

去 AI 味的同时，保留事实、数字、专业术语、引文、限定条件和作者立场。保留学术语体，优先修改有明确阅读问题的表达；已经清楚的文字可以原样保留。

## 主要改善哪些表达

| 常见问题 | 编辑重点 |
|---|---|
| 模板腔和空泛评价 | 清理没有承载实际信息的铺垫与包装，让研究问题和证据更突出 |
| 重复预告和小结 | 合并确实重复的内容，保留独有的主题、范围和研究目的 |
| 机械衔接和生硬句式 | 依据实际逻辑整理句子与段落衔接，改善翻译腔和难读表达 |
| 冗余表达和含混指代 | 用原文已有信息直接表达动作，明确对象与指代 |

合成示例，仅示意局部表达调整：

> 原文：本研究拟对问卷条目进行逐项核对工作。
>
> 改后：本研究拟逐项核对问卷条目。

整理冗余句法，同时保留“拟开展”的研究状态、核对对象和逐项范围。

## 安装与调用

需要 Python 3.10 或以上；运行与测试只使用 Python 标准库。使用完整编辑流程还需要能加载本地 Skill 的 Codex 会话。

```sh
git clone https://github.com/Brighthao18/academic-deai-zh.git
cd academic-deai-zh
```

直接在这个项目中使用 Codex，即可发现 `.agents/skills/academic-deai-zh`。要在其他项目使用，可运行：

```sh
python -X utf8 tools/install_skill.py
```

默认复制到用户目录的 `.agents/skills/academic-deai-zh`；已有同名目录时拒绝覆盖。也可以用 `--dest <完整目标目录>` 指定位置，目标目录须尚不存在。安装包含许可和来源说明，不改模型配置。技能未出现时重新打开 Codex 会话。路径依据 [OpenAI 官方 Skill 文档](https://learn.chatgpt.com/docs/build-skills)。

安装后直接输入：

```text
用 $academic-deai-zh 给这段论文讨论去 AI 味，采用 standard 模式。
保留医学术语、全部事实、数字、条件、研究状态和引文；输出新文件。
```

支持粘贴文本或 UTF-8 TXT/Markdown 文件。也可要求 `conservative`（局部冗余清理）或 `diagnose`（只诊断）。`standard` 是默认模式；方法、结果和条件密集段会更保守。Word 仅有只读文字提取能力，尚不支持保留格式的回写。

也可从 [Releases](https://github.com/Brighthao18/academic-deai-zh/releases) 下载独立 Skill ZIP。解压后将完整 `academic-deai-zh` 文件夹放入项目或用户的 `.agents/skills`；已有安装时先自行保留副本，再选择新的目标位置。

## 本地工具

Codex 会话负责理解、编辑和语义复核；本地 Python 工具负责定位、计算补丁、检查、回退与导出。独立 CLI 不调用模型，不能自行完成语义改写或证明完全等义。

以下命令只准备任务，不生成改稿。示例是合成材料，没有真实研究数据：

```sh
python -X utf8 .agents/skills/academic-deai-zh/scripts/deai.py prepare --input examples/input.md --output work/task.json --mode standard --genre report
```

| 步骤 | 工具 | 用途 |
|---|---|---|
| 准备 | `prepare` / `scan` | 保留全文，定位段落、保护区与候选问题 |
| 提案 | `build-bundle` | 将模型给出的段落提案编译为补丁，不填写通过判断 |
| 复核 | `review-request --format compact` | 生成完整前后文和待填写的复核模板 |
| 预检 | `check-review` | 检查证据和门控，提供具体错误位置 |
| 应用 | `apply` | 应用有复核证据的事务；失败或存疑时回退 |
| 导出 | `export` | 输出新稿、HTML 差异、说明和检查记录 |

语义复核必须由会话实际完成；不能把模板中的 `unknown` 批量改成 `pass`。机械检查通过只证明有限不变量。完整接口见 [contracts.md](.agents/skills/academic-deai-zh/references/contracts.md)，判断与恢复边界见 [SKILL.md](.agents/skills/academic-deai-zh/SKILL.md)。

## 验证与开发

在全新克隆目录运行：

```sh
python -X utf8 -m unittest discover -s tests
python -X utf8 tools/verify_public.py --tracked
python -X utf8 tools/build_release.py --output-dir dist
```

工程测试覆盖保护区、数字与组别绑定、限定词作用范围、陈旧哈希、补丁事务、回退、上下文引文、导出原稿保护及独立发行包。测试中的语义审阅是明确标记的模拟样例，不是模型调用或人工金标准。CI 在 Windows、Linux 与多个 Python 版本执行这些检查。

“去 AI 味”指改善表达，本工具不判断作者身份或优化 AI 检测器分数。目前没有证据证明本工具总体写作效果优于普通保真提示词；不能根据工程测试宣称效果。详见 [验证边界](docs/validation.md)。

## 开源范围与贡献

[MIT](LICENSE) 适用于公开仓库中本项目的代码、文档和合成示例。公开文件由 [public-files.json](public-files.json) 明确列出；发行包使用相同范围并提供文件哈希。研发语料、第三方文章、私人稿件、模型原始响应、凭证和历史工作目录不在公开范围内。

设计参考和固定版本见 [来源说明](docs/upstream.md)。欢迎提交问题和改进；先阅读 [贡献说明](CONTRIBUTING.md)。提交示例时请使用合成或已授权且脱敏的材料。安全问题见 [SECURITY.md](SECURITY.md)。

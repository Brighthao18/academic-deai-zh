# academic-deai-zh 1.5.0 · 独立 Skill

需要 Python 3.10 或以上；运行工具仅依赖标准库，无需 API Key。

将这个完整文件夹复制到项目或用户目录的 `.agents/skills/academic-deai-zh`，不要覆盖已有安装。在 Codex 会话中输入：

```text
用 $academic-deai-zh 改善这段论文文字，保留全部事实、数字、条件和引文，输出新文件。
```

当前会话完成诊断、编辑与语义复核。独立 CLI 只准备任务、计算补丁、检查、回退和导出，不自行调用模型：

```sh
python -X utf8 scripts/deai.py prepare --input input.md --output work/task.json --mode standard
```

上述命令须在本文件夹内运行，`input.md` 是用户提供的 UTF-8 TXT/Markdown 文件。完整流程见 `SKILL.md` 与 `references/contracts.md`。默认 `standard`，另有 `conservative` 和只诊断的 `diagnose`。

Word 仅支持只读文字提取，不支持保格式回写。检查通过不代表完全等义、人工验证或事实核实；总体写作效果尚未证明。模板中的未知判断必须实际复核，不能自动改成通过。

本包不含研究语料、模型凭证、私人稿件或外部 API 调用脚本。许可见 `LICENSE`，设计来源见 `UPSTREAM.md`。源码、测试和发布记录：[GitHub](https://github.com/Brighthao18/academic-deai-zh)。

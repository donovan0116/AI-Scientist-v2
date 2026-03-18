# AI Scientist-v2 项目技术导读

基于当前仓库真实代码的完整导读，面向首次接手该仓库的开发者。

---

## 1. 项目目标

### 这个项目是做什么的

**AI Scientist-v2** 是一个端到端的**自主科研系统**：从高层研究主题出发，自动生成研究想法、设计并运行实验、分析结果、撰写论文并可选地进行审稿。目标是在**无需人工撰写模板**的前提下，在机器学习等领域完成“workshop 级别”的自动化科学发现，并已产生被同行评审接受的 AI 撰写论文。

### 整体输入与最终输出

- **输入**
  - **Ideation 阶段**：一个 Markdown 主题文件（如 `ai_scientist/ideas/my_research_topic.md`），包含 Title、Keywords、TL;DR、Abstract 等，描述要探索的研究方向。
  - **主实验管线**：Ideation 产出的 JSON 想法文件（如 `ai_scientist/ideas/my_research_topic.json`），可选同名的 `.py` 初始代码（`--load_code`）和 HF 数据集引用（`--add_dataset_ref`）。
- **最终输出**
  - 时间戳命名的实验目录 `experiments/{date}_{idea_name}_attempt_{id}/`；
  - 其中包含：实验日志与树可视化（`logs/0-run/unified_tree_viz.html`）、各阶段 summary JSON、聚合图表（`figures/`）、LaTeX 与 PDF 论文（如 `{timestamp_ideaname}.pdf`），以及可选的审稿结果（`review_text.txt`、`review_img_cap_ref.json`）。

### 与普通“论文总结/写作 agent”的核心区别

- **不依赖人工模板**：v1 依赖人工写好的模板；v2 由 LLM 从主题描述生成想法并细化实验设计。
- **渐进式 Agentic Tree Search (BFTS)**：实验以**树搜索**形式进行——多棵解空间树、每步并行扩展多个节点（写代码→执行→解析指标/反馈→选优或调试），由 **Experiment Manager Agent** 分阶段引导（初始实现 → baseline 调参 → 创意研究 → 消融）。
- **全链路闭环**：Ideation（含 Semantic Scholar 查新）→ 多阶段实验（含多 seed 评估、VLM 对图表的反馈）→ 实验总结 → 引用收集 → 写作 → 审稿，全部在代码内串联。

---

## 2. 顶层结构总览

### 根目录关键文件/文件夹

| 路径 | 作用 |
|------|------|
| `ai_scientist/` | 核心 Python 包：ideation、树搜索、写作、审稿、绘图、工具与想法示例。 |
| `docs/` | 文档（如 `API_NONE_DEBUG.md`、logo、本导读）。 |
| `launch_scientist_bfts.py` | **主管线入口**：读 idea JSON、写 idea.md/idea.json、改写 bfts 配置、跑实验→聚合图→写稿→审稿。 |
| `bfts_config.yaml` | **BFTS/实验与 LLM 配置**：agent 并行度、每阶段迭代数、搜索深度、code/feedback/report 模型等。 |
| `requirements.txt` | Python 依赖（anthropic, openai, omegaconf, pypdf, 等）。 |
| `experiments/` | 每次运行生成的时间戳实验目录（非版本控制）。 |

### Ideation 与主管线的入口对应关系

- **Ideation 入口**：`ai_scientist/perform_ideation_temp_free.py`  
  - 命令行示例：`python ai_scientist/perform_ideation_temp_free.py --workshop-file ai_scientist/ideas/my_research_topic.md --model gpt-4o-2024-05-13 --max-num-generations 20 --num-reflections 5`  
  - 输入：`--workshop-file` 指向的 `.md`；输出：同名 `.json`（如 `my_research_topic.json`）。
- **主管线入口**：`launch_scientist_bfts.py`  
  - 命令行示例：`python launch_scientist_bfts.py --load_ideas ai_scientist/ideas/my_research_topic.json --load_code --add_dataset_ref --model_writeup ... --model_citation ... --model_review ... --num_cite_rounds 20`  
  - 输入：`--load_ideas` 指向的 `.json`（ideation 产出）；输出：`experiments/{date}_{idea_name}_attempt_{id}/` 及其中 PDF 等。

---

## 3. 主流程 / 执行链路

### 从启动命令开始的顺序

**用户运行 Ideation 时：**

1. 执行 `python ai_scientist/perform_ideation_temp_free.py --workshop-file <path>.md ...`
2. 读取 `--workshop-file` 的 Markdown 内容作为 `workshop_description`。
3. 循环 `max_num_generations` 次：每次内层做 `num_reflections` 轮反思；每轮调用 `get_response_from_llm`，解析 ACTION/ARGUMENTS，若为 `SearchSemanticScholar` 则调用 `SemanticScholarSearchTool.use_tool`，若为 `FinalizeIdea` 则把 idea 加入列表并进入下一个 idea。
4. 将全部 idea 写入 `<workshop-file>.replace('.md','.json')`（如 `my_research_topic.json`）。

**用户运行 `launch_scientist_bfts.py` 时：**

1. **解析参数**：`parse_arguments()`，得到 `load_ideas`、`idea_idx`、`load_code`、`add_dataset_ref`、各 model、`skip_writeup`/`skip_review` 等。
2. **设置根目录**：`os.environ["AI_SCIENTIST_ROOT"] = ...`
3. **加载 idea**：`ideas = json.load(open(args.load_ideas))`，取 `idea = ideas[args.idea_idx]`。
4. **建实验目录**：`idea_dir = experiments/{date}_{idea['Name']}_attempt_{attempt_id}`，生成 `idea_path_md`、`idea_path_json`。
5. **可选加载代码**：若 `--load_code`，从与 JSON 同名的 `.py` 读入；若 `--add_dataset_ref`，读 `hf_dataset_reference.py`；合并后写回 `ideas[args.idea_idx]["Code"]`。
6. **idea 转 Markdown**：`idea_to_markdown(idea, idea_path_md, code_path)`（`bfts_utils`）。
7. **写 idea.json**：把当前 idea 存到 `idea_dir/idea.json`。
8. **改写 BFTS 配置**：`edit_bfts_config_file(config_path, idea_dir, idea_path_json)` 复制 `bfts_config.yaml` 到 `idea_dir/bfts_config.yaml`，并设置 `desc_file=idea_path_json`、`workspace_dir=idea_dir`、`data_dir`、`log_dir`。
9. **执行实验**：`perform_experiments_bfts(idea_config_path)`（见下）。
10. **拷贝实验产物**：将 `idea_dir/logs/0-run/experiment_results` 拷到 `idea_dir/experiment_results`（若存在）。
11. **聚合图表**：`aggregate_plots(base_folder=idea_dir, model=args.model_agg_plots)`（`perform_plotting`）。
12. **删除临时 experiment_results**：`shutil.rmtree(idea_dir/experiment_results)`。
13. **保存 token 统计**：`save_token_tracker(idea_dir)`。
14. **若不 skip_writeup**：先 `gather_citations(...)` 得到 `citations_text`，再按 `writeup_type` 调用 `perform_writeup` 或 `perform_icbinb_writeup`（可重试 `writeup_retries` 次）。
15. **若不 skip_review 且未 skip_writeup**：`find_pdf_path_for_review(idea_dir)` 找 PDF，`load_paper` + `perform_review`（LLM）+ `perform_imgs_cap_ref_review`（VLM），写 `review_text.txt`、`review_img_cap_ref.json`。
16. **清理子进程**：用 `psutil` 终止相关 python/torch/mp 进程，`sys.exit(0)`。

**数据流小结**：  
Markdown topic → (ideation) → idea JSON → (launch) idea.md + idea.json + 每实验目录 bfts_config → 实验树与日志 → draft/baseline/research/ablation summary JSON → 聚合图 + citations → LaTeX/PDF → 审稿输出。

---

## 4. 关键模块拆解

### 4.1 `ai_scientist/perform_ideation_temp_free.py`

- **职责**：从高层主题 Markdown 生成多条结构化研究想法（JSON），支持 Semantic Scholar 查新与多轮反思。
- **关键函数**：`generate_temp_free_idea()`：循环生成；每条 idea 内多轮 reflection，解析 ACTION/ARGUMENTS，调用工具或 FinalizeIdea。
- **被谁调用**：仅作为脚本 `__main__` 运行，不被其他模块 import。
- **输入**：`workshop_file` 的 Markdown 内容；**输出**：同路径 `.json` 文件（idea 列表）。

### 4.2 `ai_scientist/treesearch/perform_experiments_bfts_with_agentmanager.py`

- **职责**：BFTS 实验的主入口；加载配置与任务描述、准备 workspace、创建 `AgentManager`、运行实验并生成各阶段 summary。
- **关键**：`perform_experiments_bfts(config_path)`：`load_cfg` → `load_task_desc`（读 `cfg.desc_file`，即 idea JSON 路径，得到 JSON 字符串）→ `backend.compile_prompt_to_md(task_desc)` → `prep_agent_workspace` → `AgentManager(task_desc, cfg, workspace_dir)` → `manager.run(exec_callback, step_callback)`；结束后若 `generate_report` 则 `overall_summarize(manager.journals.items(), cfg)` 写 draft/baseline/research/ablation_summary.json。
- **被谁调用**：`launch_scientist_bfts.py`。
- **注意**：`create_exec_callback` 里使用了未在该文件定义的 `interpreter`；实际执行在 `ParallelAgent` 的 worker 进程内用各自 `Interpreter` 完成，此处 callback 在当前并行路径下可能未被调用（遗留/死代码）。

### 4.3 `ai_scientist/treesearch/agent_manager.py`

- **职责**：实验阶段编排与阶段切换；维护多个 `Stage` 和每个 stage 对应的 `Journal`，判断何时进入下一阶段、何时完成。
- **关键类**：`AgentManager`；`Stage`（name, description, goals, max_iterations, num_drafts, stage_number）；`StageTransition`。
- **关键方法**：`run(exec_callback, step_callback)`：外层按 main stage 循环，内层按 sub-stage 循环；对当前 sub-stage 用 `_create_agent_for_stage(stage)` 得到 `ParallelAgent`，在 `with agent` 下循环 `agent.step(exec_callback)` 并 `step_callback`，再用 `_check_stage_completion` / `_check_substage_completion` 决定是否完成；完成后做 multi-seed eval 与 plot aggregation，然后进入下一 stage。
- **被谁调用**：`perform_experiments_bfts_with_agentmanager.py`。
- **输入**：`task_desc`（idea JSON 的字符串，在 __init__ 里 `json.loads`）、`cfg`、`workspace_dir`；**输出**：通过 `journals` 和 `step_callback` 写日志与 summary，无直接返回值。

### 4.4 `ai_scientist/treesearch/parallel_agent.py`

- **职责**：单阶段内的 BFTS 并行执行：选节点、在进程池中生成/调试/改进代码、执行、解析指标与 VLM 反馈、写回 Journal。
- **关键类**：`ParallelAgent`（含 `Journal`、`_select_parallel_nodes`、`step(exec_callback)`）；`MinimalAgent`（worker 内用于生成 plan/code、解析结果）；`AblationConfig` / `AblationIdea`、`HyperparamTuningIdea`。
- **关键逻辑**：`step()`：`_select_parallel_nodes()` 选出最多 `num_workers` 个待扩展节点（含 None 表示新 draft）→ 为每个提交 `_process_node_wrapper` 到 `ProcessPoolExecutor`；wrapper 内在 worker 里创建 `Interpreter`、`MinimalAgent`，根据父节点是否 buggy、是否 stage2/4 决定 `_draft` / `_debug` / `_improve` / `_generate_hyperparam_tuning_node` / `_generate_ablation_node`，然后 `process_interpreter.run(child_node.code)`，再 `parse_exec_result`、VLM 分析图表等，结果序列化回主进程；主进程用 `Node.from_dict(result_data, self.journal)` 恢复并 `journal.append(result_node)`。
- **被谁调用**：`AgentManager._create_agent_for_stage()` 创建并作为 context manager 使用。
- **输入**：task_desc、cfg、journal、stage_name、best_stage1/2/3_node 等；**输出**：通过写入 `journal` 和 step_callback 的 save_run 产出 tree_plot、journal.json、best_solution_*.py 等。

### 4.5 `ai_scientist/treesearch/journal.py`

- **职责**：解空间树的节点与树结构；单节点评估、选优、生成摘要。
- **关键类**：`Node`（code, plan, metric, is_buggy, parent, children, plot 相关、VLM 反馈等）；`Journal`（nodes 列表、draft_nodes/good_nodes/buggy_nodes、get_best_node、generate_summary）。
- **关键方法**：`Journal.get_best_node(cfg=...)`：可用 LLM 选优（`node_selection_spec`）或按 metric；`generate_summary(include_code, **model_kwargs)`：用 LLM 汇总成功/失败实验。
- **被谁调用**：agent_manager、parallel_agent、log_summarization、config（save_run 里 serialize journal）、tree_export。

### 4.6 `ai_scientist/treesearch/log_summarization.py`

- **职责**：把各阶段的 Journal 整理成 draft/baseline/research/ablation 四类 summary，供写作与绘图使用。
- **关键函数**：`get_stage_summary(journal, stage_name, model, client)`、`update_summary(...)`、`overall_summarize(journals, cfg)`；`get_node_log(node)` 会包含 `exp_results_npy_files` 等路径供后续聚合图使用。
- **被谁调用**：`perform_experiments_bfts_with_agentmanager.py` 在实验结束后调用 `overall_summarize`。

### 4.7 `ai_scientist/treesearch/bfts_utils.py`

- **职责**：idea 与配置的简单转换与写入。
- **关键函数**：`idea_to_markdown(data, output_path, load_code)`：把 idea 字典写成 idea.md，可选追加 Code 块；`edit_bfts_config_file(config_path, idea_dir, idea_path)`：复制并改写 bfts_config，设置 desc_file、workspace_dir、data_dir、log_dir。
- **被谁调用**：`launch_scientist_bfts.py`。

### 4.8 `ai_scientist/treesearch/utils/config.py`

- **职责**：加载与预处理 BFTS 配置；加载任务描述；准备 agent workspace；保存 run（journal + config + tree_plot + best_solution）。
- **关键**：`load_cfg(path)` → `prep_cfg`（解析 data_dir、desc_file、log_dir、workspace_dir、exp_name 等）；`load_task_desc(cfg)`：若 `cfg.desc_file` 存在则 `open(cfg.desc_file).read()`（launch 时即为 idea.json 的内容）；`prep_agent_workspace(cfg)`；`save_run(cfg, journal, stage_name)`。
- **被谁调用**：perform_experiments_bfts、agent_manager、parallel_agent、tree_export 等。

### 4.9 `ai_scientist/perform_plotting.py`

- **职责**：用 LLM 根据各阶段 summary 生成“聚合绘图”脚本，运行后把图放到 `figures/`，供写稿使用。
- **关键**：`aggregate_plots(base_folder, model)`：`build_aggregator_prompt(combined_summaries_str, idea_text)` → LLM 生成 Python 代码 → `extract_code_snippet` → `run_aggregator_script`。
- **被谁调用**：`launch_scientist_bfts.py`。

### 4.10 `ai_scientist/perform_icbinb_writeup.py` / `perform_writeup.py`

- **职责**：根据 idea 与实验 summary、citations 生成 LaTeX 并编译成 PDF；icbinb 为 4 页格式。
- **关键**：`gather_citations(base_folder, num_cite_rounds, small_model)`：多轮调用小模型 + `search_for_papers`（Semantic Scholar），产出 BibTeX 文本；`perform_writeup` / `perform_icbinb_writeup`：读 idea、summary、citations，调 LLM 写 sections，填模板，编译 LaTeX。
- **被谁调用**：`launch_scientist_bfts.py`。

### 4.11 `ai_scientist/tools/semantic_scholar.py`

- **职责**：Semantic Scholar 检索；ideation 与 citation 阶段都会用到。
- **关键**：`SemanticScholarSearchTool.use_tool`、`search_for_papers(query, result_limit)`（可 fallback 到 arXiv）。
- **被谁调用**：`perform_ideation_temp_free.py`、`perform_icbinb_writeup.py`、`perform_writeup.py`。

### 4.12 `ai_scientist/llm.py` / `ai_scientist/vlm.py`

- **职责**：统一封装 OpenAI/Anthropic/OpenRouter/Bedrock 等 LLM 调用；VLM 用于图表分析与审稿。
- **关键**：`create_client(model)`、`get_response_from_llm`、`extract_json_between_markers`；backend 的 `query(..., func_spec=...)` 做结构化输出。
- **被谁调用**：全项目几乎所有需要 LLM/VLM 的模块。

### 4.13 `ai_scientist/treesearch/interpreter.py`

- **职责**：在指定工作目录下执行 Python 代码、捕获输出与异常，返回 `ExecutionResult`。
- **被谁调用**：`parallel_agent` 的 worker 内创建 `Interpreter` 并 `run(code)`。

### 4.14 `ai_scientist/treesearch/utils/tree_export.py`

- **职责**：从 Journal 生成 tree_data.json、tree_plot.html；并可根据各 stage 目录生成 `unified_tree_viz.html`。
- **被谁调用**：`config.save_run()` 里 `tree_export.generate(cfg, journal, save_dir / "tree_plot.html")`；unified 可视化在 tree_export 内部根据 log_dir 的 stage 目录生成。

---

## 5. 配置系统

### `bfts_config.yaml` 结构说明

- **data_dir / log_dir / workspace_dir**：由 `edit_bfts_config_file` 在启动时覆盖为当前实验目录下的 `data`、`logs`、以及 `idea_dir`。
- **desc_file**：同上，被设为当前实验的 `idea_path_json`（idea.json 的路径），`load_task_desc` 会读其内容作为任务描述（JSON 字符串）。
- **exec**：`timeout`（单次代码执行超时）、`agent_file_name`（如 runfile.py）、`format_tb_ipython`。
- **agent**：
  - **type**：`parallel`（与 sequential 二选一）。
  - **num_workers**：每步并行扩展的节点数（并行度）。
  - **steps**：未指定 stage 专用 max_iters 时各阶段共用的步数上限。
  - **stages**：`stage1_max_iters` ~ `stage4_max_iters`，每阶段最大迭代数。
  - **multi_seed_eval.num_seeds**：多 seed 评估的种子数（README 建议 num_workers<3 时与 num_workers 一致，否则 3）。
  - **code / feedback / vlm_feedback**：各用哪个 model、temp、max_tokens（coding、执行结果/错误反馈、图表 VLM 反馈）。
  - **search**：`max_debug_depth`（单条路径最大连续 debug 次数）、`debug_prob`（遇失败时以多大概率尝试 debug）、`num_drafts`（Stage 1 的根节点数/独立树数量）。
- **report**：最终 report 的 model/temp（若启用 generate_report）。
- **generate_report**：是否在实验结束后调用 `overall_summarize` 写 draft/baseline/research/ablation summary。

### 对成本、搜索深度、并行度与成功率影响最大的参数

- **成本**：`agent.code.model`、`agent.feedback.model`、`agent.vlm_feedback.model`、各 stage 的 max_iters 与 `steps`、`num_workers`、`num_drafts`；写作阶段的 `--model_writeup`、`--model_citation`、`--num_cite_rounds`。
- **搜索深度**：`agent.steps`、`agent.stages.stage*_max_iters`、`search.max_debug_depth`、`search.num_drafts`。
- **并行度**：`agent.num_workers`（同时扩展的节点数）。
- **成功率**：README 指出实验阶段使用强模型（如 Claude 3.5 Sonnet）成功率更高；`search.debug_prob`、`max_debug_depth` 影响失败后是否继续尝试修复。

### 配置如何被读取与传递

- **读取**：`utils/config.load_cfg(path)` 使用 OmegaConf 加载 YAML，并执行 `prep_cfg()`（路径解析、exp_name 生成、log_dir/workspace_dir 子目录等）。
- **传递**：`perform_experiments_bfts(idea_config_path)` 传入的是经 `edit_bfts_config_file` 写好的 `idea_dir/bfts_config.yaml`；该 cfg 被传给 `AgentManager` 和 `ParallelAgent`，并一路传到 worker 内的 `MinimalAgent`、`Interpreter` 以及 `log_summarization`、`save_run` 等。

---

## 6. Agent 视角理解

### 功能单元与角色

- **Ideation Agent**（`perform_ideation_temp_free`）：根据主题 Markdown 与 Semantic Scholar 工具，多轮反思生成多条 idea，输出 JSON。
- **Experiment Manager（AgentManager）**：编排 4 个 main stage（初始实现、baseline 调参、创意研究、消融），每个 stage 内可有多个 sub-stage；决定何时完成当前 stage、何时做 multi-seed 与 plot aggregation，并创建/销毁每阶段的 ParallelAgent。
- **Parallel Agent（ParallelAgent + worker 内 MinimalAgent）**：在单阶段内维护 Journal 树，每步选若干节点并行扩展（draft/debug/improve/hyperparam/ablation），在 worker 进程中执行代码、解析指标与 VLM 反馈，结果写回 Journal。
- **Report/Summarization**：`overall_summarize` 将各 stage 的 Journal 整理成四类 summary，供写作与绘图使用。
- **Writing**：`perform_icbinb_writeup` / `perform_writeup` 使用 idea、summary、citations 生成 LaTeX 并编译 PDF。
- **Citation**：`gather_citations` 多轮调用小模型 + Semantic Scholar 检索，产出 BibTeX。
- **Review**：`perform_review`（LLM 审正文）、`perform_imgs_cap_ref_review`（VLM 审图/题注/引用）。

### 协作关系

- **串行阶段**：Ideation → 主管线（实验 → 聚合图 → citations → writeup → review）是顺序的。
- **树搜索扩展**：实验阶段内由 ParallelAgent 做 BFTS——多棵解空间树、每步多节点并行扩展、LLM 选优/反馈/调试，体现“agentic tree search”。
- **Manager–Worker**：AgentManager 为“经理”，为每个 stage 创建 ParallelAgent；“工人”是进程池中的 worker，每个 worker 内运行 MinimalAgent + Interpreter，结果汇总回主进程的 Journal。

---

## 7. 一次完整运行的最小闭环

### 最小可运行路径

1. **准备**
   - 环境：`conda create -n ai_scientist python=3.11`，安装 PyTorch(CUDA)、poppler、chktex，`pip install -r requirements.txt`。
   - 至少设置：`OPENAI_API_KEY`（或所用模型对应 key）；可选 `S2_API_KEY`（Semantic Scholar）。
   - 主题文件：在 `ai_scientist/ideas/` 下放一个 `.md`（参考 `i_cant_believe_its_not_better.md` 结构）。

2. **运行 Ideation**
   - `python ai_scientist/perform_ideation_temp_free.py --workshop-file ai_scientist/ideas/my_research_topic.md --model gpt-4o-2024-05-13 --max-num-generations 2 --num-reflections 3`
   - 得到 `ai_scientist/ideas/my_research_topic.json`。

3. **运行主管线**
   - `python launch_scientist_bfts.py --load_ideas ai_scientist/ideas/my_research_topic.json --idea_idx 0 --model_writeup gpt-4o-2024-11-20 --model_citation gpt-4o-2024-11-20 --model_review gpt-4o-2024-11-20 --model_agg_plots gpt-4o-2024-11-20 --num_cite_rounds 5`
   - 若需要初始代码或 HF 数据集引用，加上 `--load_code`、`--add_dataset_ref`（并确保对应 .py 或 hf_dataset_reference.py 存在）。

4. **中间文件**
   - `experiments/{date}_{idea_name}_attempt_0/idea.md`、`idea.json`、`bfts_config.yaml`
   - `experiments/.../logs/0-run/stage_*` 下：`journal.json`、`config.yaml`、`tree_plot.html`、`best_solution_*.py`、`notes/stage_progress.json`
   - `experiments/.../logs/0-run/draft_summary.json`、`baseline_summary.json`、`research_summary.json`、`ablation_summary.json`
   - `experiments/.../logs/0-run/unified_tree_viz.html`
   - `experiments/.../figures/`、`experiments/.../latex/`、`experiments/.../cached_citations.bib`、`experiments/.../timestamp_ideaname.pdf`

5. **看结果**
   - 树与日志：`experiments/{date}_{idea_name}_attempt_0/logs/0-run/unified_tree_viz.html`。
   - 论文：`experiments/{date}_{idea_name}_attempt_0/{timestamp_ideaname}.pdf`。
   - 审稿（若未 skip_review）：`review_text.txt`、`review_img_cap_ref.json`。

### 最容易出错的 5 个点

1. **desc_file 与 idea 内容**：`edit_bfts_config_file` 把 `desc_file` 设为 idea **JSON** 路径；`load_task_desc` 读的是该文件**原始字节/字符串**，AgentManager 里再 `json.loads(task_desc)`。若 JSON 格式错误或缺少必需键（Title, Abstract, Short Hypothesis, Experiments, Risk Factors and Limitations），会在这里报错。
2. **`--load_code` 但无对应 .py**：若传了 `--load_code` 但不存在与 ideas 文件同名的 `.py`，会警告并继续，但 `idea_to_markdown(..., code_path)` 里若后面仍把 `load_code` 当非空传进去，可能触发 assert（当前实现是 code_path 不存在时置为 None 避免 assert）。
3. **执行环境**：代码在 worker 的 `Interpreter` 中执行，需安装实验可能用到的包（torch、datasets 等）；超时由 `exec.timeout` 控制，长时间训练可能被 kill。
4. **Semantic Scholar 限流/失败**：未设置 `S2_API_KEY` 或 429 时会 fallback 到 arXiv；若仍失败，可考虑跳过 citation 或写稿中的检索逻辑。
5. **LaTeX/PDF 生成**：需系统安装 pdflatex、bibtex；模板与字体缺失会导致写稿阶段失败；PDF 路径或命名不符合 `find_pdf_path_for_review` 的约定时，审稿可能找不到文件。

---

## 8. 代码阅读建议

### 推荐阅读顺序

1. **`launch_scientist_bfts.py`**  
   从入口理清：读 idea → 建目录 → 改配置 → 调实验 → 聚合图 → citations → writeup → review；知道每一步调了哪些模块。

2. **`ai_scientist/treesearch/bfts_utils.py`**  
   短且直观：`idea_to_markdown`、`edit_bfts_config_file` 如何把 idea 和配置落到磁盘。

3. **`ai_scientist/treesearch/utils/config.py`**  
   理解 `load_cfg`、`load_task_desc`、`prep_agent_workspace`、`save_run` 以及 Config 结构，后续所有用 cfg 的地方都依赖这里。

4. **`ai_scientist/treesearch/perform_experiments_bfts_with_agentmanager.py`**  
   看 `perform_experiments_bfts` 的完整流程：cfg → task_desc → workspace → AgentManager → run → overall_summarize；以及 step_callback 如何写 stage 与 summary。

5. **`ai_scientist/treesearch/agent_manager.py`**  
   重点看 `run()` 的双层循环（main stage / sub-stage）、`_create_agent_for_stage`、`_check_stage_completion` / `_check_substage_completion`、multi-seed 与 plot aggregation 的触发时机。

6. **`ai_scientist/treesearch/journal.py`**  
   `Node` 字段与 `Journal` 的 good_nodes、get_best_node、generate_summary；理解树结构和“选优”如何影响后续阶段。

7. **`ai_scientist/treesearch/parallel_agent.py`**  
   先看 `step()` 与 `_select_parallel_nodes()`，再看 `_process_node_wrapper` 在 worker 里如何创建 Interpreter、MinimalAgent，以及 draft/debug/improve/hyperparam/ablation 分支；最后看 `_process_single_node` 的入参与返回（序列化/反序列化 Node）。

8. **`ai_scientist/treesearch/log_summarization.py`**  
   `overall_summarize`、`get_stage_summary`、`get_node_log`（含 exp_results_npy_files），理解四类 summary 如何被写稿与绘图使用。

9. **`ai_scientist/perform_icbinb_writeup.py`**  
   `gather_citations`、`perform_writeup`、与 idea/summary/citations 的读取与 LaTeX 生成流程。

10. **`ai_scientist/perform_ideation_temp_free.py`**  
    工具调用与 FinalizeIdea 的解析逻辑，与主管线解耦，适合最后补全“从主题到 idea”的闭环。

---

## 9. 总结表

| 文件/模块 | 作用 | 是否主链路 | 是否优先阅读 |
|-----------|------|------------|--------------|
| `launch_scientist_bfts.py` | 主管线入口：idea→实验→图→引用→写稿→审稿 | 是 | 是 |
| `bfts_config.yaml` | BFTS/实验与 LLM 配置 | 是 | 是 |
| `ai_scientist/treesearch/perform_experiments_bfts_with_agentmanager.py` | 实验入口与 report 生成 | 是 | 是 |
| `ai_scientist/treesearch/agent_manager.py` | 阶段编排与 stage 切换 | 是 | 是 |
| `ai_scientist/treesearch/parallel_agent.py` | 单阶段 BFTS 并行扩展与 worker 逻辑 | 是 | 是 |
| `ai_scientist/treesearch/journal.py` | 解空间树节点与 Journal | 是 | 是 |
| `ai_scientist/treesearch/utils/config.py` | 配置与任务描述加载、workspace、save_run | 是 | 是 |
| `ai_scientist/treesearch/bfts_utils.py` | idea→md、改写 bfts 配置 | 是 | 是 |
| `ai_scientist/treesearch/log_summarization.py` | 各阶段→draft/baseline/research/ablation summary | 是 | 是 |
| `ai_scientist/perform_plotting.py` | 聚合图脚本生成与执行 | 是 | 中 |
| `ai_scientist/perform_icbinb_writeup.py` | 4 页写稿 + gather_citations | 是 | 是 |
| `ai_scientist/perform_writeup.py` | 8 页写稿 | 是（writeup_type=normal 时） | 中 |
| `ai_scientist/perform_ideation_temp_free.py` | Ideation 脚本入口 | 是（ideation 管线） | 是 |
| `ai_scientist/tools/semantic_scholar.py` | 文献检索（ideation + citation） | 是 | 中 |
| `ai_scientist/llm.py` / `vlm.py` | LLM/VLM 统一接口 | 是 | 中 |
| `ai_scientist/treesearch/backend/` | query、compile_prompt_to_md、多后端 | 是 | 中 |
| `ai_scientist/treesearch/interpreter.py` | 执行 Python 代码 | 是 | 中 |
| `ai_scientist/treesearch/utils/tree_export.py` | 树可视化与 unified_tree_viz | 是 | 低 |
| `ai_scientist/perform_llm_review.py` / `perform_vlm_review.py` | 审稿 | 是（未 skip_review 时） | 低 |
| `ai_scientist/ideas/*.md` / `*.json` | 主题与想法示例 | 输入/示例 | 参考 |
| `docs/` | 文档 | 否 | 按需 |

---

*文档基于当前仓库代码整理，若某处与实现不一致以代码为准；不确定处已标注。*

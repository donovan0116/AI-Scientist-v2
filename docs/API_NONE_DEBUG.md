# 为什么 API 调用会返回 None

本项目的 LLM 调用通过 OpenAI 兼容接口（含 OpenRouter）完成。出现「返回 None」或相关报错时，通常对应下面两种情形之一。

## 1. `completion` 为 None（整次响应对象为空）

**表现**：`TypeError: 'NoneType' object is not subscriptable`，发生在 `completion.choices[0]`。

**可能原因**：

- **`client.chat.completions.create()` 返回了 None**  
  - 某些情况下（如连接异常、超时、或服务端返回异常 body），OpenAI 客户端可能解析不到有效对象，返回 `None`。  
  - 使用 OpenRouter 时，上游返回非标准或错误响应时，也可能被解析成 `None`。

- **backoff 重试后仍得到 None**  
  - `backoff_create` 使用 `on_predicate`，对**返回值**做重试：当 `create()` 返回**假值**（如 `None`、`False`）时会重试。  
  - 若重试多次后仍得到 `None`，最终会把该 `None` 返回给上层，从而出现 `completion is None`。  
  - 当前配置未设置 `max_tries` / `max_time`，理论上会一直重试；若你在别处限制了重试，就可能出现「最后一次仍是 None 并返回」的情况。

**结论**：`completion is None` 表示「整次 API 调用没有拿到有效的 completion 对象」，多为网络/超时/限流或上游返回异常导致。

---

## 2. `choice.message.content` 为 None（有 completion 但文本为空）

**表现**：后续在 `extract_code(completion_text)` 等处把 `None` 当字符串用时报错，或上层逻辑里出现「LLM returned None after all retries」。

**可能原因**：

- **OpenAI/OpenRouter 协议允许 `content` 为空**  
  - 响应里 `message.content` 可以为 `null`（例如只返回了 `tool_calls`、或模型/策略决定不生成文本）。

- **OpenRouter / 具体模型（如 qwen3.5-9b）的偶发行为**  
  - 限流、超时、或某些请求下，上游可能返回 200 但 `content` 为 `null`。  
  - 与「模型是否支持代码生成」无关，更多是单次请求的响应异常。

**结论**：`content is None` 表示「本次请求的 completion 存在，但模型/上游没有返回任何文本内容」。

---

## 如何排查

1. **看日志**  
   - 已在 `backend_openai.py` 中增加诊断日志：  
     - `completion is None` 时会打 `API returned no completion (None)` 并带上 `model`、`messages_count`。  
     - `choices` 为空时会打 `API returned empty choices` 并带上 `model`、`completion_id`。  
     - `message.content is None` 时会打 `API returned message.content=None` 并带上 `model` 和当前 `choice`。  
   - 复现时保留这些日志，便于区分是「整次无 completion」还是「有 completion 但 content 为空」。

2. **确认环境与配额**  
   - 使用 OpenRouter 时：检查 `OPENROUTER_API_KEY`、控制台中的用量与错误率。  
   - 若同一 key 下多进程/多 worker 并发，注意限流与超时。

3. **对比其他模型**  
   - 在 `bfts_config.yaml` 中临时将 `agent.code.model` 换成同 OpenRouter 下其他模型（如 `openrouter/qwen/qwen-2.5-coder-32b`），看是否仍频繁出现 None。  
   - 若仅某个模型/提供商组合易现，可判断为上游或该模型行为。

4. **最小复现**  
   - 用同一 `model`、相同 `messages` 写一个独立脚本多次调用 `client.chat.completions.create()`，观察是否偶发返回 `None` 或 `message.content is None`，并记录当时的 HTTP 状态码与响应 body（可脱敏），便于进一步查 OpenRouter/提供商文档或工单。

---

## 3. “Plan + code extraction failed” 的真实原因

**日志位置**：`ai_scientist/treesearch/parallel_agent.py` 中 `plan_and_code_query()`（约 679、1251 行附近）。

**触发条件**：API 返回了非空 `completion_text`，但 `extract_code(completion_text)` 或 `extract_text_up_to_code(completion_text)` 得到空字符串，导致 `if code and nl_text` 不成立，于是打印 “Plan + code extraction failed, retrying...”。

**失败的真实原因（二选一或同时）**：

| 原因 | 含义 |
|------|------|
| **no natural language before first \`\`\`** | 模型回复里要么没有 \`\`\`，要么第一段 \`\`\` 之前没有内容（或 strip 后为空）。要求是：先有一段自然语言 plan，再跟 \`\`\`python ... \`\`\`。 |
| **no valid \`\`\`python ... \`\`\` block or code failed syntax check** | 没有匹配到 \`\`\`python ... \`\`\` 代码块，或匹配到的块经 `is_valid_python_script()` 检查不是合法 Python，被过滤掉后就没有可用的 code。 |

因此“failed”**不是** API 报错或返回 None，而是**模型输出格式不符合约定**：没有「先文字 + 再 \`\`\`python ... \`\`\`」，或代码块不是合法 Python。

**“giving up” 之后**：当前实现会 `return "", completion_text`，即把**原始 LLM 输出**当作 `code` 交给执行器。那是 Markdown/混合文本，不是纯 Python，所以 “Running code” 通常会报语法错误，看起来像没有进展。日志中已增加 WARNING，提示此时在用原始输出当代码。

**建议**：  
- 使用 `bfts_config.yaml` 里专用于代码的模型（如 `openrouter/qwen/qwen-2.5-coder-32b-instruct`），并在 system prompt 中明确要求「先写简短自然语言计划，再写一个 \`\`\`python ... \`\`\` 代码块」。  
- 复现时看新加的 “(reason: …)” 和（若开启 DEBUG 日志）前 600 字符的响应内容，即可确认是 nl 缺失还是 code 块缺失/非法。

---

## 4. 403 "This model is not available in your region"

**表现**：调用 OpenRouter 上的 Claude（或其它地区限制模型）时出现 `Error code: 403 - This model is not available in your region`。

**原因**：限制的是**请求的出口 IP 所在地区**，不是“机器能不能上外网”。即使本机或 git 能访问外网，若出口 IP 在受限地区，仍会 403。

**解决办法**：让请求通过**代理**发出，使出口 IP 落在允许的地区（例如海外代理）。

1. **设置代理环境变量**（在运行 `launch_scientist_bfts.py` 的同一终端或环境中）：
   - 只对 OpenRouter 走代理：`export OPENROUTER_HTTPS_PROXY=http://你的代理地址:端口`（如 `http://127.0.0.1:7890`）。
   - 或让所有 HTTPS 走代理：`export HTTPS_PROXY=http://你的代理地址:端口`。
2. 然后正常启动脚本。代码会检测上述变量，并为 OpenRouter 的请求使用 `httpx` 客户端走代理。
3. 若代理需认证，格式一般为：`http://user:password@host:port`。

**注意**：`bfts_config.yaml` 里使用 OpenRouter 时模型 ID 必须带前缀 `openrouter/`（如 `openrouter/anthropic/claude-3.5-sonnet`），否则请求会发到默认 OpenAI 端点并可能报错。模型 ID 以 OpenRouter 文档为准（如 [OpenRouter models](https://openrouter.ai/models)）。

---

## 代码位置速查

- 请求发出与 completion 校验：`ai_scientist/treesearch/backend/backend_openai.py`（`query()` 内 `backoff_create` 与 `completion is None` / `choices` 检查）。
- 重试逻辑（对返回值做重试）：`ai_scientist/treesearch/backend/utils.py` 中 `backoff_create`（`@backoff.on_predicate`）。
- 使用 completion 文本并处理 None：`ai_scientist/treesearch/parallel_agent.py` 中 `plan_and_code_query()`，以及 `ai_scientist/treesearch/utils/response.py` 中 `extract_code` / `extract_text_up_to_code`（收到 None 会抛错，便于发现未处理的 API 失败）。
- “Plan + code extraction failed” 的打印与重试：`ai_scientist/treesearch/parallel_agent.py` 的 `plan_and_code_query()`；提取逻辑在 `ai_scientist/treesearch/utils/response.py` 的 `extract_code()`、`extract_text_up_to_code()`。
- OpenRouter 代理：`ai_scientist/treesearch/backend/backend_openai.py` 的 `_openrouter_http_client()` 与 `get_ai_client()`，读取 `OPENROUTER_HTTPS_PROXY` 或 `HTTPS_PROXY`。

Subagent b4feebc3 completed successfully:

Based on my research, here is a comprehensive report on advanced quality control and execution enforcement mechanisms for AI agent systems in 2025-2026.

---

# Advanced Quality Control & Execution Enforcement Mechanisms for AI Agent Systems (2025-2026)

## Executive Summary

The field has matured from "prompt-level guardrails" to **deterministic, multi-layered enforcement architectures**. The most effective systems combine:
- **Separation of concerns** (planning vs execution, reasoning vs authority)
- **Independent verification** (different models, vendors, sessions)
- **Deterministic gates** (schema validation, policy enforcement, SPC)
- **Real-time monitoring** (behavioral fingerprinting, drift detection)
- **Self-healing orchestration** (monitor-diagnose-recover loops)

All mechanisms below are designed to be added to existing Python hook-based systems.

---

## 1. Multi-Model Adversarial Review (C3 Pattern)

**How it works:**
A generator agent produces output, which is reviewed by 1-3 independent critic agents using different models, vendors, and prompt incentives. Critics operate in isolated sessions to prevent conversation contamination. They must explicitly find flaws or provide a structured PASS verdict.

**Why it's effective:**
- Breaks the "self-review monoculture" where AI validates its own blind spots
- Regulatory compliance (SOC 2, HIPAA, EU AI Act) requires "different people, different models, different incentives"
- Cost: ~9× single call (3 agents × 3 rounds) but catches 60-80% more critical defects

**Implementation approach for Python hook system:**
```python
# PostToolUse hook implementation
def adversarial_review_hook(tool_name, tool_input, tool_output):
    if tool_name in HIGH_STAKES_TOOLS:
        critics = [
            {"model": "gpt-4o", "persona": "security_auditor"},
            {"model": "claude-3-5-sonnet", "persona": "production_breaker"},
            {"model": "gemini-2.5-flash", "persona": "readability_checker"}
        ]
        findings = []
        for critic in critics:
            result = run_isolated_critic(critic, tool_input, tool_output)
            if result["verdict"] != "PASS":
                findings.append(result)
        
        # Deduplicate and promote issues caught by 2+ critics
        promoted = deduplicate_findings(findings)
        if promoted:
            raise ReviewBlockedException(promoted)
```

**Cost/complexity tradeoff:**
- **Cost:** High (3-9× token cost per high-stakes operation)
- **Complexity:** Medium (requires model routing, isolated sessions)
- **Best for:** Security changes, auth boundaries, data mutations, irreversible actions

---

## 2. Persona-Based Hostile Reviewers

**How it works:**
Three adversarial personas each MUST find at least one real issue:
- **The Saboteur:** "How do I break this in production?"
- **The New Hire:** "Can I understand this with zero context?"
- **The Security Auditor:** OWASP-informed vulnerability scan

Issues caught by 2+ personas are automatically promoted in severity.

**Why it's effective:**
- Forces perspective shift beyond syntax checking
- Covers orthogonal failure classes (operational, cognitive, security)
- Reduces false positives through deduplication across personas

**Implementation approach for Python hook system:**
```python
# Pre-commit or PostToolUse hook
def persona_review_hook(diff_context):
    personas = {
        "saboteur": load_prompt("saboteur.md"),
        "new_hire": load_prompt("new_hire.md"),
        "security_auditor": load_prompt("security_auditor.md")
    }
    
    findings_by_persona = {}
    for name, prompt in personas.items():
        findings = run_llm_review(prompt, diff_context)
        findings_by_persona[name] = findings
    
    # Promote issues found by 2+ personas
    promoted = find_overlapping_issues(findings_by_persona)
    if promoted:
        return {"verdict": "BLOCK", "findings": promoted}
    return {"verdict": "CONCERNS" if any(findings_by_persona.values()) else "CLEAN"}
```

**Cost/complexity tradeoff:**
- **Cost:** Medium (3× LLM calls per review)
- **Complexity:** Low (prompt engineering, no infrastructure)
- **Best for:** Code reviews, plan validation, architecture decisions

---

## 3. Deterministic Schema Validation Gates

**How it works:**
Agent output passes through a pipeline of deterministic gates before being accepted. Each gate answers one question with a binary pass/fail. Cheap gates run first (JSON validation, required fields), expensive gates run last (API reconciliation, fact-checking). Same input + same config = same verdict, always.

**Why it's effective:**
- Separates probabilistic reasoning from deterministic correctness
- Cannot be reasoned around or jailbroken
- Provides audit trail and replay capability

**Implementation approach for Python hook system:**
```python
# PostToolUse hook wrapper
class DeterministicGate:
    def __init__(self, gate_name, check_func, priority):
        self.gate_name = gate_name
        self.check_func = check_func
        self.priority = priority

gates = [
    DeterministicGate("json_schema", validate_json_schema, 1),
    DeterministicGate("required_fields", check_required_fields, 1),
    DeterministicGate("secret_scan", scan_for_secrets, 2),
    DeterministicGate("url_validation", validate_urls, 2),
    DeterministicGate("api_reconciliation", reconcile_api_calls, 3),
]

def deterministic_gate_hook(tool_output):
    sorted_gates = sorted(gates, key=lambda g: g.priority)
    for gate in sorted_gates:
        result = gate.check_func(tool_output)
        if not result["passed"]:
            log_gate_failure(gate.gate_name, result)
            raise GateBlockedException(gate.gate_name, result["reason"])
    return tool_output
```

**Cost/complexity tradeoff:**
- **Cost:** Low (pure algorithm, no LLM calls)
- **Complexity:** Low (JSON Schema, regex, API calls)
- **Best for:** All agent outputs, especially structured data, API calls

---

## 4. Runtime Policy Enforcement (Reference Monitor)

**How it works:**
A reference monitor intercepts all agent actions before execution and evaluates them against a declarative policy specification (Datalog-derived language). Policies track information flow across agents via a dependency graph. Actions are blocked before execution if they violate policy.

**Why it's effective:**
- Provides deterministic policy enforcement independent of model reasoning
- Tracks transitive information flow and cross-agent provenance
- Prevents prompt injection, confused deputy attacks, privilege escalation

**Implementation approach for Python hook system:**
```python
# PreToolUse hook as reference monitor
class PolicyEnforcer:
    def __init__(self, policy_rules):
        self.policy_rules = policy_rules
        self.dependency_graph = DependencyGraph()
    
    def evaluate_action(self, tool_name, tool_input, agent_state):
        # Build current state from dependency graph
        current_state = self.dependency_graph.get_state(agent_state)
        
        # Evaluate policy rules
        for rule in self.policy_rules:
            if not rule.evaluate(tool_name, tool_input, current_state):
                log_policy_violation(rule, tool_name, tool_input)
                raise PolicyViolationException(rule.name)
        
        # Update dependency graph if action proceeds
        self.dependency_graph.add_action(tool_name, tool_input, agent_state)
        return True

policy_enforcer = PolicyEnforcer(load_policy("policies.datalog"))

def pre_tool_use_hook(tool_name, tool_input):
    policy_enforcer.evaluate_action(tool_name, tool_input, get_agent_state())
```

**Cost/complexity tradeoff:**
- **Cost:** Low (graph traversal, rule evaluation)
- **Complexity:** High (policy language, dependency graph tracking)
- **Best for:** Regulated environments, multi-agent systems, security-critical operations

---

## 5. Plan-Execute Separation with Compiled DAGs

**How it works:**
The planner agent emits a JSON task graph once. The system compiles this into an immutable workflow (e.g., Conductor, Airflow). After compilation, execution is pure deterministic workflow — crash-safe, replay-safe, free of LLM randomness. Retries, parallelism, branching are workflow primitives, not LLM decisions.

**Why it's effective:**
- Two identical plans produce identical executions
- Crash recovery resumes at last completed step, not from scratch
- Testing can use static plans without LLM calls

**Implementation approach for Python hook system:**
```python
# PostPlanning hook
def plan_compile_hook(plan_json):
    # Validate plan structure
    if not validate_plan_dag(plan_json):
        raise InvalidPlanException("Plan must be valid DAG")
    
    # Compile to deterministic workflow
    workflow = compile_to_workflow(plan_json)
    
    # Store compiled workflow for execution
    store_workflow(workflow)
    
    # Return workflow ID for executor
    return {"workflow_id": workflow.id, "steps": len(workflow.nodes)}

# Execution hooks (PreStep, PostStep)
def pre_step_hook(step_id):
    workflow = load_workflow()
    step = workflow.get_step(step_id)
    
    # Check dependencies completed
    if not workflow.dependencies_satisfied(step_id):
        raise DependencyNotReadyException(step_id)
    
    return step

def post_step_hook(step_id, result):
    workflow = load_workflow()
    workflow.mark_complete(step_id, result)
    
    # Determine next steps deterministically
    next_steps = workflow.get_ready_steps()
    return next_steps
```

**Cost/complexity tradeoff:**
- **Cost:** Low (one LLM call per plan, then deterministic)
- **Complexity:** Medium (workflow engine integration)
- **Best for:** Long-horizon tasks, reproducible workflows, CI/CD pipelines

---

## 6. Execution Coverage Matrix Enforcement

**How it works:**
A coverage matrix defines required audit channels for each operation class (tool calls, file mutations, HTTP requests, task lifecycle updates). Before execution, the system verifies that all required audit channels are available and properly configured. Missing channels block execution.

**Why it's effective:**
- Makes "audit everything" concrete and enforceable
- Provides checklist for reviewers
- Ensures reconstructability for investigations

**Implementation approach for Python hook system:**
```python
# PreToolUse hook with coverage matrix
COVERAGE_MATRIX = {
    "file_write": {"channel": "command_audit", "fields": ["path", "actor", "status"]},
    "http_request": {"channel": "loop_audit", "fields": ["run_id", "tool_name", "outcome"]},
    "tool_call": {"channel": "loop_audit", "fields": ["run_id", "session_id", "input_hash", "output_hash"]},
}

def coverage_check_hook(tool_name, tool_input):
    operation_class = classify_operation(tool_name)
    required = COVERAGE_MATRIX.get(operation_class)
    
    if not required:
        raise UncoveredOperationException(operation_class)
    
    # Verify audit channel exists
    if not audit_channel_exists(required["channel"]):
        raise AuditChannelMissingException(required["channel"])
    
    # Verify required fields are capturable
    missing_fields = [f for f in required["fields"] if not can_capture(f, tool_input)]
    if missing_fields:
        raise AuditFieldMissingException(missing_fields)
    
    # Set up audit context
    setup_audit_context(required["channel"], tool_name, tool_input)
```

**Cost/complexity tradeoff:**
- **Cost:** Low (metadata checks)
- **Complexity:** Low (matrix configuration, field validation)
- **Best for:** Compliance, auditability, regulated environments

---

## 7. Behavioral Drift Detection (12-Dimension Fingerprinting)

**How it works:**
System maintains 12-dimensional behavioral fingerprints: JSD decision patterns, Levenshtein tool paths, EMD latency distributions, semantic clusters, bigram tool transitions, verbosity, loop depth, output length, retries, output drift. Bootstrap confidence intervals and minimum detectable effect (MDE) analysis determine statistical significance.

**Why it's effective:**
- Catches silent changes before users notice
- Distinguishes between noise and real drift
- Provides root cause attribution (prompt change, model swap, tool update)

**Implementation approach for Python hook system:**
```python
# PostToolUse hook for drift tracking
class DriftDetector:
    def __init__(self):
        self.baseline = load_baseline_fingerprints()
        self.current_window = []
    
    def update_fingerprint(self, tool_name, tool_input, tool_output, latency):
        fingerprint = {
            "tool_sequence": self.get_tool_sequence(),
            "decision_pattern": self.compute_decision_pattern(),
            "latency_distribution": self.update_latency_dist(latency),
            "output_length": len(tool_output),
            "loop_depth": self.detect_loop_depth(),
            "timestamp": time.time()
        }
        self.current_window.append(fingerprint)
        
        # Check drift every N samples
        if len(self.current_window) >= 100:
            self.check_drift()
    
    def check_drift(self):
        current_stats = compute_window_stats(self.current_window)
        for dim in self.baseline:
            js_divergence = compute_js_divergence(
                current_stats[dim], 
                self.baseline[dim]
            )
            ci = bootstrap_ci(self.current_window, dim)
            
            if js_divergence > ci["upper_bound"]:
                alert_drift(dim, js_divergence, ci)

drift_detector = DriftDetector()

def drift_tracking_hook(tool_name, tool_input, tool_output, latency):
    drift_detector.update_fingerprint(tool_name, tool_input, tool_output, latency)
```

**Cost/complexity tradeoff:**
- **Cost:** Low (statistical computations, no LLM)
- **Complexity:** Medium (fingerprint computation, statistical analysis)
- **Best for:** Production monitoring, model updates, prompt changes

---

## 8. Statistical Process Control (SPC) with Control Charts

**How it works:**
Applies manufacturing SPC techniques to agent outputs. Six quality dimensions (accuracy, hallucination rate, tone, task accuracy, response length, latency) each get X-bar charts with 3σ control limits computed from historical baseline. Western Electric and Nelson rules trigger alerts (run violations, trends, points beyond 3σ).

**Why it's effective:**
- Detects drift 4-8 days before user impact
- Proven 90-year methodology from manufacturing
- Provides statistical confidence, not vibes

**Implementation approach for Python hook system:**
```python
# PostExecution hook for SPC
class SPCMonitor:
    def __init__(self):
        self.control_limits = load_control_limits()
        self.metrics_history = defaultdict(list)
    
    def update_metric(self, metric_name, value):
        self.metrics_history[metric_name].append(value)
        
        # Apply Western Electric rules
        recent = self.metrics_history[metric_name][-20:]
        
        # Rule 1: Point beyond 3σ
        if abs(value - self.control_limits[metric_name]["center"]) > 3 * self.control_limits[metric_name]["sigma"]:
            alert_spc_violation(metric_name, "point_beyond_3sigma", value)
        
        # Rule 2: 9 consecutive points on one side of center
        if all(x > self.control_limits[metric_name]["center"] for x in recent[-9:]):
            alert_spc_violation(metric_name, "run_above_center", recent)
        
        # Rule 3: 6 consecutive increasing/decreasing points
        if is_monotonic_trend(recent[-6:], length=6):
            alert_spc_violation(metric_name, "monotonic_trend", recent)

spc_monitor = SPCMonitor()

def spc_hook(execution_result):
    spc_monitor.update_metric("accuracy", execution_result["accuracy"])
    spc_monitor.update_metric("hallucination_rate", execution_result["hallucination_rate"])
    spc_monitor.update_metric("latency_ms", execution_result["latency_ms"])
```

**Cost/complexity tradeoff:**
- **Cost:** Low (statistical calculations)
- **Complexity:** Low (control chart implementation)
- **Best for:** Production quality monitoring, regression detection

---

## 9. Self-Healing Monitor-Detect-Diagnose-Recover Loop

**How it works:**
A four-stage loop treats reliability as a bounded runtime control problem:
1. **Monitor:** Observe execution patterns and output consistency
2. **Detect:** Identify abnormal behavior via failure signals
3. **Diagnose:** Map signals to failure classes (timeout, malformed args, stale context)
4. **Recover:** Select targeted recovery action under explicit budget (retry, replan, escalate)

**Why it's effective:**
- 98.8% task success vs 94.5% for retry-only
- Reduces silent failures to 0.0% with verifier guidance
- Budgeted recovery prevents infinite loops

**Implementation approach for Python hook system:**
```python
# PostToolUse hook with self-healing
class SelfHealingOrchestrator:
    def __init__(self, recovery_budget=3):
        self.recovery_budget = recovery_budget
        self.recovery_attempts = 0
        self.failure_signals = []
    
    def handle_failure(self, tool_name, error, context):
        failure_class = classify_failure(error, context)
        self.failure_signals.append(failure_class)
        
        if self.recovery_attempts >= self.recovery_budget:
            escalate_to_human(failure_class, self.failure_signals)
            return
        
        recovery_action = select_recovery(failure_class, context)
        self.recovery_attempts += 1
        
        if recovery_action == "retry":
            return retry_with_backoff(tool_name, context)
        elif recovery_action == "replan":
            return replan_from_checkpoint(context)
        elif recovery_action == "fallback_tool":
            return try_fallback_tool(tool_name, context)
        elif recovery_action == "escalate":
            escalate_to_human(failure_class, self.failure_signals)

healer = SelfHealingOrchestrator()

def self_healing_hook(tool_name, tool_input, error):
    if error:
        return healer.handle_failure(tool_name, error, {"input": tool_input})
```

**Cost/complexity tradeoff:**
- **Cost:** Medium (recovery attempts add token cost)
- **Complexity:** Medium (failure classification, recovery strategies)
- **Best for:** Tool-augmented agents, production workloads, critical tasks

---

## 10. Checkpointed Backtracking with Causal Reasoning

**How it works:**
When a failure occurs, the system identifies the affected subtrajectory via a dependency-aware Critical Transition Graph, rewinds to the appropriate checkpoint, and invalidates only downstream steps affected by the failure. Uses cross-iteration Repair Memory to prevent recurrence of the same failure.

**Why it's effective:**
- Repairs 59-65% of initially failed tasks
- Reduces agent turns and token usage vs full replanning
- Targeted recovery vs blunt retry

**Implementation approach for Python hook system:**
```python
# PostStep hook with checkpointing
class CheckpointManager:
    def __init__(self):
        self.checkpoints = {}
        self.dependency_graph = DependencyGraph()
    
    def create_checkpoint(self, step_id, state):
        self.checkpoints[step_id] = {
            "state": copy.deepcopy(state),
            "timestamp": time.time(),
            "dependencies": self.dependency_graph.get_dependencies(step_id)
        }
    
    def backtrack_to_checkpoint(self, failed_step_id):
        # Find affected upstream steps
        affected = self.dependency_graph.get_affected_subgraph(failed_step_id)
        
        # Find latest safe checkpoint
        safe_checkpoint = None
        for step_id in reversed(affected):
            if step_id in self.checkpoints:
                safe_checkpoint = self.checkpoints[step_id]
                break
        
        if not safe_checkpoint:
            return None  # No safe checkpoint, full replan needed
        
        # Restore state
        restore_state(safe_checkpoint["state"])
        
        # Invalidate downstream steps
        for step in affected:
            if step > safe_checkpoint["timestamp"]:
                invalidate_step(step)
        
        return safe_checkpoint

checkpoint_manager = CheckpointManager()

def checkpoint_hook(step_id, state):
    checkpoint_manager.create_checkpoint(step_id, state)

def failure_hook(failed_step_id):
    checkpoint = checkpoint_manager.backtrack_to_checkpoint(failed_step_id)
    if checkpoint:
        return replay_from_checkpoint(checkpoint)
```

**Cost/complexity tradeoff:**
- **Cost:** Medium (checkpoint storage, state copying)
- **Complexity:** High (dependency graph, causal reasoning)
- **Best for:** Long-horizon tasks, expensive operations, stateful workflows

---

## 11. Multi-Model Consensus Engine

**How it works:**
Responses from multiple heterogeneous LLMs are fed into a supervised meta-learner. Features include semantic embeddings, pairwise similarity, clustering statistics, lexical cues, reasoning-quality scores, confidence estimates, and model-specific priors. Gradient-boosted trees, listwise ranking, or graph neural networks determine the most likely correct answer.

**Why it's effective:**
- 4.6-8.1 percentage point accuracy improvement over strongest single LLM
- Outperforms majority vote by 8.1 points
- Reduces hallucinations on TruthfulQA

**Implementation approach for Python hook system:**
```python
# PostToolUse hook for consensus
class ConsensusEngine:
    def __init__(self, models):
        self.models = models
        self.meta_learner = load_meta_learner("consensus_model.pkl")
    
    def get_consensus(self, prompt, tool_input):
        responses = {}
        for model in self.models:
            responses[model] = call_model(model, prompt, tool_input)
        
        # Extract features
        features = self.extract_features(responses)
        
        # Meta-learner predicts best answer
        best_model = self.meta_learner.predict(features)
        
        # Return consensus answer with confidence
        return {
            "answer": responses[best_model],
            "confidence": features[best_model]["confidence"],
            "agreement_score": compute_agreement(responses)
        }
    
    def extract_features(self, responses):
        features = {}
        for model, response in responses.items():
            features[model] = {
                "semantic_embedding": embed(response),
                "confidence": extract_confidence(response),
                "reasoning_quality": score_reasoning(response),
                "pairwise_similarity": {m: similarity(response, responses[m]) for m in responses}
            }
        return features

consensus = ConsensusEngine(["gpt-4o", "claude-3-5-sonnet", "gemini-2.5-flash"])

def consensus_hook(tool_name, tool_input):
    if tool_name in CRITICAL_TOOLS:
        result = consensus.get_consensus(build_prompt(tool_name), tool_input)
        if result["agreement_score"] < 0.7:
            escalate_to_human("Low consensus", result)
        return result["answer"]
```

**Cost/complexity tradeoff:**
- **Cost:** High (N× model calls per operation)
- **Complexity:** Medium (feature extraction, meta-learner)
- **Best for:** High-stakes decisions, accuracy-critical tasks, regulatory compliance

---

## 12. Self-Anchored Consensus (SAC) for Byzantine Faults

**How it works:**
Decentralized iterative filter-and-refine protocol where agents exchange responses, locally evaluate and filter unreliable messages, and refine their own outputs. Provides (F+1)-robustness conditions for communication graphs to ensure honest agents preserve reliable information despite Byzantine influence.

**Why it's effective:**
- Suppresses Byzantine influence without relying on self-reported confidence
- Works across diverse communication topologies
- Provably robust under adversarial conditions

**Implementation approach for Python hook system:**
```python
# PostToolUse hook for SAC
class SelfAnchoredConsensus:
    def __init__(self, agents):
        self.agents = agents
        self.communication_graph = build_graph(agents)
    
    def sac_protocol(self, initial_responses):
        current_responses = initial_responses.copy()
        
        for round_num in range(MAX_ROUNDS):
            new_responses = {}
            
            for agent in self.agents:
                # Get neighbor responses
                neighbors = self.communication_graph.get_neighbors(agent)
                neighbor_responses = [current_responses[n] for n in neighbors]
                
                # Locally evaluate and filter
                filtered = self.filter_unreliable(agent, neighbor_responses)
                
                # Refine own response
                new_responses[agent] = self.refine_response(
                    current_responses[agent], 
                    filtered
                )
            
            # Check convergence
            if has_converged(current_responses, new_responses):
                break
            
            current_responses = new_responses
        
        return select_final_response(current_responses)
    
    def filter_unreliable(self, agent, responses):
        # Use agent's own response as anchor
        anchor = current_responses[agent]
        filtered = []
        
        for resp in responses:
            if similarity(anchor, resp) > THRESHOLD:
                filtered.append(resp)
        
        return filtered

sac = SelfAnchoredConsensus(["agent_a", "agent_b", "agent_c"])

def sac_hook(tool_name, tool_input):
    initial = get_initial_responses(tool_name, tool_input)
    consensus = sac.sac_protocol(initial)
    return consensus
```

**Cost/complexity tradeoff:**
- **Cost:** High (multi-agent communication, multiple rounds)
- **Complexity:** High (graph topology, convergence detection)
- **Best for:** Multi-agent systems, adversarial environments, distributed deployments

---

## 13. OpenTelemetry-Based Quality Instrumentation

**How it works:**
Every LLM call, tool call, argument, and result is instrumented as an OpenTelemetry span using GenAI semantic conventions. A separate grading agent reads traces back from the observability backend (SigNoz, Jaeger), grades the execution (groundedness, accuracy, safety), and writes scores back as metrics. Quality becomes a first-class signal that can be graphed, alerted on, and gated in CI.

**Why it's effective:**
- No custom UI — uses existing observability tools
- Quality is measurable and actionable
- Enables blocking deploys on quality degradation

**Implementation approach for Python hook system:**
```python
# Wrap all hooks with OpenTelemetry
from opentelemetry import trace
from opentelemetry.semconv.ai import GenAIAttributes

tracer = trace.get_tracer(__name__)

def instrumented_hook(hook_func):
    @wraps(hook_func)
    def wrapper(*args, **kwargs):
        with tracer.start_as_current_span(hook_func.__name__) as span:
            # Set GenAI attributes
            span.set_attribute(GenAIAttributes.OPERATION_NAME, hook_func.__name__)
            span.set_attribute("agent.tool.name", kwargs.get("tool_name", ""))
            
            result = hook_func(*args, **kwargs)
            
            # Record result
            span.set_attribute("agent.result.status", result.get("status", "unknown"))
            
            return result
    return wrapper

# Quality grading hook (runs after execution)
def quality_grading_hook(trace_id):
    trace = fetch_trace_from_otel(trace_id)
    
    # Grade execution
    grades = {
        "groundedness": grade_groundedness(trace),
        "accuracy": grade_accuracy(trace),
        "safety": grade_safety(trace)
    }
    
    # Write back as metrics
    for metric, value in grades.items():
        emit_otel_metric(f"agent.quality.{metric}", value)
    
    # Fail build if below threshold
    if grades["groundedness"] < 0.8:
        raise QualityGateException("Groundedness below threshold")
```

**Cost/complexity tradeoff:**
- **Cost:** Low (OTel instrumentation, periodic grading)
- **Complexity:** Low (standard OTel integration)
- **Best for:** Production monitoring, CI/CD gates, observability stacks

---

## 14. Runtime Data-Quality Gating (SARC-DQ)

**How it works:**
Metadata-borne defects (stale prices, superseded records) are detected via a metadata-aware pre-action gate. The gate checks freshness, lineage, and provenance before allowing agent action. Uses downstream-only remediation — if the gate blocks, the agent cannot proceed. A model-free oracle derived from task decision geometry tracks defect rates.

**Why it's effective:**
- Catches defects that never enter agent context
- Recovers 100% loss on covered signals
- Capability does not buy skepticism — flat across 15× model tiers

**Implementation approach for Python hook system:**
```python
# PreToolUse hook for data quality gating
class DataQualityGate:
    def __init__(self, quality_predicates):
        self.quality_predicates = quality_predicates
        self.oracle = load_oracle("decision_geometry.pkl")
    
    def check_data_quality(self, tool_input):
        # Check each predicate
        for predicate in self.quality_predicates:
            if not predicate.check(tool_input):
                log_data_quality_violation(predicate.name, tool_input)
                raise DataQualityBlockedException(predicate.name)
        
        # Oracle check
        defect_probability = self.oracle.predict_defect(tool_input)
        if defect_probability > 0.3:
            escalate_for_review(tool_input, defect_probability)
            return False
        
        return True

dq_gate = DataQualityGate([
    FreshnessPredicate(max_age_hours=24),
    LineagePredicate(required_sources=["trusted_db"]),
    ProvenancePredicate(allowed_origins=["api_v1"])
])

def data_quality_hook(tool_name, tool_input):
    if not dq_gate.check_data_quality(tool_input):
        raise DataQualityBlockedException("Data quality check failed")
```

**Cost/complexity tradeoff:**
- **Cost:** Low (predicate checks, oracle inference)
- **Complexity:** Medium (predicate definition, oracle training)
- **Best for:** Data-intensive agents, regulated industries, financial systems

---

## 15. Real-Time Execution Telemetry Dashboard

**How it works:**
WebSocket-based dashboard shows live execution view: active agents with heartbeat, queue depth per agent, error rate (1-min sliding window), cost per run (token usage × model price). Structured JSON traces capture run_id, status, per-agent latency, tokens, and outcomes. Alert rules trigger actions (circuit breaker, pagerduty) based on conditions.

**Why it's effective:**
- Proactive alerts vs reactive grep
- Per-agent metrics vs aggregate "it works"
- Structured traces vs raw text logs

**Implementation approach for Python hook system:**
```python
# All hooks emit telemetry
class TelemetryEmitter:
    def __init__(self):
        self.websocket = WebSocketClient(TELEMETRY_URL)
        self.metrics = defaultdict(list)
    
    def emit_execution_event(self, event_type, data):
        event = {
            "timestamp": time.time(),
            "event_type": event_type,
            "data": data
        }
        self.websocket.send(json.dumps(event))
    
    def update_metrics(self, agent_name, latency_ms, tokens, status):
        self.metrics[agent_name].append({
            "latency_ms": latency_ms,
            "tokens": tokens,
            "status": status,
            "timestamp": time.time()
        })
        
        # Compute rolling error rate
        recent = [m for m in self.metrics[agent_name] if time.time() - m["timestamp"] < 60]
        error_rate = sum(1 for m in recent if m["status"] == "error") / len(recent) if recent else 0
        
        self.emit_execution_event("agent_metrics", {
            "agent": agent_name,
            "error_rate": error_rate,
            "latency_ms": latency_ms,
            "tokens": tokens
        })

telemetry = TelemetryEmitter()

def telemetry_hook(tool_name, tool_input, tool_output, latency_ms, tokens):
    telemetry.emit_execution_event("tool_call", {
        "tool": tool_name,
        "status": "success" if tool_output else "error",
        "latency_ms": latency_ms,
        "tokens": tokens
    })
    
    telemetry.update_metrics("current_agent", latency_ms, tokens, "success")
```

**Cost/complexity tradeoff:**
- **Cost:** Low (WebSocket, minimal storage)
- **Complexity:** Low (event emission, dashboard UI)
- **Best for:** Production monitoring, operations teams, real-time debugging

---

## Implementation Priority Matrix

| Mechanism | Impact | Complexity | Cost | Priority |
|-----------|--------|------------|------|----------|
| Deterministic Schema Validation | High | Low | Low | **P0** |
| OpenTelemetry Instrumentation | High | Low | Low | **P0** |
| Runtime Policy Enforcement | High | High | Low | **P1** |
| Behavioral Drift Detection | High | Medium | Low | **P1** |
| SPC Control Charts | Medium | Low | Low | **P1** |
| Self-Healing Loop | High | Medium | Medium | **P2** |
| Multi-Model Adversarial Review | High | Medium | High | **P2** |
| Persona-Based Reviewers | Medium | Low | Medium | **P2** |
| Plan-Execute Separation | High | Medium | Low | **P2** |
| Coverage Matrix | Medium | Low | Low | **P2** |
| Consensus Engine | Medium | Medium | High | **P3** |
| Checkpointed Backtracking | Medium | High | Medium | **P3** |
| Data-Quality Gating | Medium | Medium | Low | **P3** |
| SAC Byzantine Consensus | Low | High | High | **P4** |
| Real-Time Dashboard | Medium | Low | Low | **P4** |

---

## Recommended Starting Implementation

For an existing Python hook-based system, start with:

1. **Week 1-2:** Add deterministic schema validation and OpenTelemetry instrumentation to all hooks
2. **Week 3-4:** Implement SPC control charts for key quality metrics
3. **Week 5-6:** Add behavioral drift detection with 3-4 key dimensions
4. **Week 7-8:** Implement self-healing loop for common failure classes
5. **Week 9-12:** Add adversarial review for high-stakes operations

This progression builds foundational observability first, then adds intelligence, then advanced enforcement — minimizing risk while maximizing value.
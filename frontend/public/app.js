// UPI Settlement Console - talks to the backend through nginx at /api/.
const $ = (id) => document.getElementById(id);
const rupees = (v) => "₹" + Number(v).toLocaleString("en-IN", { minimumFractionDigits: 2, maximumFractionDigits: 2 });

async function api(path, options = {}) {
  const res = await fetch("/api" + path, {
    headers: { "Content-Type": "application/json", ...(options.headers || {}) },
    ...options,
  });
  const body = await res.json().catch(() => ({}));
  if (!res.ok) throw new Error(body.error || `HTTP ${res.status}`);
  return body;
}

function text(el, value) {
  el.textContent = value;
  return el;
}

function setMsg(el, message, ok) {
  el.textContent = message;
  el.className = "msg " + (ok ? "ok" : "err");
}

async function refreshHealth() {
  const pill = $("health");
  try {
    const h = await api("/health");
    pill.textContent = "SETTLEMENT_CORE=" + h.settlement_core;
    pill.className = "pill " + (h.settlement_core === "ACTIVE" ? "pill-ok" : "pill-bad");
  } catch (e) {
    pill.textContent = "Backend unreachable";
    pill.className = "pill pill-bad";
  }
}

async function refreshStats() {
  const s = await api("/stats");
  $("s-total").textContent = s.total_payments;
  $("s-pending").textContent = s.pending_count;
  $("s-pending-amt").textContent = rupees(s.pending_amount);
  $("s-settled").textContent = s.settled_count;
  $("s-settled-amt").textContent = rupees(s.settled_amount);
  $("s-batches").textContent = s.batch_count;
}

async function refreshTxns() {
  const status = $("filter").value;
  const rows = await api("/payments" + (status ? "?status=" + status : ""));
  const tbody = $("txns");
  tbody.replaceChildren();
  if (!rows.length) {
    const tr = tbody.insertRow();
    const td = text(tr.insertCell(), "No payments yet");
    td.colSpan = 7;
    td.className = "empty";
    return;
  }
  for (const p of rows) {
    const tr = tbody.insertRow();
    text(tr.insertCell(), "").append(text(document.createElement("code"), p.txn_id));
    text(tr.insertCell(), p.payer_vpa);
    text(tr.insertCell(), p.payee_vpa);
    text(tr.insertCell(), rupees(p.amount)).className = "num";
    text(tr.insertCell(), p.status).className = "status status-" + p.status;
    text(tr.insertCell(), p.batch_id || "—");
    text(tr.insertCell(), p.created_at.replace("T", " ").replace("+00:00", ""));
  }
}

async function refreshBatches() {
  const batches = await api("/settlements");
  const box = $("batches");
  box.replaceChildren();
  for (const b of batches.slice(0, 5)) {
    const div = document.createElement("div");
    div.className = "batch";
    const head = document.createElement("strong");
    head.textContent = `${b.batch_id} · ${b.payment_count} payments · ${rupees(b.gross_amount)}`;
    const ul = document.createElement("ul");
    for (const [bank, v] of Object.entries(b.per_bank)) {
      text(ul.appendChild(document.createElement("li")), `@${bank}: ${v.count} → ${rupees(v.amount)}`);
    }
    div.append(head, ul);
    box.append(div);
  }
}

async function refreshAll() {
  await refreshHealth();
  try {
    await Promise.all([refreshStats(), refreshTxns(), refreshBatches()]);
  } catch (e) {
    console.error(e);
  }
}

$("pay-form").addEventListener("submit", async (event) => {
  event.preventDefault();
  const form = event.target;
  const data = Object.fromEntries(new FormData(form));
  const button = form.querySelector("button[type=submit]");
  button.disabled = true;
  try {
    const p = await api("/payments", {
      method: "POST",
      body: JSON.stringify(data),
      headers: { "Idempotency-Key": crypto.randomUUID ? crypto.randomUUID() : String(Date.now()) },
    });
    setMsg($("pay-msg"), `Accepted ${p.txn_id} for ${rupees(p.amount)} (PENDING)`, true);
    form.reset();
  } catch (e) {
    setMsg($("pay-msg"), e.message, false);
  } finally {
    button.disabled = false;
    refreshAll();
  }
});

$("seed").addEventListener("click", async () => {
  const samples = [
    ["asha@okaxis", "freshmart@ybl", "1249.00", "Groceries"],
    ["rahul@oksbi", "cityelectric@okhdfcbank", "2310.50", "Electricity bill"],
    ["meera@ybl", "chaiwala@paytm", "40.00", "Tea"],
    ["dev@okicici", "freshmart@ybl", "318.75", "Vegetables"],
    ["neha@okaxis", "metrorail@oksbi", "60.00", "Metro card top-up"],
  ];
  try {
    for (const [payer_vpa, payee_vpa, amount, note] of samples) {
      await api("/payments", { method: "POST", body: JSON.stringify({ payer_vpa, payee_vpa, amount, note }) });
    }
    setMsg($("pay-msg"), "Added 5 sample payments", true);
  } catch (e) {
    setMsg($("pay-msg"), e.message, false);
  }
  refreshAll();
});

$("settle").addEventListener("click", async () => {
  const button = $("settle");
  button.disabled = true;
  try {
    const r = await api("/settlements/run", { method: "POST" });
    setMsg($("settle-msg"), r.batch_id ? `${r.batch_id} settled ${r.payment_count} payments, ${rupees(r.gross_amount)}` : r.message, true);
  } catch (e) {
    setMsg($("settle-msg"), e.message, false);
  } finally {
    button.disabled = false;
    refreshAll();
  }
});

$("filter").addEventListener("change", refreshTxns);

refreshAll();
setInterval(refreshAll, 5000);

import { useState } from "react";

const green = "#22c55e";
const darkGreen = "#16a34a";
const lightGreen = "#dcfce7";
const bg = "#0a0f0a";
const card = "#111811";
const border = "#1e2e1e";
const textPrimary = "#f0fdf0";
const textSecondary = "#86efac";
const textMuted = "#4ade80";

const styles = {
  app: {
    background: bg,
    minHeight: "100vh",
    fontFamily: "'DM Sans', sans-serif",
    color: textPrimary,
    padding: "0",
  },
  header: {
    padding: "48px 48px 0",
    borderBottom: `1px solid ${border}`,
    paddingBottom: "24px",
  },
  badge: {
    display: "inline-block",
    background: "#052e16",
    border: `1px solid ${darkGreen}`,
    color: textMuted,
    padding: "4px 12px",
    borderRadius: "999px",
    fontSize: "11px",
    letterSpacing: "2px",
    textTransform: "uppercase",
    marginBottom: "12px",
  },
  title: {
    fontSize: "36px",
    fontWeight: "800",
    color: textPrimary,
    margin: "0 0 4px",
    letterSpacing: "-1px",
  },
  subtitle: {
    color: textSecondary,
    fontSize: "15px",
    margin: 0,
  },
  nav: {
    display: "flex",
    gap: "8px",
    padding: "20px 48px",
    borderBottom: `1px solid ${border}`,
    overflowX: "auto",
  },
  navBtn: (active) => ({
    padding: "8px 20px",
    borderRadius: "8px",
    border: `1px solid ${active ? green : border}`,
    background: active ? "#052e16" : "transparent",
    color: active ? green : textSecondary,
    fontSize: "13px",
    fontWeight: "600",
    cursor: "pointer",
    whiteSpace: "nowrap",
    transition: "all 0.2s",
  }),
  content: {
    padding: "40px 48px",
  },
  diagramTitle: {
    fontSize: "22px",
    fontWeight: "700",
    marginBottom: "6px",
    color: textPrimary,
  },
  diagramSubtitle: {
    color: textSecondary,
    fontSize: "14px",
    marginBottom: "36px",
  },
};

// ─── DIAGRAM 1: System Overview ───────────────────────────────────────────────
function OverviewDiagram() {
  const layers = [
    {
      label: "INPUT LAYER",
      color: "#1e3a1e",
      accent: green,
      items: [
        { icon: "📱", text: "WhatsApp" },
        { icon: "💬", text: "SMS" },
        { icon: "🎙️", text: "Voice Call" },
        { icon: "🌐", text: "Web App" },
      ],
    },
    {
      label: "AGENT LAYER",
      color: "#1a3320",
      accent: "#4ade80",
      items: [
        { icon: "🤖", text: "Kisan Agent" },
        { icon: "🧠", text: "LLM Brain" },
        { icon: "💾", text: "Farmer Memory" },
        { icon: "🔀", text: "Intent Router" },
      ],
    },
    {
      label: "INTELLIGENCE LAYER",
      color: "#163316",
      accent: "#86efac",
      items: [
        { icon: "🔬", text: "YOLOv8 ONNX" },
        { icon: "🌦️", text: "Weather AI" },
        { icon: "📍", text: "Outbreak Radar" },
        { icon: "💰", text: "Price Predictor" },
      ],
    },
    {
      label: "DATA LAYER",
      color: "#0f2b0f",
      accent: "#a3e635",
      items: [
        { icon: "🗃️", text: "PlantVillage" },
        { icon: "📡", text: "Open-Meteo API" },
        { icon: "📊", text: "Agmarknet API" },
        { icon: "🗺️", text: "Geo Database" },
      ],
    },
  ];

  return (
    <div>
      <div style={{ display: "flex", flexDirection: "column", gap: "4px" }}>
        {layers.map((layer, li) => (
          <div key={li}>
            <div
              style={{
                display: "flex",
                alignItems: "center",
                gap: "16px",
                padding: "20px 24px",
                background: layer.color,
                border: `1px solid ${layer.accent}22`,
                borderRadius: li === 0 ? "12px 12px 0 0" : li === layers.length - 1 ? "0 0 12px 12px" : "0",
              }}
            >
              <div
                style={{
                  width: "160px",
                  flexShrink: 0,
                  fontSize: "10px",
                  fontWeight: "700",
                  letterSpacing: "1.5px",
                  color: layer.accent,
                }}
              >
                {layer.label}
              </div>
              <div style={{ display: "flex", gap: "12px", flexWrap: "wrap", flex: 1 }}>
                {layer.items.map((item, ii) => (
                  <div
                    key={ii}
                    style={{
                      display: "flex",
                      alignItems: "center",
                      gap: "8px",
                      background: "#ffffff08",
                      border: `1px solid ${layer.accent}33`,
                      borderRadius: "8px",
                      padding: "8px 16px",
                      fontSize: "13px",
                      color: textPrimary,
                      fontWeight: "500",
                    }}
                  >
                    <span>{item.icon}</span>
                    <span>{item.text}</span>
                  </div>
                ))}
              </div>
            </div>
            {li < layers.length - 1 && (
              <div style={{ display: "flex", justifyContent: "center", padding: "2px 0", background: "#0d180d" }}>
                <div style={{ color: green, fontSize: "18px" }}>↕</div>
              </div>
            )}
          </div>
        ))}
      </div>

      {/* Output row */}
      <div style={{ marginTop: "32px" }}>
        <div style={{ fontSize: "10px", fontWeight: "700", letterSpacing: "1.5px", color: textMuted, marginBottom: "12px" }}>
          OUTPUT TO FARMER
        </div>
        <div style={{ display: "flex", gap: "12px", flexWrap: "wrap" }}>
          {[
            { icon: "🩺", text: "Disease Diagnosis" },
            { icon: "💊", text: "Treatment Plan" },
            { icon: "⚠️", text: "Outbreak Alert" },
            { icon: "📄", text: "Insurance PDF" },
            { icon: "📈", text: "Price Forecast" },
            { icon: "🌤️", text: "Weather Briefing" },
          ].map((o, i) => (
            <div
              key={i}
              style={{
                display: "flex",
                alignItems: "center",
                gap: "8px",
                background: "#052e16",
                border: `1px solid ${green}44`,
                borderRadius: "8px",
                padding: "10px 18px",
                fontSize: "13px",
                fontWeight: "500",
              }}
            >
              <span>{o.icon}</span>
              <span style={{ color: textSecondary }}>{o.text}</span>
            </div>
          ))}
        </div>
      </div>
    </div>
  );
}

// ─── DIAGRAM 2: Kisan Agent Flow ──────────────────────────────────────────────
function AgentDiagram() {
  const steps = [
    { step: "01", title: "Farmer Sends Message", desc: "Photo / Text / Voice via WhatsApp", icon: "📲", color: "#1e3a1e" },
    { step: "02", title: "WhatsApp Webhook", desc: "Twilio receives & forwards to backend", icon: "🔗", color: "#1a3320" },
    { step: "03", title: "Intent Classifier", desc: "Is this a photo? Question? Follow-up?", icon: "🔀", color: "#163316" },
    { step: "04", title: "Kisan Agent Brain", desc: "LangChain agent selects the right tools", icon: "🤖", color: "#123012" },
    { step: "05", title: "Tool Execution", desc: "YOLOv8 / Weather / Price / Outbreak APIs", icon: "⚙️", color: "#0f2b0f" },
    { step: "06", title: "LLM Response Generator", desc: "Formats response in farmer's language", icon: "✍️", color: "#0d260d" },
    { step: "07", title: "Reply Sent", desc: "Text + image + voice back to WhatsApp", icon: "✅", color: "#0b220b" },
  ];

  return (
    <div style={{ display: "flex", gap: "32px" }}>
      {/* Main flow */}
      <div style={{ flex: 1 }}>
        {steps.map((s, i) => (
          <div key={i} style={{ display: "flex", alignItems: "flex-start", gap: "16px", marginBottom: "4px" }}>
            <div style={{ display: "flex", flexDirection: "column", alignItems: "center" }}>
              <div
                style={{
                  width: "44px",
                  height: "44px",
                  borderRadius: "12px",
                  background: s.color,
                  border: `1px solid ${green}44`,
                  display: "flex",
                  alignItems: "center",
                  justifyContent: "center",
                  fontSize: "20px",
                  flexShrink: 0,
                }}
              >
                {s.icon}
              </div>
              {i < steps.length - 1 && (
                <div style={{ width: "1px", height: "20px", background: `${green}44`, margin: "2px 0" }} />
              )}
            </div>
            <div style={{ paddingTop: "8px", paddingBottom: "16px" }}>
              <div style={{ display: "flex", alignItems: "center", gap: "10px", marginBottom: "2px" }}>
                <span style={{ fontSize: "10px", color: textMuted, fontWeight: "700", letterSpacing: "1px" }}>
                  STEP {s.step}
                </span>
              </div>
              <div style={{ fontSize: "15px", fontWeight: "700", color: textPrimary, marginBottom: "2px" }}>{s.title}</div>
              <div style={{ fontSize: "13px", color: textSecondary }}>{s.desc}</div>
            </div>
          </div>
        ))}
      </div>

      {/* Side: Agent tools */}
      <div style={{ width: "240px", flexShrink: 0 }}>
        <div
          style={{
            background: "#0d1f0d",
            border: `1px solid ${border}`,
            borderRadius: "12px",
            padding: "20px",
            position: "sticky",
            top: "20px",
          }}
        >
          <div style={{ fontSize: "10px", fontWeight: "700", letterSpacing: "1.5px", color: textMuted, marginBottom: "16px" }}>
            AGENT TOOLS
          </div>
          {[
            { icon: "🔬", name: "diagnose_crop", desc: "YOLOv8 ONNX" },
            { icon: "🌦️", name: "get_weather", desc: "Open-Meteo" },
            { icon: "💰", name: "get_price", desc: "Agmarknet" },
            { icon: "📍", name: "check_outbreaks", desc: "Geo Cluster" },
            { icon: "📢", name: "send_alert", desc: "Broadcaster" },
            { icon: "📄", name: "generate_pdf", desc: "Insurance" },
            { icon: "🏛️", name: "find_schemes", desc: "Gov Matcher" },
          ].map((t, i) => (
            <div
              key={i}
              style={{
                padding: "10px 12px",
                borderRadius: "8px",
                background: "#ffffff04",
                border: `1px solid ${border}`,
                marginBottom: "6px",
              }}
            >
              <div style={{ fontSize: "12px", fontWeight: "600", color: textPrimary, marginBottom: "1px" }}>
                {t.icon} {t.name}
              </div>
              <div style={{ fontSize: "11px", color: textMuted }}>{t.desc}</div>
            </div>
          ))}
        </div>
      </div>
    </div>
  );
}

// ─── DIAGRAM 3: ML Pipeline ───────────────────────────────────────────────────
function MLDiagram() {
  const phases = [
    {
      phase: "PHASE 1",
      title: "Data Collection",
      color: "#1e3a1e",
      items: ["PlantVillage — 54k images", "PlantDoc — real-world noise", "Rice Disease Dataset", "IP102 Pest — 75k images", "Wheat Disease Dataset"],
    },
    {
      phase: "PHASE 2",
      title: "Preprocessing",
      color: "#1a3320",
      items: ["Resize → 640×640", "Augmentation (flip, rotate, blur)", "Normalize pixel values", "YAML label config", "Train / Val / Test split"],
    },
    {
      phase: "PHASE 3",
      title: "Training (GPU)",
      color: "#163316",
      items: ["YOLOv8-large architecture", "100 epochs, batch=32", "Early stopping (patience=20)", "Target: 85%+ mAP50", "Saved as best.pt"],
    },
    {
      phase: "PHASE 4",
      title: "Export",
      color: "#123012",
      items: ["Convert .pt → .onnx", "Simplify + optimize", "Size: ~45MB", "CPU-ready (no GPU)", "Test inference speed"],
    },
    {
      phase: "PHASE 5",
      title: "Deployment",
      color: "#0f2b0f",
      items: ["FastAPI model server", "ONNX Runtime inference", "~200ms per image", "REST endpoint /diagnose", "Returns JSON results"],
    },
  ];

  return (
    <div>
      <div style={{ display: "flex", gap: "4px", overflowX: "auto", paddingBottom: "8px" }}>
        {phases.map((p, i) => (
          <div key={i} style={{ display: "flex", alignItems: "stretch", gap: "4px", flex: 1, minWidth: "160px" }}>
            <div
              style={{
                flex: 1,
                background: p.color,
                border: `1px solid ${green}33`,
                borderRadius: "12px",
                padding: "20px 16px",
              }}
            >
              <div style={{ fontSize: "9px", fontWeight: "700", letterSpacing: "1.5px", color: textMuted, marginBottom: "6px" }}>
                {p.phase}
              </div>
              <div style={{ fontSize: "14px", fontWeight: "700", color: textPrimary, marginBottom: "14px" }}>{p.title}</div>
              {p.items.map((item, ii) => (
                <div
                  key={ii}
                  style={{
                    fontSize: "12px",
                    color: textSecondary,
                    padding: "5px 0",
                    borderBottom: `1px solid ${border}`,
                    display: "flex",
                    alignItems: "center",
                    gap: "6px",
                  }}
                >
                  <span style={{ color: green, fontSize: "8px" }}>▶</span>
                  {item}
                </div>
              ))}
            </div>
            {i < phases.length - 1 && (
              <div style={{ display: "flex", alignItems: "center", color: green, fontSize: "20px", flexShrink: 0 }}>→</div>
            )}
          </div>
        ))}
      </div>

      {/* Accuracy bar */}
      <div
        style={{
          marginTop: "24px",
          background: "#0d1f0d",
          border: `1px solid ${border}`,
          borderRadius: "12px",
          padding: "20px 24px",
          display: "flex",
          gap: "32px",
          alignItems: "center",
          flexWrap: "wrap",
        }}
      >
        <div style={{ fontSize: "10px", fontWeight: "700", letterSpacing: "1.5px", color: textMuted }}>MODEL BENCHMARKS</div>
        {[
          { label: ".pt (Train)", val: 95, note: "GPU only" },
          { label: ".onnx (Deploy)", val: 94, note: "CPU ready" },
          { label: "Inference", val: null, note: "~200ms" },
          { label: "Model Size", val: null, note: "~45MB" },
        ].map((m, i) => (
          <div key={i}>
            <div style={{ fontSize: "12px", color: textSecondary, marginBottom: "4px" }}>{m.label}</div>
            {m.val ? (
              <div style={{ display: "flex", alignItems: "center", gap: "8px" }}>
                <div style={{ width: "80px", height: "6px", background: "#1a2e1a", borderRadius: "3px", overflow: "hidden" }}>
                  <div style={{ width: `${m.val}%`, height: "100%", background: green, borderRadius: "3px" }} />
                </div>
                <span style={{ fontSize: "14px", fontWeight: "700", color: green }}>{m.val}%</span>
              </div>
            ) : (
              <div style={{ fontSize: "16px", fontWeight: "700", color: green }}>{m.note}</div>
            )}
          </div>
        ))}
      </div>
    </div>
  );
}

// ─── DIAGRAM 4: Tech Stack ────────────────────────────────────────────────────
function TechDiagram() {
  const stack = [
    {
      layer: "Frontend",
      icon: "🖥️",
      color: "#1e3a1e",
      techs: [
        { name: "React", role: "Web dashboard" },
        { name: "Leaflet.js", role: "Outbreak heatmap" },
        { name: "Tailwind CSS", role: "Styling" },
        { name: "WebRTC", role: "Live camera feed" },
      ],
    },
    {
      layer: "Agent & Backend",
      icon: "⚙️",
      color: "#1a3320",
      techs: [
        { name: "LangChain", role: "Agent orchestration" },
        { name: "FastAPI", role: "REST API server" },
        { name: "Twilio", role: "WhatsApp integration" },
        { name: "Claude / GPT-4", role: "LLM responses" },
      ],
    },
    {
      layer: "AI / ML",
      icon: "🧠",
      color: "#163316",
      techs: [
        { name: "YOLOv8", role: "Disease detection" },
        { name: "ONNX Runtime", role: "CPU inference" },
        { name: "IndicTrans2", role: "12 Indian languages" },
        { name: "Prophet (Meta)", role: "Price prediction" },
      ],
    },
    {
      layer: "External APIs",
      icon: "📡",
      color: "#123012",
      techs: [
        { name: "Open-Meteo", role: "Weather data (free)" },
        { name: "Agmarknet", role: "Mandi prices (free)" },
        { name: "Google STT", role: "Voice processing" },
        { name: "Ngrok", role: "Hackathon tunneling" },
      ],
    },
    {
      layer: "Database",
      icon: "🗄️",
      color: "#0f2b0f",
      techs: [
        { name: "PostgreSQL", role: "Farmer profiles" },
        { name: "Redis", role: "Real-time cache" },
        { name: "PostGIS", role: "Geo outbreak data" },
        { name: "Firebase", role: "Alt: quick setup" },
      ],
    },
  ];

  return (
    <div style={{ display: "grid", gridTemplateColumns: "repeat(auto-fill, minmax(220px, 1fr))", gap: "12px" }}>
      {stack.map((s, i) => (
        <div
          key={i}
          style={{
            background: s.color,
            border: `1px solid ${green}22`,
            borderRadius: "12px",
            padding: "20px",
          }}
        >
          <div style={{ fontSize: "24px", marginBottom: "8px" }}>{s.icon}</div>
          <div style={{ fontSize: "10px", fontWeight: "700", letterSpacing: "1.5px", color: textMuted, marginBottom: "4px" }}>
            LAYER
          </div>
          <div style={{ fontSize: "16px", fontWeight: "700", color: textPrimary, marginBottom: "16px" }}>{s.layer}</div>
          {s.techs.map((t, ti) => (
            <div
              key={ti}
              style={{
                display: "flex",
                justifyContent: "space-between",
                alignItems: "center",
                padding: "7px 0",
                borderBottom: `1px solid ${border}`,
              }}
            >
              <span style={{ fontSize: "13px", fontWeight: "600", color: textPrimary }}>{t.name}</span>
              <span style={{ fontSize: "11px", color: textMuted }}>{t.role}</span>
            </div>
          ))}
        </div>
      ))}
    </div>
  );
}

// ─── DIAGRAM 5: Team Structure ────────────────────────────────────────────────
function TeamDiagram() {
  const members = [
    {
      role: "ML Engineer",
      icon: "🔬",
      color: "#1e3a1e",
      day1: ["Download PlantVillage dataset", "Set up YOLOv8 training pipeline", "Begin GPU training"],
      day2: ["Validate model accuracy", "Export to ONNX format", "Build FastAPI /diagnose endpoint"],
      day3: ["Fine-tune on Indian crops", "Test inference speed", "Optimize for demo"],
    },
    {
      role: "Backend + Agent",
      icon: "🤖",
      color: "#1a3320",
      day1: ["Set up Twilio WhatsApp sandbox", "Build LangChain agent skeleton", "Connect Weather API"],
      day2: ["Implement all agent tools", "Geo outbreak clustering", "Farmer memory system"],
      day3: ["Follow-up scheduler", "Govt scheme matcher", "WhatsApp voice support"],
    },
    {
      role: "Frontend Dev",
      icon: "🖥️",
      color: "#163316",
      day1: ["React project setup", "Farmer dashboard UI", "Camera upload component"],
      day2: ["Leaflet outbreak heatmap", "Real-time updates", "Mobile-responsive layout"],
      day3: ["Admin analytics panel", "Live video scanning UI", "Demo polish + animations"],
    },
    {
      role: "NLP + Data",
      icon: "🌐",
      color: "#123012",
      day1: ["Set up IndicTrans2", "Multilingual test cases", "Agmarknet API integration"],
      day2: ["Price prediction model (Prophet)", "Voice message pipeline", "Insurance PDF generator"],
      day3: ["12-language testing", "Demo script rehearsal", "Pitch deck support"],
    },
  ];

  return (
    <div>
      <div style={{ display: "grid", gridTemplateColumns: "repeat(2, 1fr)", gap: "12px" }}>
        {members.map((m, i) => (
          <div
            key={i}
            style={{
              background: m.color,
              border: `1px solid ${green}22`,
              borderRadius: "12px",
              padding: "20px",
            }}
          >
            <div style={{ display: "flex", alignItems: "center", gap: "12px", marginBottom: "16px" }}>
              <div
                style={{
                  width: "44px",
                  height: "44px",
                  borderRadius: "10px",
                  background: "#ffffff08",
                  border: `1px solid ${green}33`,
                  display: "flex",
                  alignItems: "center",
                  justifyContent: "center",
                  fontSize: "22px",
                }}
              >
                {m.icon}
              </div>
              <div>
                <div style={{ fontSize: "10px", fontWeight: "700", letterSpacing: "1.5px", color: textMuted }}>PERSON {i + 1}</div>
                <div style={{ fontSize: "16px", fontWeight: "700", color: textPrimary }}>{m.role}</div>
              </div>
            </div>
            {[
              { label: "Day 1", tasks: m.day1, col: green },
              { label: "Day 2", tasks: m.day2, col: "#4ade80" },
              { label: "Day 3", tasks: m.day3, col: "#86efac" },
            ].map((d, di) => (
              <div key={di} style={{ marginBottom: "10px" }}>
                <div style={{ fontSize: "10px", fontWeight: "700", color: d.col, letterSpacing: "1px", marginBottom: "4px" }}>
                  {d.label}
                </div>
                {d.tasks.map((t, ti) => (
                  <div key={ti} style={{ fontSize: "12px", color: textSecondary, padding: "2px 0", display: "flex", gap: "6px" }}>
                    <span style={{ color: d.col, fontSize: "8px", marginTop: "4px" }}>◆</span>
                    {t}
                  </div>
                ))}
              </div>
            ))}
          </div>
        ))}
      </div>
    </div>
  );
}

export default function CropDocDiagrams() {
  const [active, setActive] = useState("overview");

  const tabs = [
    { id: "overview", label: "System Overview", Component: OverviewDiagram },
    { id: "agent", label: "Kisan Agent Flow", Component: AgentDiagram },
    { id: "ml", label: "ML Pipeline", Component: MLDiagram },
    { id: "tech", label: "Tech Stack", Component: TechDiagram },
    { id: "team", label: "Team Structure", Component: TeamDiagram },
  ];

  const current = tabs.find((t) => t.id === active);

  return (
    <div style={styles.app}>
      <link
        href="https://fonts.googleapis.com/css2?family=DM+Sans:wght@400;500;600;700;800&display=swap"
        rel="stylesheet"
      />
      <div style={styles.header}>
        <div style={styles.badge}>🌾 CROPDOC — PROJECT DIAGRAMS</div>
        <h1 style={styles.title}>Technical Architecture</h1>
        <p style={styles.subtitle}>Complete implementation blueprint for CropDoc + Kisan Agent</p>
      </div>

      <nav style={styles.nav}>
        {tabs.map((t) => (
          <button key={t.id} style={styles.navBtn(active === t.id)} onClick={() => setActive(t.id)}>
            {t.label}
          </button>
        ))}
      </nav>

      <div style={styles.content}>
        <div style={styles.diagramTitle}>{current.label}</div>
        <div style={styles.diagramSubtitle}>
          {active === "overview" && "End-to-end system layers from farmer input to actionable output"}
          {active === "agent" && "Step-by-step flow of how Kisan Agent processes farmer messages"}
          {active === "ml" && "From raw dataset to deployed ONNX model on hackathon laptop"}
          {active === "tech" && "Every library, API, and tool used to build CropDoc"}
          {active === "team" && "3-day task breakdown for all 4 team members"}
        </div>
        <current.Component />
      </div>
    </div>
  );
}
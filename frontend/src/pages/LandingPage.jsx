/**
 * LandingPage.jsx — BharatVantage v1.1
 *
 * Updated messaging based on new metric system:
 * - Hero: "Know where every ₹100 goes"
 * - Features: True order margin, Payout Bridge, 3-state penalties, CA Export
 * - User journey: upload → 3-layer dashboard → profit decisions
 */

import React, { useEffect, useRef, useState } from "react";
import { Link } from "react-router-dom";

function useReveal() {
  const ref = useRef(null);
  const [visible, setVisible] = useState(false);
  useEffect(() => {
    const obs = new IntersectionObserver(
      ([e]) => { if (e.isIntersecting) { setVisible(true); obs.disconnect(); } },
      { threshold: 0.1 }
    );
    if (ref.current) obs.observe(ref.current);
    return () => obs.disconnect();
  }, []);
  return [ref, visible];
}

function Reveal({ children, delay = 0, className = "" }) {
  const [ref, visible] = useReveal();
  return (
    <div ref={ref} className={className} style={{
      opacity: visible ? 1 : 0,
      transform: visible ? "translateY(0)" : "translateY(28px)",
      transition: `opacity 0.65s ease ${delay}ms, transform 0.65s ease ${delay}ms`,
    }}>
      {children}
    </div>
  );
}

// ── Features (v1.1 messaging) ─────────────────────────────────────────────
const FEATURES = [
  {
    icon: "₹",
    title: "True Order Margin",
    desc: "See exactly what you pocket from every Swiggy and Zomato order — after commission, GST on commission, ad spend, and packaging. Per platform. Not a blended guess.",
    tag: "Online",
  },
  {
    icon: "⬇",
    title: "Payout Bridge",
    desc: "A waterfall that shows exactly where your gross revenue disappears — including the 18% GST on commission most owners don't know they owe.",
    tag: "Online",
  },
  {
    icon: "✓",
    title: "Recoverable Penalties",
    desc: "Penalties split into three buckets: recoverable (dispute now), non-recoverable (kitchen issue), and review required. Never dispute the wrong ones.",
    tag: "Online",
  },
  {
    icon: "⚡",
    title: "Prime Cost Speedometer",
    desc: "Food cost + staff cost as a percentage of your earnings. Alert fires at 60%. Critical alert at 65% — the danger zone where most restaurants start losing money.",
    tag: "All types",
  },
  {
    icon: "₹₹",
    title: "Cash Reconciliation",
    desc: "Compare what Petpooja recorded as cash sales against your physical drawer count. Daily gap alerts flag pilferage before it compounds.",
    tag: "Dine-in",
  },
  {
    icon: "📄",
    title: "CA Export Report",
    desc: "A structured GST reconciliation PDF — output GST, reverse charge on commissions, packaging ITC, and reconciliation gap — ready for your CA to file GSTR-1 and GSTR-3B.",
    tag: "All types",
  },
];

const PLATFORMS = ["Swiggy", "Zomato", "Petpooja", "Tally", "ONDC"];

const METRICS = [
  { value: "< 2 min", label: "Upload to first insight" },
  { value: "₹47",     label: "Average dine-in keeps per ₹100" },
  { value: "₹24",     label: "Average online keeps per ₹100" },
  { value: "3-state", label: "Penalty classification model" },
];

// ── Journey steps ──────────────────────────────────────────────────────────
const JOURNEY = [
  { step: "01", label: "Upload your data",        desc: "Swiggy CSV · Zomato CSV · Petpooja POS · Tally purchase data" },
  { step: "02", label: "Ingestion runs async",     desc: "ARQ worker processes files in the background. Ready in 60–90 seconds." },
  { step: "03", label: "Layer 1: Whole business",  desc: "Total earnings · Prime cost % · Staff cost · Kitchen conflict days" },
  { step: "04", label: "Layer 2: Channel split",   desc: "For every ₹100 earned: dine-in keeps ₹47. Online keeps ₹24." },
  { step: "05", label: "Layer 3: Deep dive",       desc: "Cash gaps · Payout bridge · True margins · Recoverable penalties" },
  { step: "06", label: "Take action",              desc: "Generate dispute list · Download CA report · Flag shifts" },
];

// ── Nav ────────────────────────────────────────────────────────────────────
function Nav() {
  const [scrolled, setScrolled] = useState(false);
  useEffect(() => {
    const fn = () => setScrolled(window.scrollY > 40);
    window.addEventListener("scroll", fn);
    return () => window.removeEventListener("scroll", fn);
  }, []);
  return (
    <nav style={{
      position: "fixed", top: 0, left: 0, right: 0, zIndex: 100,
      padding: "0 2rem", height: 64,
      display: "flex", alignItems: "center", justifyContent: "space-between",
      background: scrolled ? "rgba(15,14,13,0.94)" : "transparent",
      backdropFilter: scrolled ? "blur(16px)" : "none",
      borderBottom: scrolled ? "1px solid rgba(255,255,255,0.07)" : "none",
      transition: "all 0.25s",
    }}>
      <div style={{ display: "flex", alignItems: "center", gap: 10 }}>
        <div style={{ width: 30, height: 30, borderRadius: 8, background: "#C0580A",
          display: "flex", alignItems: "center", justifyContent: "center",
          color: "#fff", fontWeight: 600, fontSize: 14 }}>B</div>
        <span style={{ fontFamily: "var(--font-display, sans-serif)",
          fontWeight: 700, fontSize: "1.05rem", color: "#f5f0e8", letterSpacing: "-0.02em" }}>
          BharatVantage
        </span>
      </div>
      <div style={{ display: "flex", alignItems: "center", gap: "1.5rem" }}>
        {["Features", "How it works", "Integrations"].map(label => (
          <a key={label} href={`#${label.toLowerCase().replace(/ /g, "-")}`}
            style={{ color: "#9c9584", fontSize: "0.875rem", textDecoration: "none", transition: "color 0.15s" }}
            onMouseEnter={e => e.target.style.color = "#f5f0e8"}
            onMouseLeave={e => e.target.style.color = "#9c9584"}>
            {label}
          </a>
        ))}
        <Link to="/login" style={{
          padding: "7px 18px", borderRadius: 9,
          background: "rgba(192,88,10,0.12)", border: "1px solid rgba(192,88,10,0.3)",
          color: "#C0580A", fontSize: "0.875rem", fontWeight: 600,
          textDecoration: "none", transition: "all 0.15s",
        }}
          onMouseEnter={e => { e.currentTarget.style.background = "#C0580A"; e.currentTarget.style.color = "#0f0e0d"; }}
          onMouseLeave={e => { e.currentTarget.style.background = "rgba(192,88,10,0.12)"; e.currentTarget.style.color = "#C0580A"; }}>
          Sign in
        </Link>
      </div>
    </nav>
  );
}

// ── Hero ───────────────────────────────────────────────────────────────────
function Hero() {
  return (
    <section style={{ minHeight: "100vh", display: "flex", flexDirection: "column",
      alignItems: "center", justifyContent: "center",
      padding: "8rem 2rem 4rem", textAlign: "center", position: "relative", overflow: "hidden" }}>
      <div style={{ position: "absolute", top: "25%", left: "50%", transform: "translateX(-50%)",
        width: 600, height: 500, borderRadius: "50%",
        background: "radial-gradient(circle, rgba(192,88,10,0.10) 0%, transparent 70%)",
        pointerEvents: "none" }} />
      <div style={{ position: "absolute", inset: 0, pointerEvents: "none",
        backgroundImage: "linear-gradient(rgba(255,255,255,0.025) 1px, transparent 1px), linear-gradient(90deg, rgba(255,255,255,0.025) 1px, transparent 1px)",
        backgroundSize: "48px 48px" }} />

      {/* Badge */}
      <div style={{ display: "inline-flex", alignItems: "center", gap: 7,
        padding: "5px 14px", borderRadius: 100,
        background: "rgba(192,88,10,0.08)", border: "1px solid rgba(192,88,10,0.2)",
        marginBottom: "1.5rem", animation: "fadeUp 0.5s ease both" }}>
        <span style={{ width: 6, height: 6, borderRadius: "50%", background: "#C0580A", display: "inline-block" }} />
        <span style={{ color: "#C0580A", fontSize: 11, fontWeight: 700, letterSpacing: "0.1em" }}>
          PROFIT INTELLIGENCE FOR INDIAN RESTAURANTS
        </span>
      </div>

      {/* Headline — the core v1.1 promise */}
      <h1 style={{
        fontFamily: "var(--font-display, sans-serif)",
        fontSize: "clamp(2.6rem, 6vw, 4.8rem)",
        fontWeight: 800, color: "#f5f0e8", lineHeight: 1.08,
        letterSpacing: "-0.03em", maxWidth: 820, margin: "0 0 1.5rem",
        animation: "fadeUp 0.5s ease 0.1s both",
      }}>
        Know where every<br />
        <span style={{ background: "linear-gradient(90deg, #C0580A, #fbbf24)",
          WebkitBackgroundClip: "text", WebkitTextFillColor: "transparent" }}>
          ₹100 goes.
        </span>
      </h1>

      <p style={{
        color: "#9c9584", fontSize: "clamp(1rem, 2vw, 1.15rem)",
        maxWidth: 540, lineHeight: 1.75, margin: "0 auto 2.5rem",
        animation: "fadeUp 0.5s ease 0.2s both",
      }}>
        Upload your Swiggy, Zomato, Petpooja, and Tally files.
        BharatVantage shows you your true order margin, payout bridge,
        recoverable penalties, and CA-ready GST report — in under 2 minutes.
      </p>

      <div style={{ display: "flex", gap: "1rem", justifyContent: "center", flexWrap: "wrap",
        animation: "fadeUp 0.5s ease 0.3s both" }}>
        <Link to="/register" style={{
          padding: "14px 32px", borderRadius: 12,
          background: "linear-gradient(135deg, #C0580A, #a04500)",
          color: "#0f0e0d", fontWeight: 700, fontSize: "1rem",
          textDecoration: "none", boxShadow: "0 0 32px rgba(192,88,10,0.35)",
          transition: "transform 0.15s",
        }}
          onMouseEnter={e => e.currentTarget.style.transform = "translateY(-2px)"}
          onMouseLeave={e => e.currentTarget.style.transform = "translateY(0)"}>
          Start free →
        </Link>
        <Link to="/login" style={{
          padding: "14px 32px", borderRadius: 12,
          background: "rgba(255,255,255,0.06)", border: "1px solid rgba(255,255,255,0.1)",
          color: "#f5f0e8", fontWeight: 600, fontSize: "1rem",
          textDecoration: "none",
        }}>Sign in</Link>
      </div>

      {/* Metric strip */}
      <div style={{ display: "flex", gap: "3rem", flexWrap: "wrap", justifyContent: "center",
        marginTop: "4rem", animation: "fadeUp 0.5s ease 0.4s both" }}>
        {METRICS.map(m => (
          <div key={m.label} style={{ textAlign: "center" }}>
            <div style={{ fontWeight: 800, fontSize: "1.75rem", color: "#C0580A",
              fontFamily: "var(--font-display, sans-serif)" }}>{m.value}</div>
            <div style={{ color: "#6b6659", fontSize: "0.8rem", marginTop: 4 }}>{m.label}</div>
          </div>
        ))}
      </div>

      <style>{`
        @keyframes fadeUp {
          from { opacity:0; transform:translateY(22px); }
          to   { opacity:1; transform:translateY(0); }
        }
      `}</style>
    </section>
  );
}

// ── Platforms strip ────────────────────────────────────────────────────────
function Platforms() {
  return (
    <section id="integrations" style={{ padding: "3rem 2rem",
      borderTop: "1px solid rgba(255,255,255,0.06)" }}>
      <Reveal>
        <p style={{ textAlign: "center", color: "#6b6659", fontSize: "0.8rem",
          letterSpacing: "0.1em", fontWeight: 600, marginBottom: "1.25rem",
          textTransform: "uppercase" }}>
          Works with your existing tools
        </p>
        <div style={{ display: "flex", gap: "0.75rem", justifyContent: "center", flexWrap: "wrap" }}>
          {PLATFORMS.map(p => (
            <div key={p} style={{
              padding: "9px 22px", borderRadius: 100,
              background: "rgba(255,255,255,0.04)", border: "1px solid rgba(255,255,255,0.08)",
              color: "#9c9584", fontSize: "0.875rem", fontWeight: 600,
            }}>{p}</div>
          ))}
        </div>
      </Reveal>
    </section>
  );
}

// ── Features grid ──────────────────────────────────────────────────────────
function Features() {
  return (
    <section id="features" style={{ padding: "5rem 2rem", maxWidth: 1100, margin: "0 auto" }}>
      <Reveal>
        <div style={{ textAlign: "center", marginBottom: "3.5rem" }}>
          <p style={{ color: "#C0580A", fontSize: "0.8rem", fontWeight: 700,
            letterSpacing: "0.1em", textTransform: "uppercase", marginBottom: 10 }}>
            What we give you
          </p>
          <h2 style={{ fontFamily: "var(--font-display, sans-serif)",
            fontSize: "clamp(1.8rem, 4vw, 3rem)", fontWeight: 800, color: "#f5f0e8",
            letterSpacing: "-0.03em", margin: 0 }}>
            Profit intelligence your CA will recognise
          </h2>
          <p style={{ color: "#6b6659", marginTop: 14, fontSize: "1rem" }}>
            Built for Indian platforms, Indian tax law, and Indian restaurant owners.
          </p>
        </div>
      </Reveal>
      <div style={{ display: "grid", gridTemplateColumns: "repeat(auto-fill, minmax(300px, 1fr))", gap: "1.25rem" }}>
        {FEATURES.map((f, i) => (
          <Reveal key={f.title} delay={i * 70}>
            <div style={{
              padding: "1.75rem", background: "rgba(255,255,255,0.03)",
              border: "1px solid rgba(255,255,255,0.07)", borderRadius: 16,
              transition: "border-color 0.15s, transform 0.15s", cursor: "default",
            }}
              onMouseEnter={e => { e.currentTarget.style.borderColor = "rgba(192,88,10,0.3)"; e.currentTarget.style.transform = "translateY(-3px)"; }}
              onMouseLeave={e => { e.currentTarget.style.borderColor = "rgba(255,255,255,0.07)"; e.currentTarget.style.transform = "translateY(0)"; }}>
              <div style={{ display: "flex", alignItems: "center", gap: 8, marginBottom: "0.75rem" }}>
                <span style={{ fontSize: "1.5rem" }}>{f.icon}</span>
                <span style={{ fontSize: "0.7rem", fontWeight: 700, padding: "2px 8px",
                  borderRadius: 100, background: "rgba(192,88,10,0.1)", color: "#C0580A",
                  border: "1px solid rgba(192,88,10,0.2)" }}>{f.tag}</span>
              </div>
              <h3 style={{ fontFamily: "var(--font-display, sans-serif)", fontWeight: 700,
                fontSize: "1.05rem", color: "#f5f0e8", margin: "0 0 0.6rem" }}>{f.title}</h3>
              <p style={{ color: "#6b6659", fontSize: "0.875rem", lineHeight: 1.65, margin: 0 }}>
                {f.desc}
              </p>
            </div>
          </Reveal>
        ))}
      </div>
    </section>
  );
}

// ── User Journey ───────────────────────────────────────────────────────────
function Journey() {
  return (
    <section id="how-it-works" style={{
      padding: "5rem 2rem",
      borderTop: "1px solid rgba(255,255,255,0.06)",
      borderBottom: "1px solid rgba(255,255,255,0.06)",
    }}>
      <div style={{ maxWidth: 900, margin: "0 auto" }}>
        <Reveal>
          <p style={{ color: "#C0580A", fontSize: "0.8rem", fontWeight: 700,
            letterSpacing: "0.1em", textTransform: "uppercase", marginBottom: 10, textAlign: "center" }}>
            How it works
          </p>
          <h2 style={{ fontFamily: "var(--font-display, sans-serif)",
            fontSize: "clamp(1.8rem, 3.5vw, 2.6rem)", fontWeight: 800, color: "#f5f0e8",
            letterSpacing: "-0.03em", textAlign: "center", margin: "0 0 3rem" }}>
            From raw CSVs to profit clarity in 6 steps
          </h2>
        </Reveal>
        <div style={{ display: "flex", flexDirection: "column", gap: "0" }}>
          {JOURNEY.map((j, i) => (
            <Reveal key={j.step} delay={i * 80}>
              <div style={{
                display: "flex", gap: "1.25rem", alignItems: "flex-start",
                padding: "1.25rem 0",
                borderBottom: i < JOURNEY.length - 1 ? "1px solid rgba(255,255,255,0.06)" : "none",
              }}>
                <div style={{
                  width: 36, height: 36, borderRadius: "50%", flexShrink: 0,
                  background: i < 2 ? "rgba(192,88,10,0.12)" : "rgba(255,255,255,0.05)",
                  border: `1px solid ${i < 2 ? "rgba(192,88,10,0.3)" : "rgba(255,255,255,0.08)"}`,
                  display: "flex", alignItems: "center", justifyContent: "center",
                  fontSize: "0.7rem", fontWeight: 700,
                  color: i < 2 ? "#C0580A" : "#6b6659",
                }}>{j.step}</div>
                <div>
                  <div style={{ fontWeight: 600, color: "#f5f0e8", marginBottom: 3, fontSize: "0.95rem" }}>
                    {j.label}
                  </div>
                  <div style={{ color: "#6b6659", fontSize: "0.85rem", lineHeight: 1.6 }}>
                    {j.desc}
                  </div>
                </div>
              </div>
            </Reveal>
          ))}
        </div>
      </div>
    </section>
  );
}

// ── CTA ────────────────────────────────────────────────────────────────────
function CTA() {
  return (
    <section style={{ padding: "7rem 2rem", textAlign: "center", position: "relative", overflow: "hidden" }}>
      <div style={{ position: "absolute", top: "50%", left: "50%",
        transform: "translate(-50%,-50%)", width: 500, height: 280, borderRadius: "50%",
        background: "radial-gradient(ellipse, rgba(192,88,10,0.10), transparent 70%)", pointerEvents: "none" }} />
      <Reveal>
        <h2 style={{ fontFamily: "var(--font-display, sans-serif)",
          fontSize: "clamp(1.8rem, 4.5vw, 3.2rem)", fontWeight: 800, color: "#f5f0e8",
          letterSpacing: "-0.03em", margin: "0 0 1.25rem" }}>
          Stop guessing. Start knowing.
        </h2>
        <p style={{ color: "#6b6659", fontSize: "1rem", marginBottom: "2.5rem" }}>
          Upload your first CSV and see your true margins in under 2 minutes.
        </p>
        <Link to="/register" style={{
          display: "inline-block", padding: "15px 40px", borderRadius: 13,
          background: "linear-gradient(135deg, #C0580A, #a04500)",
          color: "#0f0e0d", fontWeight: 700, fontSize: "1rem",
          textDecoration: "none", boxShadow: "0 0 44px rgba(192,88,10,0.35)",
          transition: "transform 0.15s",
        }}
          onMouseEnter={e => e.currentTarget.style.transform = "scale(1.03)"}
          onMouseLeave={e => e.currentTarget.style.transform = "scale(1)"}>
          Get started free →
        </Link>
      </Reveal>
    </section>
  );
}

// ── Footer ─────────────────────────────────────────────────────────────────
function Footer() {
  return (
    <footer style={{
      padding: "2rem 2rem",
      borderTop: "1px solid rgba(255,255,255,0.06)",
      display: "flex", justifyContent: "space-between", alignItems: "center",
      flexWrap: "wrap", gap: "1rem",
    }}>
      <div style={{ display: "flex", alignItems: "center", gap: 9 }}>
        <div style={{ width: 26, height: 26, borderRadius: 6, background: "#C0580A",
          display: "flex", alignItems: "center", justifyContent: "center",
          color: "#fff", fontWeight: 600, fontSize: 13 }}>B</div>
        <span style={{ fontWeight: 700, color: "#9c9584", fontSize: "0.875rem" }}>BharatVantage</span>
      </div>
      <p style={{ color: "#6b6659", fontSize: "0.8rem" }}>
        © 2026 BharatVantage · Vantage for Indian restaurants
      </p>
      <div style={{ display: "flex", gap: "1.25rem" }}>
        {["Privacy", "Terms", "Contact"].map(l => (
          <a key={l} href="#" style={{ color: "#6b6659", fontSize: "0.8rem", textDecoration: "none" }}>{l}</a>
        ))}
      </div>
    </footer>
  );
}

// ── Page ───────────────────────────────────────────────────────────────────
export default function LandingPage() {
  return (
    <div style={{ background: "#0f0e0d", minHeight: "100vh", color: "#f5f0e8" }}>
      <Nav />
      <Hero />
      <Platforms />
      <Features />
      <Journey />
      <CTA />
      <Footer />
    </div>
  );
}

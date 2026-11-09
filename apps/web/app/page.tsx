const features = [
  { number: "01", title: "Build your material library", description: "Organize tile products, finishes, dimensions, and repeatable material maps." },
  { number: "02", title: "Analyze a real space", description: "Start with a room photo. Identify the target surface and refine its boundary." },
  { number: "03", title: "Visualize with control", description: "Apply materials with perspective-aware placement, scale, rotation, and grout settings." },
];

export default function Home() {
  return (
    <main>
      <nav className="nav">
        <a className="brand" href="#"><span className="brand-mark">S</span> SURFACE<span className="muted">ANALYZER</span></a>
        <span className="nav-note">EARLY ACCESS · TILE VISUALIZATION PLATFORM</span>
      </nav>
      <section className="hero">
        <div className="eyebrow"><span className="pulse" /> THE SURFACE VISUALIZATION WORKSPACE</div>
        <h1>See the surface.<br /><em>Before it exists.</em></h1>
        <p className="intro">A new way to explore tile materials in real spaces. From a room photograph to a considered material preview, with precision and creative control.</p>
        <div className="actions">
          <a className="primary" href="#workflow">Explore the workflow <span>↗</span></a>
          <a className="secondary" href="http://localhost:8000/docs">Developer API ↗</a>
        </div>
        <div className="preview">
          <div className="preview-top"><span>WORKSPACE / PREVIEW</span><span>01 — MATERIAL STUDY</span></div>
          <div className="room">
            <div className="room-window" />
            <div className="room-wall"><div className="wall-art" /></div>
            <div className="room-floor"><div className="tile-grid" /></div>
            <div className="room-caption"><span>01</span><span>Perspective-aware material preview</span></div>
          </div>
          <div className="preview-bottom"><span>GEOMETRY-LED RENDERING</span><span>AI-ASSISTED SURFACE ANALYSIS</span><span>DESIGNED FOR TILE</span></div>
        </div>
      </section>
      <section className="workflow" id="workflow">
        <div className="section-heading"><span>THE WORKFLOW</span><span>FROM PHOTO TO POSSIBILITY</span></div>
        <div className="feature-grid">
          {features.map((feature) => <article className="feature" key={feature.number}>
            <span className="feature-number">{feature.number}</span>
            <h2>{feature.title}</h2><p>{feature.description}</p>
          </article>)}
        </div>
      </section>
      <footer><span>© 2026 SURFACE ANALYZER</span><span>BUILT FOR MATERIAL THINKERS.</span></footer>
    </main>
  );
}

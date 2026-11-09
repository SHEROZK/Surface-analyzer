"use client";

import { useCallback, useEffect, useRef, useState } from "react";

const API = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";
type Product = { id: string; name: string; sku?: string; width_mm?: number; height_mm?: number; finish?: string; material_url?: string | null };
type Project = { id: string; name: string; status: string; room_image_url?: string | null };
type Asset = { id: string; type: string; url: string };
type ProjectDetail = { id: string; name: string; status: string; assets: Asset[] };

export default function Workspace() {
  const [products, setProducts] = useState<Product[]>([]);
  const [projects, setProjects] = useState<Project[]>([]);
  const [selectedProject, setSelectedProject] = useState<ProjectDetail | null>(null);
  const [selectedProduct, setSelectedProduct] = useState("");
  const [projectName, setProjectName] = useState("");
  const [productName, setProductName] = useState("");
  const [sku, setSku] = useState("");
  const [width, setWidth] = useState("600");
  const [height, setHeight] = useState("600");
  const [finish, setFinish] = useState("Matt");
  const [busy, setBusy] = useState(false);
  const [message, setMessage] = useState("");
  const [points, setPoints] = useState<{x:number;y:number}[]>([]);
  const [scale, setScale] = useState(0.45);
  const [opacity, setOpacity] = useState(0.88);
  const canvasRef = useRef<HTMLCanvasElement>(null);
  const roomImageRef = useRef<HTMLImageElement | null>(null);
  const textureImageRef = useRef<HTMLImageElement | null>(null);

  const refresh = useCallback(async () => {
    try {
      const [p, r] = await Promise.all([fetch(API + "/api/v1/products"), fetch(API + "/api/v1/projects")]);
      if (!p.ok || !r.ok) throw new Error("API unavailable");
      const productData: Product[] = await p.json();
      setProducts(productData);
      setProjects(await r.json());
      setSelectedProduct(current => current || productData[0]?.id || "");
    } catch {
      setMessage("Could not connect to the API. Start the Docker Compose stack and refresh.");
    }
  }, []);

  const loadProject = useCallback(async (id: string) => {
    const response = await fetch(API + "/api/v1/projects/" + id);
    if (!response.ok) return;
    const detail: ProjectDetail = await response.json();
    const room = detail.assets.find(asset => asset.type === "room");
    setSelectedProject({ ...detail, room_image_url: room?.url || null } as ProjectDetail & {room_image_url?: string});
    setPoints([]);
  }, []);

  useEffect(() => { void refresh(); }, [refresh]);

  const activeProduct = products.find(product => product.id === selectedProduct) || null;
  const roomUrl = (selectedProject as (ProjectDetail & {room_image_url?: string}) | null)?.room_image_url || null;

  const redraw = useCallback(() => {
    const canvas = canvasRef.current;
    const room = roomImageRef.current;
    if (!canvas || !room || !room.complete) return;
    const ctx = canvas.getContext("2d");
    if (!ctx) return;
    canvas.width = room.naturalWidth;
    canvas.height = room.naturalHeight;
    ctx.drawImage(room, 0, 0);
    if (points.length >= 3) {
      ctx.save();
      ctx.beginPath();
      points.forEach((point, index) => index === 0 ? ctx.moveTo(point.x * canvas.width, point.y * canvas.height) : ctx.lineTo(point.x * canvas.width, point.y * canvas.height));
      ctx.closePath();
      ctx.clip();
      const texture = textureImageRef.current;
      if (texture?.complete && texture.naturalWidth) {
        const pattern = ctx.createPattern(texture, "repeat");
        if (pattern) {
          const tileWidth = Math.max(24, canvas.width * scale / 2.5);
          const tileHeight = tileWidth * (texture.naturalHeight / texture.naturalWidth);
          ctx.globalAlpha = opacity;
          ctx.translate(0, 0);
          ctx.scale(tileWidth / texture.naturalWidth, tileHeight / texture.naturalHeight);
          const scaledPattern = ctx.createPattern(texture, "repeat");
          if (scaledPattern) {
            ctx.setTransform(tileWidth / texture.naturalWidth, 0, 0, tileHeight / texture.naturalHeight, 0, 0);
            ctx.fillStyle = scaledPattern;
            ctx.fillRect(0, 0, canvas.width * texture.naturalWidth / tileWidth, canvas.height * texture.naturalHeight / tileHeight);
          }
        }
      } else {
        ctx.fillStyle = "rgba(165,176,139,.58)";
        ctx.fill();
      }
      ctx.restore();
      ctx.save();
      ctx.beginPath();
      points.forEach((point, index) => index === 0 ? ctx.moveTo(point.x * canvas.width, point.y * canvas.height) : ctx.lineTo(point.x * canvas.width, point.y * canvas.height));
      ctx.closePath();
      ctx.strokeStyle = "#d9e3c4";
      ctx.lineWidth = Math.max(2, canvas.width / 500);
      ctx.stroke();
      ctx.restore();
    }
    points.forEach(point => {
      ctx.beginPath();
      ctx.arc(point.x * canvas.width, point.y * canvas.height, Math.max(4, canvas.width / 180), 0, Math.PI * 2);
      ctx.fillStyle = "#d9e3c4";
      ctx.fill();
    });
  }, [points, scale, opacity]);

  useEffect(() => { redraw(); }, [redraw, roomUrl, selectedProduct]);

  function loadRoom(url: string) {
    const image = new Image();
    image.onload = () => { roomImageRef.current = image; redraw(); };
    image.src = API + url;
  }
  function loadTexture(url?: string | null) {
    textureImageRef.current = null;
    if (!url) { redraw(); return; }
    const image = new Image();
    image.onload = () => { textureImageRef.current = image; redraw(); };
    image.src = API + url;
  }
  useEffect(() => { if (roomUrl) loadRoom(roomUrl); else { roomImageRef.current = null; redraw(); } }, [roomUrl]);
  useEffect(() => { loadTexture(activeProduct?.material_url); }, [activeProduct?.material_url]);

  async function createProject(event: React.FormEvent) {
    event.preventDefault(); setBusy(true); setMessage("");
    try {
      const data = new FormData(); data.set("name", projectName);
      const response = await fetch(API + "/api/v1/projects", { method: "POST", body: data });
      const result = await response.json();
      if (!response.ok) throw new Error(result.detail || "Could not create project");
      setProjectName(""); await refresh(); await loadProject(result.id); setMessage("Project created.");
    } catch (error) { setMessage(error instanceof Error ? error.message : "Project creation failed."); }
    finally { setBusy(false); }
  }

  async function createProduct(event: React.FormEvent<HTMLFormElement>) {
    event.preventDefault(); setBusy(true); setMessage("");
    const formElement = event.currentTarget;
    try {
      const form = new FormData(formElement);
      const response = await fetch(API + "/api/v1/products", { method: "POST", body: form });
      const result = await response.json();
      if (!response.ok) throw new Error(result.detail || "Could not save tile");
      formElement.reset(); await refresh(); setSelectedProduct(result.id); setMessage("Tile added to your material library.");
    } catch (error) { setMessage(error instanceof Error ? error.message : "Tile creation failed."); }
    finally { setBusy(false); }
  }

  async function uploadRoom(file?: File) {
    if (!file || !selectedProject) return;
    setBusy(true); setMessage("");
    try {
      const data = new FormData(); data.set("image", file);
      const response = await fetch(API + "/api/v1/projects/" + selectedProject.id + "/room-image", { method: "POST", body: data });
      const result = await response.json();
      if (!response.ok) throw new Error(result.detail || "Upload failed");
      await loadProject(selectedProject.id); setMessage("Room photo uploaded. Select the surface by clicking around its edges.");
    } catch (error) { setMessage(error instanceof Error ? error.message : "Upload failed."); }
    finally { setBusy(false); }
  }

  function addPoint(event: React.MouseEvent<HTMLCanvasElement>) {
    if (!roomImageRef.current) return;
    const rect = event.currentTarget.getBoundingClientRect();
    setPoints(current => [...current, { x: (event.clientX - rect.left) / rect.width, y: (event.clientY - rect.top) / rect.height }]);
  }

  return <main className="app-shell">
    <header className="app-nav"><a className="brand" href="/"><span className="brand-mark">S</span> SURFACE<span className="muted">ANALYZER</span></a><span className="workspace-tag">WORKSPACE / TILE STUDIO</span><span className="status-dot">LOCAL MVP</span></header>
    <section className="workspace-head"><div><div className="eyebrow">YOUR MATERIAL WORKSPACE</div><h1>Make the room<br/><em>your canvas.</em></h1><p>Build a tile library, upload a room, outline a surface and preview a material in place.</p></div><div className="head-count"><strong>{projects.length.toString().padStart(2,"0")}</strong><span>PROJECTS</span><strong>{products.length.toString().padStart(2,"0")}</strong><span>MATERIALS</span></div></section>
    {message && <div className="notice" role="status">{message}</div>}
    <div className="studio-grid">
      <aside className="studio-sidebar">
        <section className="panel"><div className="panel-title"><span>01 / PROJECTS</span><span>{projects.length} TOTAL</span></div>
          <form className="inline-form" onSubmit={createProject}><input value={projectName} onChange={e=>setProjectName(e.target.value)} placeholder="New project name" required/><button disabled={busy}>＋</button></form>
          <div className="project-list">{projects.map(project=><button key={project.id} className={"project-item "+(selectedProject?.id===project.id?"active":"")} onClick={()=>void loadProject(project.id)}><span className="project-icon">◫</span><span>{project.name}<small>{project.status}</small></span><span>↗</span></button>)}{projects.length===0&&<p className="empty-note">Your projects will appear here.</p>}</div>
        </section>
        <section className="panel"><div className="panel-title"><span>02 / TILE LIBRARY</span><span>{products.length} MATERIALS</span></div>
          <div className="product-list">{products.map(product=><button key={product.id} className={"product-item "+(selectedProduct===product.id?"active":"")} onClick={()=>setSelectedProduct(product.id)}><span className="swatch">{product.material_url?<img src={API+product.material_url} alt=""/>:<span>▧</span>}</span><span>{product.name}<small>{[product.width_mm&&product.height_mm?product.width_mm+" × "+product.height_mm+" mm":null,product.finish].filter(Boolean).join(" · ")||"Tile material"}</small></span></button>)}</div>
          <details className="add-material"><summary>＋ Add a tile material</summary><form onSubmit={createProduct} className="stack-form"><input name="name" placeholder="Material name" required/><input name="sku" placeholder="SKU (optional)"/><div className="two-inputs"><input name="width_mm" type="number" min="1" placeholder="Width mm"/><input name="height_mm" type="number" min="1" placeholder="Height mm"/></div><select name="finish" defaultValue="Matt"><option>Matt</option><option>Polished</option><option>Gloss</option><option>Textured</option><option>Stone</option><option>Wood effect</option></select><label className="file-label">Material texture image<input name="material" type="file" accept="image/png,image/jpeg,image/webp"/></label><button className="dark-button" disabled={busy}>Save material</button></form></details>
        </section>
      </aside>
      <section className="visualizer-panel"><div className="visualizer-top"><div><div className="panel-title">03 / PHOTO VISUALIZER</div><h2>{selectedProject?.name || "Choose a project"}</h2></div><span className="visualizer-status">{roomUrl?"ROOM LOADED":"AWAITING PHOTO"}</span></div>
        {!selectedProject ? <div className="visualizer-empty"><div className="empty-symbol">＋</div><h3>Start with a project</h3><p>Create a project on the left, then upload a room photo to begin.</p></div> :
        <><div className="canvas-wrap">{roomUrl?<canvas ref={canvasRef} onClick={addPoint} aria-label="Room photo. Click to outline the surface to visualize."/>:<div className="upload-empty"><div className="empty-symbol">↑</div><h3>Upload a room photograph</h3><p>JPG, PNG or WebP · up to 15 MB</p><label className="dark-button">Choose room photo<input type="file" accept="image/png,image/jpeg,image/webp" hidden onChange={e=>void uploadRoom(e.target.files?.[0])}/></label></div>}</div>
        {roomUrl&&<div className="visualizer-controls"><div className="control-row"><span>Surface outline</span><span>{points.length<3?"Click at least 3 points":points.length+" points selected"}</span></div><div className="control-actions"><button onClick={()=>setPoints([])}>Clear outline</button><button onClick={()=>setPoints(p=>p.slice(0,-1))}>Undo point</button><label className="file-replace">Replace photo<input type="file" accept="image/png,image/jpeg,image/webp" onChange={e=>void uploadRoom(e.target.files?.[0])}/></label></div><div className="range-row"><label>Tile scale <input type="range" min=".15" max=".9" step=".01" value={scale} onChange={e=>setScale(Number(e.target.value))}/></label><label>Opacity <input type="range" min=".2" max="1" step=".01" value={opacity} onChange={e=>setOpacity(Number(e.target.value))}/></label></div><p className="helper-text">Choose a tile with a texture image, then click around the floor or wall boundary. The outline closes automatically after three points. Use Undo point or Clear outline to refine it.</p></div>}</>}
      </section>
    </div>
    <footer className="studio-footer"><span>© 2026 SURFACE ANALYZER</span><span>PHOTO WORKFLOW MVP · CAMERA PREVIEW COMING NEXT</span></footer>
  </main>;
}

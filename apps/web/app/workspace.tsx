"use client";

import { useCallback, useEffect, useRef, useState } from "react";

const API = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";
type Product = { id: string; name: string; sku?: string; category?: string; brand?: string; collection?: string; width_mm?: number; height_mm?: number; finish?: string; material_url?: string | null; assets?: {id:string;role:string;url:string;name?:string}[] };
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
  const [detectionConfidence, setDetectionConfidence] = useState<number | null>(null);
  const [detecting, setDetecting] = useState(false);
  const [scale, setScale] = useState(0.45);
  const [opacity, setOpacity] = useState(0.88);
  const [pattern, setPattern] = useState("grid");
  const [groutWidth, setGroutWidth] = useState(0.012);
  const [groutColor, setGroutColor] = useState("#aaa69c");
  const canvasRef = useRef<HTMLCanvasElement>(null);
  const roomImageRef = useRef<HTMLImageElement | null>(null);
  const textureImageRef = useRef<HTMLImageElement | null>(null);
  const textureFacesRef = useRef<HTMLImageElement[]>([]);

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
    setDetectionConfidence(null);
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
      const primaryTexture = textureImageRef.current;
      const faces = [primaryTexture, ...textureFacesRef.current].filter((image): image is HTMLImageElement => Boolean(image?.complete && image.naturalWidth));
      if (faces.length) {
        const baseWidth = Math.max(28, canvas.width * scale / 2.5);
        const baseHeight = baseWidth * (faces[0].naturalHeight / faces[0].naturalWidth);
        const gap = Math.max(1, baseWidth * groutWidth);
        ctx.globalAlpha = opacity;
        ctx.fillStyle = groutColor;
        ctx.fillRect(0, 0, canvas.width, canvas.height);
        const drawCell = (x:number, y:number, w:number, h:number, seed:number, angle=0) => {
          const face = faces[Math.abs(seed) % faces.length];
          ctx.save();
          ctx.translate(x + w / 2, y + h / 2);
          ctx.rotate(angle);
          if (seed % 7 === 0) ctx.scale(-1, 1);
          if (seed % 11 === 0) ctx.scale(1, -1);
          ctx.drawImage(face, -w / 2 + gap / 2, -h / 2 + gap / 2, w - gap, h - gap);
          ctx.restore();
        };
        if (pattern === "herringbone") {
          const w = baseWidth * 0.5;
          const h = baseHeight;
          const stepX = w + gap;
          const stepY = h + gap;
          const rows = Math.ceil(canvas.height / stepY) + 4;
          const cols = Math.ceil(canvas.width / stepX) + 4;
          for (let row=-2; row<rows; row++) for (let col=-2; col<cols; col++) {
            const x = col * stepX * 2 + (row % 2 ? stepX : 0);
            const y = row * stepY;
            const seed = (row * 73856093) ^ (col * 19349663);
            drawCell(x, y, w, h, seed, 0);
            drawCell(x + w + gap, y + h / 2, w, h, seed + 13, Math.PI / 2);
          }
        } else {
          const diagonal = pattern === "diagonal" ? Math.PI / 4 : 0;
          const cellW = pattern === "diagonal" ? baseWidth * 1.414 : baseWidth;
          const cellH = pattern === "diagonal" ? baseHeight * 1.414 : baseHeight;
          const stepX = cellW + gap;
          const stepY = cellH + gap;
          const rows = Math.ceil(canvas.height / stepY) + 4;
          const cols = Math.ceil(canvas.width / stepX) + 4;
          for (let row=-2; row<rows; row++) for (let col=-2; col<cols; col++) {
            const offset = pattern === "brick" && row % 2 !== 0 ? stepX / 2 : 0;
            const seed = (row * 73856093) ^ (col * 19349663);
            drawCell(col * stepX + offset, row * stepY, cellW, cellH, seed, diagonal);
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
  }, [points, scale, opacity, pattern, groutWidth, groutColor]);

  useEffect(() => { redraw(); }, [redraw, roomUrl, selectedProduct]);

  function loadRoom(url: string) {
    const image = new Image();
    image.onload = () => { roomImageRef.current = image; redraw(); };
    image.src = API + url;
  }
  function loadTexture(url?: string | null, faces: string[] = []) {
    textureImageRef.current = null;
    textureFacesRef.current = [];
    if (!url) { redraw(); return; }
    const primary = new Image();
    primary.onload = () => { textureImageRef.current = primary; redraw(); };
    primary.src = API + url;
    textureFacesRef.current = faces.map(faceUrl => {
      const image = new Image();
      image.onload = () => redraw();
      image.src = API + faceUrl;
      return image;
    });
  }
  useEffect(() => { if (roomUrl) loadRoom(roomUrl); else { roomImageRef.current = null; redraw(); } }, [roomUrl]);
  useEffect(() => { loadTexture(activeProduct?.material_url, activeProduct?.assets?.filter(asset => asset.role === "texture_face").map(asset => asset.url) || []); }, [activeProduct?.id, activeProduct?.material_url]);


  async function autoDetectFloor() {
    if (!selectedProject) return;
    setDetecting(true); setMessage("");
    try {
      const response = await fetch(API + "/api/v1/projects/" + selectedProject.id + "/detect-surface?mode=floor", { method: "POST" });
      const result = await response.json();
      if (!response.ok) throw new Error(result.detail || "Could not detect the floor.");
      setPoints(result.points);
      setDetectionConfidence(result.confidence);
      setMessage("Floor outline detected. Review the proposed boundary and refine it if needed.");
    } catch (error) {
      setMessage(error instanceof Error ? error.message : "Automatic floor detection failed.");
    } finally { setDetecting(false); }
  }

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
      formElement.reset(); await refresh(); setSelectedProduct(result.id); setMessage("Product added to your material library.");
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
      await loadProject(selectedProject.id); setMessage("Room photo uploaded. Use Auto-detect floor to find the surface boundary.");
    } catch (error) { setMessage(error instanceof Error ? error.message : "Upload failed."); }
    finally { setBusy(false); }
  }

  function addPoint(event: React.MouseEvent<HTMLCanvasElement>) {
    if (!roomImageRef.current) return;
    const rect = event.currentTarget.getBoundingClientRect();
    setPoints(current => [...current, { x: (event.clientX - rect.left) / rect.width, y: (event.clientY - rect.top) / rect.height }]);
  }

  return <main className="app-shell">
    <header className="app-nav"><a className="brand" href="/"><span className="brand-mark">S</span> SURFACE<span className="muted">ANALYZER</span></a><span className="workspace-tag">WORKSPACE / SURFACE STUDIO</span><span className="status-dot">LOCAL MVP</span></header>
    <section className="workspace-head"><div><div className="eyebrow">YOUR MATERIAL WORKSPACE</div><h1>Make the room<br/><em>your canvas.</em></h1><p>Build a multi-material catalog, upload a room, outline a surface and preview finishes in place.</p></div><div className="head-count"><strong>{projects.length.toString().padStart(2,"0")}</strong><span>PROJECTS</span><strong>{products.length.toString().padStart(2,"0")}</strong><span>MATERIALS</span></div></section>
    {message && <div className="notice" role="status">{message}</div>}
    <div className="studio-grid">
      <aside className="studio-sidebar">
        <section className="panel"><div className="panel-title"><span>01 / PROJECTS</span><span>{projects.length} TOTAL</span></div>
          <form className="inline-form" onSubmit={createProject}><input value={projectName} onChange={e=>setProjectName(e.target.value)} placeholder="New project name" required/><button disabled={busy}>＋</button></form>
          <div className="project-list">{projects.map(project=><button key={project.id} className={"project-item "+(selectedProject?.id===project.id?"active":"")} onClick={()=>void loadProject(project.id)}><span className="project-icon">◫</span><span>{project.name}<small>{project.status}</small></span><span>↗</span></button>)}{projects.length===0&&<p className="empty-note">Your projects will appear here.</p>}</div>
        </section>
        <section className="panel"><div className="panel-title"><span>02 / MATERIAL LIBRARY</span><span>{products.length} PRODUCTS</span></div>
          <div className="product-list">{products.map(product=><button key={product.id} className={"product-item "+(selectedProduct===product.id?"active":"")} onClick={()=>setSelectedProduct(product.id)}><span className="swatch">{product.material_url?<img src={API+product.material_url} alt=""/>:<span>▧</span>}</span><span>{product.name}<small>{[product.category?.replaceAll("-"," "),product.brand,product.collection,product.width_mm&&product.height_mm?product.width_mm+" × "+product.height_mm+" mm":null,product.finish].filter(Boolean).join(" · ")||"Surface material"}</small></span></button>)}</div>
          <details className="add-material"><summary>＋ Add a surface product</summary><form onSubmit={createProduct} className="stack-form"><input name="name" placeholder="Material name" required/><input name="sku" placeholder="SKU / product code (optional)"/><select name="category" defaultValue="tile"><option value="tile">Tile / Porcelain</option><option value="natural-stone">Natural stone / Marble</option><option value="wood-flooring">Wood / Flooring</option><option value="wallpaper">Wallpaper</option><option value="countertop">Countertop / Slab</option><option value="paint">Paint / Coating</option><option value="panel">Wall / Decorative panel</option><option value="paver">Outdoor paver</option><option value="other">Other surface</option></select><input name="brand" placeholder="Brand / manufacturer (optional)"/><input name="collection" placeholder="Collection / range (optional)"/><div className="two-inputs"><input name="width_mm" type="number" min="1" placeholder="Width mm"/><input name="height_mm" type="number" min="1" placeholder="Height mm"/></div><select name="finish" defaultValue="Matt"><option>Matt</option><option>Polished</option><option>Gloss</option><option>Textured</option><option>Stone</option><option>Wood effect</option></select><label className="file-label">Seamless texture / main material image<input name="texture" type="file" accept="image/png,image/jpeg,image/webp"/></label><label className="file-label">Texture face variations (multiple)<input name="texture_faces" type="file" accept="image/png,image/jpeg,image/webp" multiple/></label><label className="file-label">Product gallery images (multiple)<input name="gallery" type="file" accept="image/png,image/jpeg,image/webp" multiple/></label><label className="file-label">Normal map (optional)<input name="normal_map" type="file" accept="image/png,image/jpeg,image/webp"/></label><label className="file-label">Roughness map (optional)<input name="roughness_map" type="file" accept="image/png,image/jpeg,image/webp"/></label><button className="dark-button" disabled={busy}>Save product</button></form></details>
        </section>
      </aside>
      <section className="visualizer-panel"><div className="visualizer-top"><div><div className="panel-title">03 / PHOTO VISUALIZER</div><h2>{selectedProject?.name || "Choose a project"}</h2></div><span className="visualizer-status">{roomUrl?"ROOM LOADED":"AWAITING PHOTO"}</span></div>
        {!selectedProject ? <div className="visualizer-empty"><div className="empty-symbol">＋</div><h3>Start with a project</h3><p>Create a project on the left, then upload a room photo to begin.</p></div> :
        <><div className="canvas-wrap">{roomUrl?<canvas ref={canvasRef} onClick={addPoint} aria-label="Room photo. Click to outline the surface to visualize."/>:<div className="upload-empty"><div className="empty-symbol">↑</div><h3>Upload a room photograph</h3><p>JPG, PNG or WebP · up to 15 MB</p><label className="dark-button">Choose room photo<input type="file" accept="image/png,image/jpeg,image/webp" hidden onChange={e=>void uploadRoom(e.target.files?.[0])}/></label></div>}</div>
        {roomUrl&&<div className="visualizer-controls"><div className="control-row"><span>Surface outline</span><span>{points.length<3?"Not detected":points.length+" boundary points"}{detectionConfidence!==null?" · "+Math.round(detectionConfidence*100)+"% confidence":""}</span></div><div className="control-actions"><button disabled={detecting||busy} onClick={()=>void autoDetectFloor()}>{detecting?"Detecting floor…":"✦ Auto-detect floor"}</button><button onClick={()=>{setPoints([]);setDetectionConfidence(null);}}>Clear outline</button><button onClick={()=>setPoints(p=>p.slice(0,-1))}>Undo point</button><label className="file-replace">Replace photo<input type="file" accept="image/png,image/jpeg,image/webp" onChange={e=>void uploadRoom(e.target.files?.[0])}/></label></div><div className="range-row"><label>Pattern scale <input type="range" min=".15" max=".9" step=".01" value={scale} onChange={e=>setScale(Number(e.target.value))}/></label><label>Opacity <input type="range" min=".2" max="1" step=".01" value={opacity} onChange={e=>setOpacity(Number(e.target.value))}/></label></div><div className="range-row"><label>Tile layout <select value={pattern} onChange={e=>setPattern(e.target.value)}><option value="grid">Straight / grid</option><option value="brick">Brick / offset</option><option value="diagonal">Diagonal</option><option value="herringbone">Herringbone</option></select></label><label>Grout width <input type="range" min=".004" max=".04" step=".001" value={groutWidth} onChange={e=>setGroutWidth(Number(e.target.value))}/></label></div><div className="range-row"><label>Grout colour <input type="color" value={groutColor} onChange={e=>setGroutColor(e.target.value)}/></label></div><p className="helper-text">Use Auto-detect floor to propose the visible floor boundary from the room photo. Review the result: click the image to add boundary points, use Undo point to refine it, or Clear outline to start again. Detection may need correction around rugs, furniture, reflections or unusual camera angles.</p></div>}</>}
      </section>
    </div>
    <footer className="studio-footer"><span>© 2026 SURFACE ANALYZER</span><span>PHOTO WORKFLOW MVP · MULTI-MATERIAL CATALOG</span></footer>
  </main>;
}

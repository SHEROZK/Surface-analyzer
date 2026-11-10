"use client";

import { useCallback, useEffect, useRef, useState } from "react";

const API = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";
type Product = { id: string; name: string; sku?: string; category?: string; brand?: string; collection?: string; width_mm?: number; height_mm?: number; finish?: string; material_url?: string | null; assets?: {id:string;role:string;url:string;name?:string}[] };
type Project = { id: string; name: string; status: string; room_image_url?: string | null };
type Asset = { id: string; type: string; url: string };
type ProjectDetail = { id: string; name: string; status: string; assets: Asset[] };

type Point = { x: number; y: number };
type PromptPoint = Point & { label: 0 | 1 };
type Quad = [Point, Point, Point, Point];
type Occlusion = { label: string; points: Point[]; confidence: number; area_ratio: number; bbox?: { x: number; y: number; width: number; height: number } };

function pointInPolygon(point: Point, polygon: Point[]) {
  let inside = false;
  for (let i=0,j=polygon.length-1;i<polygon.length;j=i++) {
    const a=polygon[i], b=polygon[j];
    const crosses=((a.y>point.y)!==(b.y>point.y)) && point.x < ((b.x-a.x)*(point.y-a.y))/(b.y-a.y)+a.x;
    if (crosses) inside=!inside;
  }
  return inside;
}

// Approximate the four floor-plane corners from an automatically detected or
// manually drawn polygon. The polygon remains the authoritative clipping mask.
function floorQuad(polygon: Point[]): Quad | null {
  if (polygon.length < 4) return null;
  const by = (score: (p: Point) => number) => polygon.reduce((best, p) => score(p) < score(best) ? p : best);
  const tl = by(p => p.x + p.y);
  const tr = by(p => -p.x + p.y);
  const br = by(p => -p.x - p.y);
  const bl = by(p => p.x - p.y);
  const unique = [tl, tr, br, bl].filter((p, i, all) => all.findIndex(q => q.x === p.x && q.y === p.y) === i);
  if (unique.length !== 4) return null;
  const area = Math.abs((tr.x-tl.x)*(bl.y-tl.y)-(tr.y-tl.y)*(bl.x-tl.x));
  return area > 0.0001 ? [tl, tr, br, bl] : null;
}

function affineTriangle(
  ctx: CanvasRenderingContext2D,
  image: CanvasImageSource,
  source: [Point, Point, Point],
  dest: [Point, Point, Point],
) {
  const [s0,s1,s2] = source, [d0,d1,d2] = dest;
  const den = s0.x*(s1.y-s2.y)+s1.x*(s2.y-s0.y)+s2.x*(s0.y-s1.y);
  if (Math.abs(den) < 1e-8) return;
  const a = (d0.x*(s1.y-s2.y)+d1.x*(s2.y-s0.y)+d2.x*(s0.y-s1.y))/den;
  const c = (d0.x*(s2.x-s1.x)+d1.x*(s0.x-s2.x)+d2.x*(s1.x-s0.x))/den;
  const e = (d0.x*(s1.x*s2.y-s2.x*s1.y)+d1.x*(s2.x*s0.y-s0.x*s2.y)+d2.x*(s0.x*s1.y-s1.x*s0.y))/den;
  const b = (d0.y*(s1.y-s2.y)+d1.y*(s2.y-s0.y)+d2.y*(s0.y-s1.y))/den;
  const d = (d0.y*(s2.x-s1.x)+d1.y*(s0.x-s2.x)+d2.y*(s1.x-s0.x))/den;
  const f = (d0.y*(s1.x*s2.y-s2.x*s1.y)+d1.y*(s2.x*s0.y-s0.x*s2.y)+d2.y*(s0.x*s1.y-s1.x*s0.y))/den;
  ctx.save();
  ctx.beginPath(); ctx.moveTo(d0.x,d0.y); ctx.lineTo(d1.x,d1.y); ctx.lineTo(d2.x,d2.y); ctx.closePath(); ctx.clip();
  ctx.transform(a,b,c,d,e,f);
  ctx.drawImage(image,0,0);
  ctx.restore();
}

function solveLinearSystem(matrix: number[][], values: number[]): number[] | null {
  const a = matrix.map((row, i) => [...row, values[i]]);
  const n = values.length;
  for (let col = 0; col < n; col++) {
    let pivot = col;
    for (let row = col + 1; row < n; row++) if (Math.abs(a[row][col]) > Math.abs(a[pivot][col])) pivot = row;
    if (Math.abs(a[pivot][col]) < 1e-10) return null;
    [a[col], a[pivot]] = [a[pivot], a[col]];
    const divisor = a[col][col];
    for (let j = col; j <= n; j++) a[col][j] /= divisor;
    for (let row = 0; row < n; row++) {
      if (row === col) continue;
      const factor = a[row][col];
      for (let j = col; j <= n; j++) a[row][j] -= factor * a[col][j];
    }
  }
  return a.map(row => row[n]);
}

function projectiveTransform(source: Quad, destination: Quad): number[] | null {
  const matrix: number[][] = [], values: number[] = [];
  for (let i = 0; i < 4; i++) {
    const {x, y} = source[i], u = destination[i].x, v = destination[i].y;
    matrix.push([x, y, 1, 0, 0, 0, -u*x, -u*y]); values.push(u);
    matrix.push([0, 0, 0, x, y, 1, -v*x, -v*y]); values.push(v);
  }
  return solveLinearSystem(matrix, values);
}

function mapProjective(h: number[], p: Point): Point {
  const den = h[6]*p.x + h[7]*p.y + 1;
  return {x:(h[0]*p.x+h[1]*p.y+h[2])/den, y:(h[3]*p.x+h[4]*p.y+h[5])/den};
}

// Subdivide the homography into a mesh. Each small cell is drawn as two affine
// triangles, closely approximating true projective mapping without WebGL.
function drawImageOnQuad(ctx: CanvasRenderingContext2D, image: CanvasImageSource, quad: Quad, width: number, height: number) {
  const source: Quad = [{x:0,y:0},{x:width,y:0},{x:width,y:height},{x:0,y:height}];
  const h = projectiveTransform(source, quad);
  if (!h || h.some(value => !Number.isFinite(value))) return;
  const divisions = 24;
  for (let row = 0; row < divisions; row++) for (let col = 0; col < divisions; col++) {
    const x0 = width*col/divisions, x1 = width*(col+1)/divisions;
    const y0 = height*row/divisions, y1 = height*(row+1)/divisions;
    const s00={x:x0,y:y0}, s10={x:x1,y:y0}, s11={x:x1,y:y1}, s01={x:x0,y:y1};
    const d00=mapProjective(h,s00), d10=mapProjective(h,s10), d11=mapProjective(h,s11), d01=mapProjective(h,s01);
    affineTriangle(ctx,image,[s00,s10,s11],[d00,d10,d11]);
    affineTriangle(ctx,image,[s00,s11,s01],[d00,d11,d01]);
  }
}

export default function Workspace() {
  const [authToken, setAuthToken] = useState("");
  const [authEmail, setAuthEmail] = useState("");
  const [authPassword, setAuthPassword] = useState("");
  const [authName, setAuthName] = useState("");
  const [workspaceName, setWorkspaceName] = useState("");
  const [registerMode, setRegisterMode] = useState(false);
  const [products, setProducts] = useState<Product[]>([]);
  const [projects, setProjects] = useState<Project[]>([]);
  const [selectedProject, setSelectedProject] = useState<ProjectDetail | null>(null);
  const [selectedProduct, setSelectedProduct] = useState("");
  const [surfaceProducts, setSurfaceProducts] = useState<{floor:string;wall:string}>({floor:"",wall:""});
  const [dropTarget, setDropTarget] = useState<"floor" | "wall" | null>(null);
  const [projectName, setProjectName] = useState("");
  const [productName, setProductName] = useState("");
  const [sku, setSku] = useState("");
  const [width, setWidth] = useState("600");
  const [height, setHeight] = useState("600");
  const [finish, setFinish] = useState("Matt");
  const [busy, setBusy] = useState(false);
  const [message, setMessage] = useState("");
  const [points, setPoints] = useState<{x:number;y:number}[]>([]);
  const [surfaceOutlines, setSurfaceOutlines] = useState<{floor: Point[]; wall: Point[]}>({floor: [], wall: []});
  const [surfaceOcclusions, setSurfaceOcclusions] = useState<{floor: Occlusion[]; wall: Occlusion[]}>({floor: [], wall: []});
  const [preserveOcclusions, setPreserveOcclusions] = useState(true);
  const [detectionConfidence, setDetectionConfidence] = useState<number | null>(null);
  const [detectionWarnings, setDetectionWarnings] = useState<string[]>([]);
  const [detecting, setDetecting] = useState(false);
  const [sam2PromptMode, setSam2PromptMode] = useState(false);
  const [promptLabel, setPromptLabel] = useState<0 | 1>(1);
  const [promptPoints, setPromptPoints] = useState<PromptPoint[]>([]);
  const [refiningSurface, setRefiningSurface] = useState(false);
  const [analyzingDepth, setAnalyzingDepth] = useState(false);
  const [depthMap, setDepthMap] = useState<string | null>(null);
  const [surfaceMode, setSurfaceMode] = useState<"floor" | "wall">("floor");
  const [scale, setScale] = useState(0.45);
  const [opacity, setOpacity] = useState(0.88);
  const [pattern, setPattern] = useState("grid");
  const [groutWidth, setGroutWidth] = useState(0.012);
  const [groutColor, setGroutColor] = useState("#aaa69c");
  const canvasRef = useRef<HTMLCanvasElement>(null);
  const roomImageRef = useRef<HTMLImageElement | null>(null);
  const productTexturesRef = useRef<Record<string,{primary:HTMLImageElement|null;faces:HTMLImageElement[]}>>({});
  const lastAutoDetectionRef = useRef("");

  useEffect(() => { const saved = window.sessionStorage.getItem("surface-access-token"); if (saved) setAuthToken(saved); }, []);

  const apiFetch = useCallback((url: string, init: RequestInit = {}) => fetch(url, { ...init, headers: { ...(init.headers || {}), ...(authToken ? { Authorization: "Bearer " + authToken } : {}) } }), [authToken]);

  const refresh = useCallback(async () => {
    try {
      const [p, r] = await Promise.all([apiFetch(API + "/api/v1/products"), apiFetch(API + "/api/v1/projects")]);
      if (!p.ok || !r.ok) throw new Error("API unavailable");
      const productData: Product[] = await p.json();
      setProducts(productData);
      setProjects(await r.json());
      setSelectedProduct(current => current || productData[0]?.id || "");
    } catch {
      setMessage("Could not connect to the API. Start the Docker Compose stack and refresh.");
    }
  }, [apiFetch]);

  const loadProject = useCallback(async (id: string) => {
    const response = await apiFetch(API + "/api/v1/projects/" + id);
    if (!response.ok) return;
    const detail: ProjectDetail = await response.json();
    const room = detail.assets.find(asset => asset.type === "room");
    setSelectedProject({ ...detail, room_image_url: room?.url || null } as ProjectDetail & {room_image_url?: string});
    setPoints([]);
    setSurfaceOutlines({floor: [], wall: []});
    setSurfaceOcclusions({floor: [], wall: []});
    setSurfaceProducts({floor: "", wall: ""});
    setDropTarget(null);
    setDetectionConfidence(null);
    setDetectionWarnings([]);
    setPromptPoints([]);
    setSam2PromptMode(false);
    setDepthMap(null);
  }, [apiFetch]);

  useEffect(() => { if (authToken) void refresh(); }, [refresh, authToken]);

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
    const surfaces: { mode: "floor" | "wall"; polygon: Point[] }[] = [
      { mode: "floor", polygon: surfaceOutlines.floor },
      { mode: "wall", polygon: surfaceOutlines.wall },
    ];
    for (const surface of surfaces) {
      const polygon = surface.polygon;
      const productId = surfaceProducts[surface.mode] || selectedProduct;
      const textureSet = productTexturesRef.current[productId];
      const faces = [textureSet?.primary, ...(textureSet?.faces || [])].filter((image): image is HTMLImageElement => Boolean(image?.complete && image.naturalWidth));
      if (polygon.length < 3) continue;
      ctx.save();
      ctx.beginPath();
      polygon.forEach((point, index) => index === 0 ? ctx.moveTo(point.x * canvas.width, point.y * canvas.height) : ctx.lineTo(point.x * canvas.width, point.y * canvas.height));
      ctx.closePath();
      ctx.clip();
      if (faces.length) {
        const baseWidth = Math.max(28, canvas.width * scale / 2.5);
        const baseHeight = baseWidth * (faces[0].naturalHeight / faces[0].naturalWidth);
        const gap = Math.max(1, baseWidth * groutWidth);
        ctx.globalAlpha = opacity;
        const patternCanvas = document.createElement("canvas");
        patternCanvas.width = canvas.width; patternCanvas.height = canvas.height;
        const patternCtx = patternCanvas.getContext("2d");
        if (patternCtx) {
          patternCtx.fillStyle = groutColor;
          patternCtx.fillRect(0, 0, canvas.width, canvas.height);
          const drawCell = (x:number, y:number, w:number, h:number, seed:number, angle=0) => {
            const face = faces[Math.abs(seed) % faces.length];
            patternCtx.save();
            patternCtx.translate(x + w / 2, y + h / 2);
            patternCtx.rotate(angle);
            if (seed % 7 === 0) patternCtx.scale(-1, 1);
            if (seed % 11 === 0) patternCtx.scale(1, -1);
            patternCtx.drawImage(face, -w / 2 + gap / 2, -h / 2 + gap / 2, w - gap, h - gap);
            patternCtx.restore();
          };
          if (pattern === "herringbone") {
            const w = baseWidth * 0.5, h = baseHeight;
            const stepX = w + gap, stepY = h + gap;
            const rows = Math.ceil(canvas.height / stepY) + 4;
            const cols = Math.ceil(canvas.width / stepX) + 4;
            for (let row=-2; row<rows; row++) for (let col=-2; col<cols; col++) {
              const x = col * stepX * 2 + (row % 2 ? stepX : 0), y = row * stepY;
              const seed = (row * 73856093) ^ (col * 19349663);
              drawCell(x, y, w, h, seed);
              drawCell(x + w + gap, y + h / 2, w, h, seed + 13, Math.PI / 2);
            }
          } else {
            const diagonal = pattern === "diagonal" ? Math.PI / 4 : 0;
            const cellW = pattern === "diagonal" ? baseWidth * 1.414 : baseWidth;
            const cellH = pattern === "diagonal" ? baseHeight * 1.414 : baseHeight;
            const stepX = cellW + gap, stepY = cellH + gap;
            const rows = Math.ceil(canvas.height / stepY) + 4;
            const cols = Math.ceil(canvas.width / stepX) + 4;
            for (let row=-2; row<rows; row++) for (let col=-2; col<cols; col++) {
              const offset = pattern === "brick" && row % 2 !== 0 ? stepX / 2 : 0;
              const seed = (row * 73856093) ^ (col * 19349663);
              drawCell(col * stepX + offset, row * stepY, cellW, cellH, seed, diagonal);
            }
          }
          const quad = floorQuad(polygon);
          if (quad) {
            const projected: Quad = quad.map(p => ({x:p.x*canvas.width,y:p.y*canvas.height})) as Quad;
            drawImageOnQuad(ctx, patternCanvas, projected, canvas.width, canvas.height);
          } else {
            ctx.drawImage(patternCanvas, 0, 0);
          }
        }
      } else {
        ctx.fillStyle = surface.mode === "floor" ? "rgba(165,176,139,.58)" : "rgba(120,160,190,.42)";
        ctx.fill();
      }
      ctx.restore();
      if (surface.mode === dropTarget) {
        ctx.save();
        ctx.beginPath();
        polygon.forEach((point, index) => index === 0 ? ctx.moveTo(point.x * canvas.width, point.y * canvas.height) : ctx.lineTo(point.x * canvas.width, point.y * canvas.height));
        ctx.closePath();
        ctx.fillStyle = "rgba(91, 190, 139, .20)";
        ctx.fill();
        ctx.setLineDash([Math.max(8, canvas.width / 90), Math.max(5, canvas.width / 150)]);
        ctx.strokeStyle = "#5bbe8b";
        ctx.lineWidth = Math.max(4, canvas.width / 250);
        ctx.stroke();
        ctx.restore();
      }
      if (surface.mode === surfaceMode) {
        ctx.save();
        ctx.beginPath();
        polygon.forEach((point, index) => index === 0 ? ctx.moveTo(point.x * canvas.width, point.y * canvas.height) : ctx.lineTo(point.x * canvas.width, point.y * canvas.height));
        ctx.closePath();
        ctx.strokeStyle = surface.mode === "floor" ? "#d9e3c4" : "#a8d8f0";
        ctx.lineWidth = Math.max(2, canvas.width / 500);
        ctx.stroke();
        polygon.forEach(point => {
          ctx.beginPath();
          ctx.arc(point.x * canvas.width, point.y * canvas.height, Math.max(4, canvas.width / 180), 0, Math.PI * 2);
          ctx.fillStyle = surface.mode === "floor" ? "#d9e3c4" : "#a8d8f0";
          ctx.fill();
        });
        ctx.restore();
      }
    }
    // Restore the original room pixels inside AI-detected object masks after
    // material rendering. This keeps sofas, cabinets, rugs and fixtures from
    // being painted over by the tile texture.
    if (preserveOcclusions) {
      for (const mask of [...surfaceOcclusions.floor, ...surfaceOcclusions.wall]) {
        if (mask.points.length < 3) continue;
        ctx.save();
        ctx.beginPath();
        mask.points.forEach((point, index) => index === 0
          ? ctx.moveTo(point.x * canvas.width, point.y * canvas.height)
          : ctx.lineTo(point.x * canvas.width, point.y * canvas.height));
        ctx.closePath();
        ctx.clip();
        ctx.drawImage(room, 0, 0);
        ctx.restore();
      }
    }
    for (const prompt of promptPoints) {
      ctx.beginPath();
      ctx.arc(prompt.x * canvas.width, prompt.y * canvas.height, Math.max(7, canvas.width / 130), 0, Math.PI * 2);
      ctx.fillStyle = prompt.label === 1 ? "#35c98b" : "#ed6b6b";
      ctx.fill();
      ctx.lineWidth = Math.max(2, canvas.width / 700);
      ctx.strokeStyle = "#ffffff";
      ctx.stroke();
    }
  }, [points, surfaceOutlines, surfaceMode, surfaceProducts, selectedProduct, scale, opacity, pattern, groutWidth, groutColor, dropTarget, surfaceOcclusions, preserveOcclusions, promptPoints]);

  useEffect(() => { redraw(); }, [redraw, roomUrl, selectedProduct]);

  async function fetchPrivateImage(url: string): Promise<{ image: HTMLImageElement; objectUrl: string }> {
    const response = await apiFetch(API + url);
    if (!response.ok) throw new Error("Could not load private workspace media.");
    const objectUrl = URL.createObjectURL(await response.blob());
    const image = new Image();
    await new Promise<void>((resolve, reject) => {
      image.onload = () => resolve();
      image.onerror = () => reject(new Error("Image could not be decoded."));
      image.src = objectUrl;
    });
    return { image, objectUrl };
  }

  useEffect(() => {
    let cancelled = false;
    let objectUrl = "";
    roomImageRef.current = null;
    if (!roomUrl) { redraw(); return; }
    void fetchPrivateImage(roomUrl).then(({image, objectUrl: url}) => {
      if (cancelled) { URL.revokeObjectURL(url); return; }
      objectUrl = url;
      roomImageRef.current = image;
      redraw();
    }).catch(() => setMessage("Could not load this room image. Please sign in again."));
    return () => { cancelled = true; if (objectUrl) URL.revokeObjectURL(objectUrl); };
  }, [roomUrl, apiFetch, redraw]);

  useEffect(() => {
    let cancelled = false;
    const createdUrls: string[] = [];
    productTexturesRef.current = {};
    void (async () => {
      for (const product of products) {
        const urls = [product.material_url, ...(product.assets?.filter(asset => asset.role === "texture_face").map(asset => asset.url) || [])].filter((url): url is string => Boolean(url));
        if (!urls.length) continue;
        const loaded: HTMLImageElement[] = [];
        for (const url of urls) {
          try {
            const result = await fetchPrivateImage(url);
            if (cancelled) { URL.revokeObjectURL(result.objectUrl); return; }
            createdUrls.push(result.objectUrl);
            loaded.push(result.image);
          } catch { /* Keep the rest of the catalog usable if one asset is unavailable. */ }
        }
        productTexturesRef.current[product.id] = {primary:loaded[0] || null,faces:loaded.slice(1)};
      }
      if (!cancelled) redraw();
    })();
    return () => { cancelled = true; createdUrls.forEach(URL.revokeObjectURL); productTexturesRef.current = {}; };
  }, [products, apiFetch, redraw]);


  async function autoDetectFloor() {
    if (!selectedProject) return;
    setDetecting(true); setMessage("");
    try {
      const response = await apiFetch(API + "/api/v1/projects/" + selectedProject.id + "/detect-surface?mode=" + surfaceMode, { method: "POST" });
      const result = await response.json();
      if (!response.ok) throw new Error(result.detail || "Could not detect the floor.");
      setPoints(result.points);
      setSurfaceOutlines(current => ({...current, [surfaceMode]: result.points}));
      setSurfaceOcclusions(current => ({...current, [surfaceMode]: Array.isArray(result.occlusions) ? result.occlusions : []}));
      setDetectionConfidence(result.confidence);
      setDetectionWarnings(Array.isArray(result.warnings) ? result.warnings : []);
      setMessage((surfaceMode === "floor" ? "Floor" : "Wall") + " outline detected. Review the proposed boundary and refine it if needed.");
    } catch (error) {
      setMessage(error instanceof Error ? error.message : "Automatic floor detection failed.");
    } finally { setDetecting(false); }
  }



  async function refineSurfaceWithSam2() {
    if (!selectedProject || promptPoints.length === 0) return;
    setRefiningSurface(true); setMessage("");
    try {
      const response = await apiFetch(API + "/api/v1/projects/" + selectedProject.id + "/refine-surface", {
        method: "POST", headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ points: promptPoints }),
      });
      const result = await response.json();
      if (!response.ok) throw new Error(result.detail || "SAM 2 point refinement is unavailable.");
      setPoints(result.points);
      setSurfaceOutlines(current => ({ ...current, [surfaceMode]: result.points }));
      setDetectionConfidence(result.confidence ?? null);
      setDetectionWarnings(Array.isArray(result.warnings) ? result.warnings : []);
      setSam2PromptMode(false);
      setMessage("SAM 2 created a point-guided outline locally on " + result.device + ". Review the boundary before applying material.");
    } catch (error) {
      setMessage(error instanceof Error ? error.message : "SAM 2 refinement failed.");
    } finally { setRefiningSurface(false); }
  }

  async function analyzeRoomDepth() {
    if (!selectedProject) return;
    setAnalyzingDepth(true); setMessage("");
    try {
      const response = await apiFetch(API + "/api/v1/projects/" + selectedProject.id + "/analyze-depth", { method: "POST" });
      const result = await response.json();
      if (!response.ok) throw new Error(result.detail || "Local AI depth analysis is unavailable.");
      setDepthMap(result.depth_map);
      setMessage("AI depth map generated locally (" + result.device + "). This is relative depth, not a surface boundary.");
    } catch (error) {
      setMessage(error instanceof Error ? error.message : "AI depth analysis failed.");
    } finally { setAnalyzingDepth(false); }
  }

  // Propose a floor outline automatically whenever a room image is loaded or replaced.
  // The ref prevents duplicate requests during the same project/image render cycle.
  useEffect(() => {
    if (!selectedProject || !roomUrl) return;
    const detectionKey = selectedProject.id + ":" + roomUrl;
    if (lastAutoDetectionRef.current === detectionKey) return;
    lastAutoDetectionRef.current = detectionKey;
    void autoDetectFloor();
  }, [selectedProject?.id, roomUrl]);

  async function submitAuth(event: React.FormEvent) {
    event.preventDefault(); setBusy(true); setMessage("");
    try {
      const endpoint = registerMode ? "/api/v1/auth/register" : "/api/v1/auth/login";
      const payload = registerMode ? {workspace_name:workspaceName,full_name:authName,email:authEmail,password:authPassword} : {email:authEmail,password:authPassword};
      const response = await fetch(API + endpoint, {method:"POST",headers:{"Content-Type":"application/json"},body:JSON.stringify(payload)});
      const result = await response.json();
      if (!response.ok) throw new Error(result.detail || "Authentication failed.");
      window.sessionStorage.setItem("surface-access-token",result.access_token);
      setAuthToken(result.access_token); setAuthPassword(""); setMessage("Signed in to " + result.workspace.name + ".");
    } catch (error) { setMessage(error instanceof Error ? error.message : "Authentication failed."); }
    finally { setBusy(false); }
  }

  async function createProject(event: React.FormEvent) {
    event.preventDefault(); setBusy(true); setMessage("");
    try {
      const data = new FormData(); data.set("name", projectName);
      const response = await apiFetch(API + "/api/v1/projects", { method: "POST", body: data });
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
      const response = await apiFetch(API + "/api/v1/products", { method: "POST", body: form });
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
      const response = await apiFetch(API + "/api/v1/projects/" + selectedProject.id + "/room-image", { method: "POST", body: data });
      const result = await response.json();
      if (!response.ok) throw new Error(result.detail || "Upload failed");
      await loadProject(selectedProject.id); setMessage("Room photo uploaded. Detecting the selected surface automatically…");
    } catch (error) { setMessage(error instanceof Error ? error.message : "Upload failed."); }
    finally { setBusy(false); }
  }

  function assignProductToSurface(productId: string, mode: "floor" | "wall") {
    setSurfaceProducts(current => ({...current,[mode]:productId}));
    setSelectedProduct(productId);
    setMessage("Material assigned to the " + mode + ". Drag another product onto a surface to replace it.");
  }

  function updateDropTarget(event: React.DragEvent<HTMLCanvasElement>) {
    event.preventDefault();
    const rect = event.currentTarget.getBoundingClientRect();
    const point = {x:(event.clientX-rect.left)/rect.width,y:(event.clientY-rect.top)/rect.height};
    const floorHit = surfaceOutlines.floor.length>=3 && pointInPolygon(point,surfaceOutlines.floor);
    const wallHit = surfaceOutlines.wall.length>=3 && pointInPolygon(point,surfaceOutlines.wall);
    setDropTarget(floorHit && wallHit ? surfaceMode : floorHit ? "floor" : wallHit ? "wall" : null);
  }

  function dropProduct(event: React.DragEvent<HTMLCanvasElement>) {
    event.preventDefault();
    setDropTarget(null);
    const productId = event.dataTransfer.getData("application/surface-product");
    if (!productId) return;
    const rect = event.currentTarget.getBoundingClientRect();
    const point = {x:(event.clientX-rect.left)/rect.width,y:(event.clientY-rect.top)/rect.height};
    const floorHit = surfaceOutlines.floor.length>=3 && pointInPolygon(point,surfaceOutlines.floor);
    const wallHit = surfaceOutlines.wall.length>=3 && pointInPolygon(point,surfaceOutlines.wall);
    if (floorHit && wallHit) { assignProductToSurface(productId,surfaceMode); return; }
    if (floorHit) { assignProductToSurface(productId,"floor"); return; }
    if (wallHit) { assignProductToSurface(productId,"wall"); return; }
    setMessage("Drop the material inside a detected floor or wall outline. Detect or draw that surface first.");
  }

  function addPoint(event: React.MouseEvent<HTMLCanvasElement>) {
    if (!roomImageRef.current) return;
    const rect = event.currentTarget.getBoundingClientRect();
    const nextPoint = { x: (event.clientX - rect.left) / rect.width, y: (event.clientY - rect.top) / rect.height };
    if (sam2PromptMode) {
      setPromptPoints(current => [...current, { ...nextPoint, label: promptLabel }]);
      return;
    }
    setPoints(current => [...current, nextPoint]);
    setSurfaceOutlines(current => ({...current, [surfaceMode]: [...current[surfaceMode], nextPoint]}));
  }

  if (!authToken) return <main className="app-shell"><header className="app-nav"><a className="brand" href="/"><span className="brand-mark">S</span> SURFACE<span className="muted">ANALYZER</span></a><span className="status-dot">SECURE WORKSPACE</span></header><section className="workspace-head"><div><div className="eyebrow">SURFACE ANALYZER</div><h1>Your materials.<br/><em>Your workspace.</em></h1><p>Sign in or create a workspace to manage your material catalog and room visualizations.</p></div></section><section className="panel" style={{maxWidth:480,margin:"0 auto",padding:28}}><div className="panel-title"><span>{registerMode?"CREATE WORKSPACE":"WELCOME BACK"}</span></div><form className="stack-form" onSubmit={submitAuth}>{registerMode&&<><input value={workspaceName} onChange={e=>setWorkspaceName(e.target.value)} placeholder="Workspace name" minLength={2} required/><input value={authName} onChange={e=>setAuthName(e.target.value)} placeholder="Your full name" required/></>}<input type="email" value={authEmail} onChange={e=>setAuthEmail(e.target.value)} placeholder="Email address" required/><input type="password" value={authPassword} onChange={e=>setAuthPassword(e.target.value)} placeholder="Password (minimum 10 characters)" minLength={registerMode?10:1} required/><button className="dark-button" disabled={busy}>{busy?"Please wait…":registerMode?"Create workspace":"Sign in"}</button></form><button className="control-actions" onClick={()=>setRegisterMode(v=>!v)}>{registerMode?"Already have an account? Sign in":"New here? Create a workspace"}</button>{message&&<p className="helper-text">{message}</p>}</section></main>;

  return <main className="app-shell">
    <header className="app-nav"><a className="brand" href="/"><span className="brand-mark">S</span> SURFACE<span className="muted">ANALYZER</span></a><span className="workspace-tag">WORKSPACE / SURFACE STUDIO</span><button className="status-dot" onClick={()=>{window.sessionStorage.removeItem("surface-access-token");setAuthToken("");setProducts([]);setProjects([]);setSelectedProject(null);}}>SIGN OUT</button></header>
    <section className="workspace-head"><div><div className="eyebrow">YOUR MATERIAL WORKSPACE</div><h1>Make the room<br/><em>your canvas.</em></h1><p>Build a multi-material catalog, upload a room, outline a surface and preview finishes in place.</p></div><div className="head-count"><strong>{projects.length.toString().padStart(2,"0")}</strong><span>PROJECTS</span><strong>{products.length.toString().padStart(2,"0")}</strong><span>MATERIALS</span></div></section>
    {message && <div className="notice" role="status">{message}</div>}
    <div className="studio-grid">
      <aside className="studio-sidebar">
        <section className="panel"><div className="panel-title"><span>01 / PROJECTS</span><span>{projects.length} TOTAL</span></div>
          <form className="inline-form" onSubmit={createProject}><input value={projectName} onChange={e=>setProjectName(e.target.value)} placeholder="New project name" required/><button disabled={busy}>＋</button></form>
          <div className="project-list">{projects.map(project=><button key={project.id} className={"project-item "+(selectedProject?.id===project.id?"active":"")} onClick={()=>void loadProject(project.id)}><span className="project-icon">◫</span><span>{project.name}<small>{project.status}</small></span><span>↗</span></button>)}{projects.length===0&&<p className="empty-note">Your projects will appear here.</p>}</div>
        </section>
        <section className="panel"><div className="panel-title"><span>02 / MATERIAL LIBRARY</span><span>{products.length} PRODUCTS</span></div>
          <div className="product-list">{products.map(product=><button key={product.id} draggable onDragStart={event=>event.dataTransfer.setData("application/surface-product",product.id)} className={"product-item "+(selectedProduct===product.id?"active":"")} onClick={()=>assignProductToSurface(product.id,surfaceMode)} title="Click to apply to selected surface, or drag onto the floor or wall"><span className="swatch">{product.material_url?<img src={API+product.material_url} alt=""/>:<span>▧</span>}</span><span>{product.name}<small>{[product.category?.replaceAll("-"," "),product.brand,product.collection,product.width_mm&&product.height_mm?product.width_mm+" × "+product.height_mm+" mm":null,product.finish].filter(Boolean).join(" · ")||"Surface material"}</small></span></button>)}</div>
          <details className="add-material"><summary>＋ Add a surface product</summary><form onSubmit={createProduct} className="stack-form"><input name="name" placeholder="Material name" required/><input name="sku" placeholder="SKU / product code (optional)"/><select name="category" defaultValue="tile"><option value="tile">Tile / Porcelain</option><option value="natural-stone">Natural stone / Marble</option><option value="wood-flooring">Wood / Flooring</option><option value="wallpaper">Wallpaper</option><option value="countertop">Countertop / Slab</option><option value="paint">Paint / Coating</option><option value="panel">Wall / Decorative panel</option><option value="paver">Outdoor paver</option><option value="other">Other surface</option></select><input name="brand" placeholder="Brand / manufacturer (optional)"/><input name="collection" placeholder="Collection / range (optional)"/><div className="two-inputs"><input name="width_mm" type="number" min="1" placeholder="Width mm"/><input name="height_mm" type="number" min="1" placeholder="Height mm"/></div><select name="finish" defaultValue="Matt"><option>Matt</option><option>Polished</option><option>Gloss</option><option>Textured</option><option>Stone</option><option>Wood effect</option></select><label className="file-label">Seamless texture / main material image<input name="texture" type="file" accept="image/png,image/jpeg,image/webp"/></label><label className="file-label">Texture face variations (multiple)<input name="texture_faces" type="file" accept="image/png,image/jpeg,image/webp" multiple/></label><label className="file-label">Product gallery images (multiple)<input name="gallery" type="file" accept="image/png,image/jpeg,image/webp" multiple/></label><label className="file-label">Normal map (optional)<input name="normal_map" type="file" accept="image/png,image/jpeg,image/webp"/></label><label className="file-label">Roughness map (optional)<input name="roughness_map" type="file" accept="image/png,image/jpeg,image/webp"/></label><button className="dark-button" disabled={busy}>Save product</button></form></details>
        </section>
      </aside>
      <section className="visualizer-panel"><div className="visualizer-top"><div><div className="panel-title">03 / PHOTO VISUALIZER</div><h2>{selectedProject?.name || "Choose a project"}</h2></div><span className="visualizer-status">{roomUrl?"ROOM LOADED":"AWAITING PHOTO"}</span></div>
        {!selectedProject ? <div className="visualizer-empty"><div className="empty-symbol">＋</div><h3>Start with a project</h3><p>Create a project on the left, then upload a room photo to begin.</p></div> :
        <><div className="canvas-wrap">{roomUrl?<canvas ref={canvasRef} onClick={addPoint} onDragOver={updateDropTarget} onDragLeave={()=>setDropTarget(null)} onDrop={dropProduct} aria-label="Room photo. Drag a material onto the outlined floor or wall to apply it."/>:<div className="upload-empty"><div className="empty-symbol">↑</div><h3>Upload a room photograph</h3><p>JPG, PNG or WebP · up to 15 MB</p><label className="dark-button">Choose room photo<input type="file" accept="image/png,image/jpeg,image/webp" hidden onChange={e=>void uploadRoom(e.target.files?.[0])}/></label></div>}</div>
        {roomUrl&&<div className="visualizer-controls"><div className="control-row"><span>Surface outline</span><span>{points.length<3?"Not detected":points.length+" boundary points"} · Floor: {surfaceOutlines.floor.length>=3?"saved":"—"} · Wall: {surfaceOutlines.wall.length>=3?"saved":"—"}{detectionConfidence!==null?" · "+Math.round(detectionConfidence*100)+"% detection score":""}</span></div><div className="control-row"><span>AI object masks</span><span>{surfaceOcclusions.floor.length + surfaceOcclusions.wall.length} detected · {preserveOcclusions?"preservation on":"preservation off"}</span></div><div className="control-row"><span>Applied materials</span><span>Floor: {products.find(product=>product.id===(surfaceProducts.floor||selectedProduct))?.name||"None"} · Wall: {products.find(product=>product.id===(surfaceProducts.wall||selectedProduct))?.name||"None"}</span></div>{detectionWarnings.length>0&&<ul className="helper">{detectionWarnings.map((warning,index)=><li key={index}>{warning}</li>)}</ul>}<div className="range-row"><label style={{display:"flex",alignItems:"center",gap:10}}><input type="checkbox" checked={preserveOcclusions} onChange={e=>setPreserveOcclusions(e.target.checked)}/> Preserve detected furniture and fixtures</label></div><div className="range-row"><label>Surface type <select value={surfaceMode} onChange={e=>{const nextMode=e.target.value as "floor" | "wall";setSurfaceOutlines(current=>({...current,[surfaceMode]:points}));setPoints(surfaceOutlines[nextMode]);setSurfaceMode(nextMode);setDetectionConfidence(null);setDetectionWarnings([]);}}><option value="floor">Floor</option><option value="wall">Wall</option></select></label></div><div className="control-actions"><button disabled={detecting||busy} onClick={()=>void autoDetectFloor()}>{detecting?"Detecting…": "✦ Auto-detect " + (surfaceMode === "floor" ? "floor" : "wall")}</button><button onClick={()=>{setSam2PromptMode(value=>!value);setPromptPoints([]);setMessage("Click points on the image: green includes the surface, red excludes objects outside it.");}}>{sam2PromptMode?"Exit SAM 2 points":"✦ SAM 2 point selection"}</button><button disabled={refiningSurface||busy||promptPoints.length===0} onClick={()=>void refineSurfaceWithSam2()}>{refiningSurface?"Refining…":"Refine from points ("+promptPoints.length+")"}</button><button disabled={analyzingDepth||busy} onClick={()=>void analyzeRoomDepth()}>{analyzingDepth?"Analysing…":"✦ AI depth analysis"}</button><button onClick={()=>{setPoints([]);setSurfaceOutlines(current=>({...current,[surfaceMode]:[]}));setSurfaceOcclusions(current=>({...current,[surfaceMode]:[]}));setDetectionConfidence(null);setDetectionWarnings([]);}}>Clear outline</button><button onClick={()=>setPoints(current=>{const next=current.slice(0,-1);setSurfaceOutlines(saved=>({...saved,[surfaceMode]:next}));return next;})}>Undo point</button><label className="file-replace">Replace photo<input type="file" accept="image/png,image/jpeg,image/webp" onChange={e=>void uploadRoom(e.target.files?.[0])}/></label></div>{sam2PromptMode&&<div className="range-row"><label>Next point <select value={promptLabel} onChange={e=>setPromptLabel(Number(e.target.value) as 0|1)}><option value={1}>Include surface (green)</option><option value={0}>Exclude object (red)</option></select></label><button onClick={()=>setPromptPoints([])}>Clear prompt points</button><span>{promptPoints.length} prompts · click the room image to add points</span></div>}<div className="range-row"><label>Pattern scale <input type="range" min=".15" max=".9" step=".01" value={scale} onChange={e=>setScale(Number(e.target.value))}/></label><label>Opacity <input type="range" min=".2" max="1" step=".01" value={opacity} onChange={e=>setOpacity(Number(e.target.value))}/></label></div><div className="range-row"><label>Tile layout <select value={pattern} onChange={e=>setPattern(e.target.value)}><option value="grid">Straight / grid</option><option value="brick">Brick / offset</option><option value="diagonal">Diagonal</option><option value="herringbone">Herringbone</option></select></label><label>Grout width <input type="range" min=".004" max=".04" step=".001" value={groutWidth} onChange={e=>setGroutWidth(Number(e.target.value))}/></label></div><div className="range-row"><label>Grout colour <input type="color" value={groutColor} onChange={e=>setGroutColor(e.target.value)}/></label></div><p className="helper-text">Choose Floor or Wall, then use Auto-detect to propose the visible surface boundary from the room photo. Review the result: click the image to add boundary points, use Undo point to refine it, or Clear outline to start again. Detection may need correction around rugs, furniture, reflections or unusual camera angles.</p>{depthMap&&<div className="ai-depth-preview"><strong>Local AI depth map</strong><img src={depthMap} alt="AI-estimated relative scene depth" style={{display:"block",width:"min(220px,100%)",height:"auto",marginTop:8,borderRadius:8}}/><small>Relative depth only · not a floor/wall mask</small></div>}</div>}</>}
      </section>
    </div>
    <footer className="studio-footer"><span>© 2026 SURFACE ANALYZER</span><span>PHOTO WORKFLOW MVP · MULTI-MATERIAL CATALOG</span></footer>
  </main>;
}

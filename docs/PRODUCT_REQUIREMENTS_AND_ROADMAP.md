# Surface Analyzer — Product Requirements & Competitive Build Plan

## Product ambition

Build an independent, self-hosted surface visualization software product that businesses install and operate on their own infrastructure. It should compete with established room visualizers while serving manufacturers, distributors, retailers, showrooms, and design professionals.

The benchmark is the customer journey and feature quality of Roomvo, not its implementation or proprietary assets. Surface Analyzer must use its own UX, data model, rendering pipeline, and original code.

## Product principles

1. **Visual trust first.** Product appearance, dimensions, pattern repeat, perspective, grout, and surface boundaries must be controllable and reproducible. Generative AI must not silently invent product details.
2. **One catalog, many channels.** An organization manages products once and publishes them to its own visualizer, product pages, dealer network, QR links, kiosks, and API.
3. **Multi-material, not tile-only.** Tiles are the launch vertical; the domain model must support flooring, wood, stone, countertops, wallpaper, paint, panels, pavers, and future surface types.
4. **Business outcomes.** Every visualization can become a saved design, comparison, sample request, quote request, store visit, or commerce handoff.
5. **Self-hostable and extensible.** Docker-first deployment, documented APIs, web components/SDK, and S3-compatible storage.
6. **Accessible and mobile-first.** Customer visualizer must work without an app install and provide a usable fallback when camera or WebXR support is absent.

## Competitive baseline

Public Roomvo materials describe photo upload and sample rooms, searchable product catalogs, favorites, compare mode, multi-surface visualization, grout controls, QR entry, branded embeds, product details, lead capture, image sharing/download, and integrations. These are baseline expectations, not differentiators.

## Differentiation strategy

- **Catalog operations:** bulk CSV/XLSX import, supplier feeds, product variants, collections, asset validation, duplicate detection, localization, pricing/availability, and catalog synchronization APIs.
- **Material intelligence:** separate product photography from render-ready seamless textures; support multiple texture faces, physical dimensions, repeat/rotation, finish, normal/roughness maps where available, and provenance/quality checks.
- **Rendering quality:** deterministic perspective mapping, surface segmentation with human correction, tile/board layout geometry, grout/joints, lighting and shadow preservation, edge-aware occlusion, multi-surface editing, and reproducible project settings.
- **AI assistance:** propose floor/wall/countertop masks, detect boundaries and obstructions, infer camera geometry, classify material suitability, and flag poor source assets. AI suggestions remain editable and confidence-scored.
- **Sales workflow:** saved projects, side-by-side comparisons, share links, quote/sample requests, lead inbox, showroom assignment, product availability, and analytics from visualization to conversion.
- **Deployment and integration:** customer-controlled on-premises or private-cloud installation, customer branding, custom domains, embed SDK, QR/kiosk mode, webhooks, and API access. The software must remain fully usable inside the customer's own environment.

## Product areas

### A. Catalog and product information management

A product is not just a name and one image. It has:
- Identity: name, SKU, barcode/GTIN, brand, manufacturer, collection, description, status.
- Classification: category, material family, application/surface compatibility.
- Specifications: width, height, thickness, units, plank/tile dimensions, pack coverage, weight where relevant.
- Appearance: base colour, pattern, finish, texture, variation, edge/rectification details.
- Commercial data: price, currency, sale price, stock status, availability, sample eligibility, CTA destinations.
- Variants: size, colour, finish, design, batch/lot, and supplier-specific SKU.
- Assets: hero image, gallery, detail/macro images, installation images, render texture faces, optional normal/roughness/height maps, CAD/3D assets, and technical documents.
- Import/export: CSV/XLSX templates, API sync, supplier feeds, asset ZIP mapping, validation report, and rollback.

Asset roles must be explicit. A marketing photograph must never be assumed to be a seamless render texture.

### B. Visualization experience

- Upload a room photo, use curated sample scenes, or launch camera mode.
- Detect and edit multiple surfaces in one scene.
- Support floor, wall, backsplash, shower, countertop, exterior, and other configured surfaces.
- Product browse/search/filter by brand, collection, size, finish, colour, category, and availability.
- Render physical scale, perspective, rotation, layout patterns, grout/joints, and surface finish.
- Preserve room lighting, shadows, furniture, fixtures, and occlusion as far as the deterministic pipeline permits.
- Compare products or saved designs side by side.
- Save, reopen, duplicate, share, export, and download visualizations.
- Provide mobile-first touch controls and desktop precision tools.

### C. Sales and business platform

- Organization dashboard, user roles and permissions, brand settings, custom domain.
- Lead inbox and project/customer association.
- Sample, quote, appointment, and store-locator CTAs.
- Product-level QR codes and kiosk mode.
- Embed SDK, APIs, webhooks, analytics, and conversion attribution.
- Catalog quality, usage, performance, and sales dashboards.

## Rendering architecture

Use a hybrid but deterministic-first pipeline:
1. Decode and normalize source room image; retain original.
2. Segment candidate surfaces using computer vision/ML; return masks, polygons, confidence, and editable boundaries.
3. Estimate plane geometry and perspective transform; store editable corner/mesh geometry.
4. Generate layout geometry from product physical dimensions and chosen installation pattern.
5. Map the correct texture face(s) into each tile/plank polygon using perspective-correct transforms.
6. Composite material while preserving non-target pixels, shadows, highlights, and occlusion layers.
7. Apply finish response (matte, satin, polished, textured) using optional material maps and controlled parameters.
8. Export deterministic render with complete parameter/version metadata.

Generative image models may be offered as an optional enhancement, never as the only renderer or as the source of truth for SKU appearance.

## Core domain entities

- Organization, User, Role, Permission, APIKey, BrandSettings
- Catalog, Category, Brand, Manufacturer, Collection, Product, ProductVariant
- ProductAsset, MaterialProfile, MaterialMap, TextureFace, InstallationPattern, GroutProfile
- Project, ProjectMember, RoomImage, Scene, Surface, SurfaceGeometry, RenderJob, RenderOutput
- SavedDesign, Comparison, ShareLink
- Lead, SampleRequest, QuoteRequest, Appointment, Store
- Embed, Domain, Webhook, Integration, UsageEvent, AuditEvent

All customer data belongs to the locally installed organization and is isolated within that installation. A deployment must not require a shared vendor-hosted multi-tenant control plane. Product assets have explicit asset type, dimensions, MIME, checksum, and storage lifecycle.

## Delivery roadmap and acceptance gates

### Phase 0 — Current MVP stabilization
- Preserve existing projects and product records.
- Add API/frontend automated tests and end-to-end compose verification.
- Correct image coordinate handling and current canvas sizing behavior.
- Make upload failures and missing texture states explicit.

**Gate:** existing local workflow works reliably; no existing data loss.

### Phase 1 — Catalog foundation
- Generalize TileProduct into Product while maintaining a compatibility migration.
- Add categories, variants, collections, product assets, material profiles, and texture faces.
- Add a proper product creation/edit experience with multiple assets and previews.
- Add CSV import with validation and error report.

**Gate:** an organization can create, edit, filter, import, and publish its catalog with multiple variants and render assets.

### Phase 2 — Deterministic renderer
- Surface geometry editor and perspective calibration.
- Physical tile/plank dimensions and repeat scale.
- Grid, brick, diagonal, herringbone, and configurable layout patterns.
- Grout width/colour and edge alignment.
- Multiple texture-face distribution and rotation.
- Save/reopen identical render settings.

**Gate:** measured dimensions and known test scenes produce repeatable geometry; no repeated marketing thumbnail masquerading as a texture.

### Phase 3 — Scene understanding and realism
- AI-assisted surface segmentation with confidence and manual correction.
- Multi-surface scenes and occlusion layers.
- Lighting/shadow preservation and finish response.
- Render quality benchmark set covering varied rooms, angles, and surfaces.

**Gate:** benchmark review by humans shows acceptable boundaries and product fidelity; failures are surfaced rather than hidden.

### Phase 4 — Customer visualizer
- Guided photo/sample-scene/camera entry.
- Catalog browsing, filters, favorites, compare.
- Multi-surface controls, share/export, saved designs.
- Mobile-first UX and accessibility.

**Gate:** an unauthenticated shopper can complete a visualization and share or request a quote without staff assistance.

### Phase 5 — Commercial platform
- Leads, sample/quote requests, appointments, stores, QR and kiosk.
- Embed SDK, API keys, webhooks, analytics and attribution.
- Organization branding, custom domains, role management.

**Gate:** a retailer can install the software on its own infrastructure, integrate the visualizer into its website, and trace a lead from product view to request.

### Phase 6 — Enterprise and scale
- Supplier catalog feeds, ERP/PIM/DAM integrations.
- Installation health, optional license validation, backups, observability, and operational administration.
- Installer and upgrade reliability, backups and restore, observability, security testing, and offline-capable operation where practical.
- Performance budgets and asynchronous render workers.

**Gate:** customer installation passes security, organization-level access control, backup/restore, load, upgrade, and operational-readiness checks.

## Immediate engineering priorities

1. Replace the single-image material assumption with explicit product assets and texture faces.
2. Generalize the catalog without breaking the existing TileProduct API or migrating away existing records.
3. Replace the current naive repeated Canvas pattern with a perspective-aware layout renderer.
4. Add tests for upload validation, asset associations, catalog CRUD, and renderer geometry.
5. Do not describe the MVP as Roomvo-equivalent until the rendering and customer workflow acceptance gates pass.

## Success metrics

- Time from catalog import to first published visualization.
- Percentage of products with valid render-ready assets.
- Surface boundary correction rate.
- Render completion time and failure rate.
- Repeatability and product-fidelity review scores.
- Visualization-to-save, visualization-to-share, sample, quote, and purchase conversion.
- Catalog sync freshness and embed uptime.

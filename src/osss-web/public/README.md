# `public/`

The `public/` directory is where all **static assets** for the OSSS Web application live.  
Files placed here are served **verbatim** at the root of the site and do not go through Webpack or
the Next.js bundling pipeline.

---

## 📌 Purpose

- **Host static files** such as images, icons, fonts, and documents that need to be served directly.
- **Provide globally accessible assets** without requiring imports or special bundling.
- **Mirror a conventional `/static` folder** — anything here is copied to the build output as-is.

---

## 📂 Usage & Examples

- Place a file in `public/` → it becomes available at the root of your app.

```
public/
├── favicon.ico          # → https://example.com/favicon.ico
├── robots.txt           # → https://example.com/robots.txt
├── images/logo.png      # → https://example.com/images/logo.png
└── docs/demo.pdf        # → https://example.com/docs/demo.pdf
```

- Example usage in a component:

```tsx
<Image src="/images/logo.png" alt="OSSS Logo" width={200} height={60} />
```

---

## 🔑 How It Works

- **Direct serving**: Next.js does not transform or hash filenames in `public/`. What you put in is what you get out.
- **Caching**: Files are typically cached aggressively by browsers/CDNs. Use versioned filenames (e.g. `logo.v2.png`) to bust caches.
- **Security**: All files are publicly accessible. Do **not** put secrets or private files here.
- **Relative URLs**: Always reference starting with `/`, which maps to the site root.

---

## 🚦 Developer Notes

- **Good candidates**: Logos, static images, PDF documentation, robots.txt, sitemap.xml, favicons.
- **Bad candidates**: API secrets, private documents, environment configs — these should never be committed here.
- **Alternatives**: For images that benefit from optimization (resizing, WebP, lazy loading), prefer Next.js `<Image>` component pointing to `/public` assets.

---

## ✅ Summary

The `public/` directory is the **static asset root** for OSSS Web.  
Anything placed here is served **directly at runtime** without processing.  

Use it for:  

- Favicons and PWA icons.  
- Robots and sitemap files.  
- Logos, static images, and downloads.  

Avoid placing anything here that should not be publicly accessible.

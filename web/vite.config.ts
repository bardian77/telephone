import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'

// GitHub Pages serves the site under /<repo>/; set VITE_BASE=/telephone/ in CI.
export default defineConfig({
  plugins: [react()],
  base: process.env.VITE_BASE ?? '/',
  server: {
    proxy: { '/api': 'http://127.0.0.1:8000' },
  },
})

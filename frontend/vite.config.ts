// @ts-ignore -- The Tailwind Vite plugin is installed in Docker's node_modules volume.
import react from '@vitejs/plugin-react'

// @ts-ignore -- The Tailwind Vite plugin is installed in Docker's node_modules volume.
import { defineConfig } from 'vite'

// @ts-ignore -- The Tailwind Vite plugin is installed in Docker's node_modules volume.
import tailwindcss from '@tailwindcss/vite';


// https://vite.dev/config/
export default defineConfig({
  plugins: [react(), tailwindcss()],
})

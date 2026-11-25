# Experts Search Frontend

## Develop in a VS Code dev container

Install and start Docker Desktop, and install the VS Code
[Dev Containers extension](https://marketplace.visualstudio.com/items?itemName=ms-vscode-remote.remote-containers).

1. In VS Code, use **File → Open Folder…** to open this `frontend` directory
   (rather than the repository root).
2. Run **Dev Containers: Reopen in Container** from the Command Palette
   (`Cmd+Shift+P` on macOS).
3. Wait for the image download and the automatic `npm ci` to finish.
4. In the VS Code terminal inside the container, run:

   ```sh
   npm run dev -- --host 0.0.0.0 --port 5173 --strictPort
   ```

5. Open <http://localhost:5173>, or use the forwarded port in VS Code's **Ports** tab.

The configuration in `.devcontainer/devcontainer.json` provides Node.js 24,
installs the frontend dependencies, and forwards Vite's port. Its Dockerfile
uses the official `node:24-bookworm-slim` image from Docker Hub and adds Git,
curl, certificates, and sudo for the non-root `node` user. Dependencies live in a Docker volume so Linux packages
are kept separate from any macOS or Windows `node_modules` on the host.
VS Code's terminal and TypeScript tooling use the dependencies inside the container.
The source files remain in this local folder, so edits persist when the container
is rebuilt.

After changing `package-lock.json`, run `npm ci` in the container again.
After changing the dev container configuration, run **Dev Containers: Rebuild
Container**. Stop Vite with `Ctrl+C` before restarting it.

If opening fails, check that Docker Desktop is running (`docker info` should
succeed in a host terminal), that the Dev Containers extension is installed,
and that VS Code opened `frontend` itself. See **Dev Containers: Show Container
Log** for startup or installation errors.

If the log stays at `docker pull` / `Pulling fs layer`, the image download has
not finished; dependency installation has not started yet. You can run
`docker pull node:24-bookworm-slim` in a host terminal to see the download
separately. Connection reset errors indicate a registry connection problem;
check your network, VPN, or Docker Desktop proxy settings if downloads fail.

This container runs the frontend independently. Start backend services separately
using the repository root README when you need them. The root Compose
`front-end` service is a separate way to run Vite; stop it before running the
dev container's server if it already occupies host port 5173.

## Vite template reference

This template provides a minimal setup to get React working in Vite with HMR and some ESLint rules.

Currently, two official plugins are available:

- [@vitejs/plugin-react](https://github.com/vitejs/vite-plugin-react/blob/main/packages/plugin-react) uses [Oxc](https://oxc.rs)
- [@vitejs/plugin-react-swc](https://github.com/vitejs/vite-plugin-react/blob/main/packages/plugin-react-swc) uses [SWC](https://swc.rs/)

## React Compiler

The React Compiler is not enabled on this template because of its impact on dev & build performances. To add it, see [this documentation](https://react.dev/learn/react-compiler/installation).

## Expanding the ESLint configuration

If you are developing a production application, we recommend updating the configuration to enable type-aware lint rules:

```js
export default defineConfig([
  globalIgnores(['dist']),
  {
    files: ['**/*.{ts,tsx}'],
    extends: [
      // Other configs...

      // Remove tseslint.configs.recommended and replace with this
      tseslint.configs.recommendedTypeChecked,
      // Alternatively, use this for stricter rules
      tseslint.configs.strictTypeChecked,
      // Optionally, add this for stylistic rules
      tseslint.configs.stylisticTypeChecked,

      // Other configs...
    ],
    languageOptions: {
      parserOptions: {
        project: ['./tsconfig.node.json', './tsconfig.app.json'],
        tsconfigRootDir: import.meta.dirname,
      },
      // other options...
    },
  },
])

```

You can also install [eslint-plugin-react-x](https://npmx.dev/package/eslint-plugin-react-x) and [eslint-plugin-react-dom](https://npmx.dev/package/eslint-plugin-react-dom) for React-specific lint rules:

```js
// eslint.config.js
import reactX from 'eslint-plugin-react-x'
import reactDom from 'eslint-plugin-react-dom'

export default defineConfig([
  globalIgnores(['dist']),
  {
    files: ['**/*.{ts,tsx}'],
    extends: [
      // Other configs...
      // Enable lint rules for React
      reactX.configs['recommended-typescript'],
      // Enable lint rules for React DOM
      reactDom.configs.recommended,
    ],
    languageOptions: {
      parserOptions: {
        project: ['./tsconfig.node.json', './tsconfig.app.json'],
        tsconfigRootDir: import.meta.dirname,
      },
      // other options...
    },
  },
])

```

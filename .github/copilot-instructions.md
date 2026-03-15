# Copilot Instructions for MainsailDev

- Repo layout: `mainsail/` (Vue 2 + Vite frontend) and `virtual-klipper-printer/` (Dockerized Moonraker/Klipper simulator + dummy webcam). Primary work happens in `mainsail/`.
- Node requirements live in [mainsail/package.json](mainsail/package.json): use Node 18 or 20; install with `npm install`.
- Dev server: run `npm run serve` in `mainsail/` (Vite on 0.0.0.0:8080 per [mainsail/vite.config.ts](mainsail/vite.config.ts)). If 8080 is taken, pass `--port <alt>`.
- Local backend: start the simulator with `docker compose up -d` inside `virtual-klipper-printer/`; Moonraker API is on 7125 and dummy webcam on 8110 per [virtual-klipper-printer/docker-compose.yml](virtual-klipper-printer/docker-compose.yml).
- Point the UI at the simulator via [mainsail/public/config.json](mainsail/public/config.json) (`hostname`/`port`/`path`). The store ingests this in [mainsail/src/store/actions.ts](mainsail/src/store/actions.ts#L17-L55); env `VUE_APP_INSTANCES_DB` can override `instancesDB` (`moonraker`/`browser`/`json`).
- Routing and sockets: Vuex state lives in `mainsail/src/store/`; socket setup hinges on `socket/setData` commits and `Vue.$socket.connect()` when `instancesDB` is `moonraker` (see [mainsail/src/main.ts](mainsail/src/main.ts#L70-L110)).
- Component style: Vue 2 with class decorators (`vue-property-decorator`) and Vuetify; path alias `@` -> `src` (see [mainsail/vite.config.ts](mainsail/vite.config.ts#L64-L88)).
- Localization: translations in `mainsail/src/locales/*.json`; messages loaded via `vue-i18n`. Keep keys consistent; use `npm run i18n-extract` to detect missing keys.
- Styling: Sass with PostCSS nesting; themes under `mainsail/public/css/themes/` and assets in `mainsail/src/assets/styles/`.
- Builds: `npm run build` outputs to `dist/` and zips via `build.zip`; `npm run preview` serves the build (default 4173).
- Testing: `npm run test` builds, serves preview, then runs Cypress via `start-server-and-test`; Cypress base URL is 4173 per [mainsail/cypress.config.ts](mainsail/cypress.config.ts).
- E2E examples: [mainsail/cypress/e2e/dashboard.cy.ts](mainsail/cypress/e2e/dashboard.cy.ts) asserts the dashboard shows connection text; adapt this pattern for new flows.
- PWA/service worker: enabled even in dev via Vite PWA plugin (see [mainsail/vite.config.ts](mainsail/vite.config.ts#L5-L61)); beware caching when changing `config.json`.
- Remote mode config lives in [mainsail/remote/config.json](mainsail/remote/config.json); keep `public/config.json` for local dev and `remote/` for hosted scenarios.
- Debugging connectivity: `curl http://localhost:7125/printer/info` validates Moonraker; UI should show "Connecting to localhost" then ready.
- Preferred conventions: keep imports absolute via `@/`; use Vuex modules instead of ad-hoc event buses; update `configInstances` when using `instancesDB=json`.
- Avoid editing generated files in `dev-dist/` or `dist/`; treat `printer_data/` in the simulator as runtime state, not source.

/// <reference types="vite/client" />

interface ImportMetaEnv {
  readonly VITE_JARVIS_BRIDGE_URL?: string;
  readonly VITE_JARVIS_WS_URL?: string;
  readonly VITE_APP_VERSION?: string;
}

interface ImportMeta {
  readonly env: ImportMetaEnv;
}